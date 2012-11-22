#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the 7th step of ZIBgridfree.}

	This tool will perform a direct reweighting of the sampling nodes. It should be run on a pool of converged nodes. From the reweighted partial distributions that were sampled in the individual nodes one can reconstruct the overall Boltzmann distribution.
	
	B{The next step is L{zgf_analyze}.}

How it works
============
	At the command line, type::
		$ zgf_reweight [options]

Direct reweighting strategies
=============================

	Currently, three different direct reweighting approaches are implemented:

		- Direct free energy reweighting: see Klimm, Bujotzek, Weber 2011
		- Entropy reweighting: see Klimm, Bujotzek, Weber 2011
		- Presampling analysis reweighting: see formula 18 in Fackeldey, Durmaz, Weber 2011

	B{Entropy reweighting "entropy"}

	Choice of the evaluation region: The size of the evaluation region is chosen as large as the variance of the internal coordinate time series (obtained from the sampling trajectory), averaged over all nodes.

	Choice of reference points by energy region: Instead of specifying a fixed number of reference points, we follow the approach of M. Weber, K. Andrae: A simple method for the estimation of entropy differences. MATCH Comm. Math. Comp. Chem. 63(2):319-332, 2010. This means we are picking a dynamic number of reference points by declaring all the sampling points within a certain energy region (which we choose as the energy standard deviation) around the mean potential energy of the system as reference points.

	Finding of near points: Our measure of conformational entropy is based on an estimate of the sampling density. For this purpose, we look for sampling points adjacent to our reference points and denote them as 'near points'. As each reference points counts as its own near point, the number of near points can never be zero.

	Calculation of entropy and free energy: The number of (inverse) near points enters directly into the calculation of entropy for the corresponding node. Finally, thermodynamic weights are derived from the free energy differences. Some useful information regarding reference points, their adjacent near points and energy averages will be stored in the reweighting log file.

Frame weights
=============

	As in Gromacs we use simple harmonic restraint potentials to approximate the original radial basis functions used in ZIBgridfree, we have to perform a frame reweighting of the sampling trajectories afterwards. The frame weight of each individual frame q belonging to node i is calculated as:

	frame_weight(q) = S{Phi}_i(q) / exp( -S{beta} * penalty_potential_i(q) )

	Frame weights should yield values between zero and one. Slightly higher values than one are feasible. Note that frame weights are not normalized to one.

	Overweight frames are possible if S{Phi}_i(q) is high (meaning that q is well within its native basis function) while the penalty_potential_i(q) is high, as well. Hence, q is punished wrongly, as q should only be punished by the penalty potential if it attempts to leave its native basis function.

	When overweight frames occur, this probably means that your approximation of the S{Phi} function for the corresponding node is bad. You can check this by using L{zgf_browser}. If the penalty potential kicks in where S{Phi} is still good, you have got a bad approximation of the S{Phi} function. Overweight frame weights will trigger a WARNING. Furthermore, any occurence of overweight frame weights will be stored in the reweighting log file.

Choice of energy observables for reweighting
============================================

You can pick from various options. You can decide if you want to use observables from the standard run (as stored in 'ener.edr') or from a rerun (as stored in 'rerun.edr') that you did with L{zgf_rerun}. You can also read bonded and non-bonded energy observables from different edr-files. If you are not happy with the standard choice of energy observables, you can provide a file with costum observables (non-bonded only).

Check restraint energy
======================

This option is mainly for debugging. It compares wether ZIBMolPy internally calculates the same restraint energies as Gromacs (as stored in the edr-file of the run). You can also compare ZIBMolPy and Gromacs restraint energies visually by using the FrameWeightPlot in L{zgf_browser}.

"""

from ZIBMolPy.constants import AVOGADRO, BOLTZMANN
from ZIBMolPy.restraint import DihedralRestraint, DistanceRestraint
from ZIBMolPy.ui import Option, OptionsList
from ZIBMolPy.phi import get_phi, get_phi_potential
from ZIBMolPy.pool import Pool
from ZIBMolPy import gromacs
import zgf_cleanup

from subprocess import Popen, PIPE
from datetime import datetime
from tempfile import mktemp
from warnings import warn
import numpy as np
import sys
import os
import re
from os import path


CRITICAL_FRAME_WEIGHT = 5.0


options_desc = OptionsList([
	Option("c", "ignore-convergence", "bool", "reweight despite not-converged", default=False),
	Option("f", "ignore-failed", "bool", "reweight and ignore mdrun-failed nodes", default=False),
	Option("m", "method", "choice", "reweighting method", choices=("entropy", "direct", "presampling")),
	Option("b", "e-bonded", "choice", "bonded energy type", choices=("run_standard", "rerun_standard", "none")),
	Option("n", "e-nonbonded", "choice", "nonbonded energy type", choices=("run_standard", "run_moi", "run_moi_sol_sr", "run_moi_sol_lr", "run_custom", "rerun_standard", "rerun_moi", "rerun_moi_sol_sr", "rerun_moi_sol_lr", "rerun_custom", "none")),
	Option("e", "custom-energy", "file", extension="txt", default="custom_energy.txt"),
	Option("t", "presamp-temp", "float", "presampling temp", default=1000), #TODO maybe drop this and ask user instead... method has to be reworked anyway
	Option("r", "save-refpoints", "bool", "save refpoints in observables", default=False),
	Option("R", "check-restraint", "bool", "check if ZIBMolPy calculates the same restraint energy as Gromacs", default=False),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return( len(pool) > 1 and len(pool.where("isa_partition and state in ('converged','not-converged','mdrun-failed')")) == len(pool.where("isa_partition")) )


#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	zgf_cleanup.main()
	
	pool = Pool()

	not_reweightable = "isa_partition and state not in ('converged'"
	if(options.ignore_convergence):
		not_reweightable += ",'not-converged'"
	if(options.ignore_failed):
		not_reweightable += ",'mdrun-failed'"
	not_reweightable += ")"

	if pool.where(not_reweightable):
		print "Pool can not be reweighted due to the following nodes:"		
		for bad_guy in pool.where(not_reweightable):
			print "Node %s with state %s."%(bad_guy.name, bad_guy.state)
		sys.exit("Aborting.")

	active_nodes = pool.where("isa_partition and state != 'mdrun-failed'")
	assert(len(active_nodes) == len(active_nodes.multilock())) # make sure we lock ALL nodes

	if(options.check_restraint):
		for n in active_nodes:
			check_restraint_energy(n)

	if(options.method == "direct"):
		reweight_direct(active_nodes, options)
	elif(options.method == "entropy"):
		reweight_entropy(active_nodes, options)
	elif(options.method == "presampling"):
		reweight_presampling(active_nodes, options)
	else:
		raise(Exception("Method unkown: "+options.method))
	
	weight_sum = np.sum([n.tmp['weight'] for n in active_nodes])
	
	print "Thermodynamic weights calculated by method '%s':"%options.method
	for n in active_nodes:
		n.obs.weight_direct = n.tmp['weight'] / weight_sum
		if(options.method == "direct"):
			print("  %s with mean_V: %f [kJ/mol], %d refpoints and weight: %f" % (n.name, n.obs.mean_V, n.tmp['n_refpoints'], n.obs.weight_direct))
		else:
			print("  %s with A: %f [kJ/mol] and weight: %f" % (n.name, n.obs.A, n.obs.weight_direct))
	print "The above weighting uses bonded energies='%s' and nonbonded energies='%s'."%(options.e_bonded, options.e_nonbonded)

	for n in active_nodes:
		n.save()

	active_nodes.unlock()


#===============================================================================
def reweight_direct(nodes, options):
	print "Direct free energy reweighting: see Klimm, Bujotzek, Weber 2011"

	custom_energy_terms = None
	if(options.e_nonbonded in ("run_custom", "rerun_custom")):
		assert(path.exists(options.custom_energy))
		custom_energy_terms = [entry.strip() for entry in open(options.custom_energy).readlines() if entry != "\n"]
	
	beta = nodes[0].pool.thermo_beta
	
	for n in nodes:
		# get potential V and substract penalty potential
		energies = load_energy(n, options.e_bonded, options.e_nonbonded, custom_energy_terms)

		frame_weights = n.frameweights
		phi_values = n.phi_values
		phi_weighted_energies = energies + get_phi_potential(n.trajectory, n)

		# define evaluation region where sampling is rather dense, e. g. around mean potential energy with standard deviation of potential energy
		n.obs.mean_V = np.average(phi_weighted_energies, weights=frame_weights)
		n.obs.std_V = np.sqrt(np.average(np.square(phi_weighted_energies - n.obs.mean_V), weights=frame_weights))
		n.tmp['weight'] = 0.0
	
	# new part
	mean_mean_V = np.mean([n.obs.mean_V for n in nodes])
	std_mean_V = np.sqrt(np.mean([np.square(n.obs.mean_V - mean_mean_V) for n in nodes]))

	print "### original std_mean_V: %f"%std_mean_V
	print "### mean over obs.std_V: %f"%np.mean([n.obs.std_V for n in nodes]) #TODO decide upon one way to calculate std_mean_V

	energy_region = std_mean_V
	
	for n in nodes:
		refpoints = np.where(np.abs(phi_weighted_energies - n.obs.mean_V) < energy_region)[0]
		n.tmp['n_refpoints'] = len(refpoints)
		
		log = open(n.reweighting_log_fn, "a") # using separate log-file
		def output(message):
			print(message)
			log.write(message+"\n")

		output("======= Starting node reweighting %s"%datetime.now())

		output("  unweighted mean V: %s [kJ/mol], without penalty potential" % np.mean(energies))
		output("  phi-weighted mean V: %s [kJ/mol], without penalty potential" % np.mean(phi_weighted_energies))
		output("  weighted mean V: %f [kJ/mol]" % n.obs.mean_V)
		output("  energy region (=tenth of weighted V standard deviaton): %f [kJ/mol]" % energy_region)
		output("  number of refpoints: %d" % n.tmp['n_refpoints'])

		# calculate weights with direct ansatz
		for ref in refpoints:
			n.tmp['weight'] += np.exp(beta*phi_weighted_energies[ref])
		
		n.tmp['weight'] = float(n.trajectory.n_frames) / float(n.tmp['weight'])
		n.obs.S = 0.0
		n.obs.A = 0.0
		if(options.save_refpoints):
			n.obs.refpoints = refpoints
		
		log.close()


#===============================================================================
def reweight_entropy(nodes, options):
	print "Entropy reweighting: see Klimm, Bujotzek, Weber 2011"

	custom_energy_terms = None
	if(options.e_nonbonded in ("run_custom", "rerun_custom")):
		assert(path.exists(options.custom_energy))
		custom_energy_terms = [entry.strip() for entry in open(options.custom_energy).readlines() if entry != "\n"]

	# calculate variance of internal coordinates
	conjugate_var = np.mean([n.trajectory.merged_var_weighted() for n in nodes]) # this be our evaluation region

	# find refpoints and calculate nearpoints
	for n in nodes:
		log = open(n.reweighting_log_fn, "a") # using separate log-file
		def output(message):
			print(message)
			log.write(message+"\n")
			
		output("======= Starting node reweighting %s"%datetime.now())
		
		# get potential V and substract penalty potential
		energies = load_energy(n, options.e_bonded, options.e_nonbonded, custom_energy_terms)

		frame_weights = n.frameweights
		phi_values = n.phi_values
		phi_weighted_energies = energies + get_phi_potential(n.trajectory, n)
	
		# calculate mean V
		n.obs.mean_V = np.average(phi_weighted_energies, weights=frame_weights)
		n.tmp['weight'] = 1.0
		n.obs.std_V = np.sqrt(np.average(np.square(phi_weighted_energies - n.obs.mean_V), weights=frame_weights))
	
		# every frame within this region is considered refpoint
		energy_region = n.obs.std_V
		refpoints = np.where(np.abs(phi_weighted_energies - n.obs.mean_V) < energy_region)[0]
			
		output("  unweighted mean V: %s [kJ/mol], without penalty potential" % np.mean(energies))
		output("  phi-weighted mean V: %s [kJ/mol], without penalty potential" % np.mean(phi_weighted_energies))
		output("  weighted mean V: %f [kJ/mol]" % n.obs.mean_V)
		output("  energy region (=weighted V standard deviation): %f [kJ/mol]" % energy_region)
		output("  evaluation region (=conjugate variance): %f" % conjugate_var)
		output("  number of refpoints: %d" % len(refpoints))

		if( len(refpoints) == 0 ):
			raise(Exception("Zero refpoints for "+n.name+" ["+n.trr_fn+"]."))
				
		norm_inv_nearpoints = []
		for ref in refpoints: # for each refpoint count nearpoints
			diffs = (n.trajectory - n.trajectory.getframe(ref)).norm2() #TODO -> needs Marcus-check -> Do we have to consider Frame-weights here?
			nearpoints = np.sum(diffs < conjugate_var)
			#output("    refpoint %d with energy %f has %d nearpoints" % (ref, phi_weighted_energies[ref], nearpoints))
			if(nearpoints == 1):
				output("WARNING: No nearpoints found for refpoint %d! (%s)" % (ref, n.name))
			norm_inv_nearpoints.append( float(n.trajectory.n_frames)/float(nearpoints) ) # new calculation formula (see wiki), +1 is implicit as refpoint counts as nearpoint
				
		n.tmp['medi_inv_nearpoints'] = np.median(norm_inv_nearpoints)
		n.obs.S = AVOGADRO*BOLTZMANN*np.log(n.tmp['medi_inv_nearpoints']) # [kJ/mol*K]
		n.obs.A = n.obs.mean_V - nodes[0].pool.temperature*n.obs.S # [kJ/mol]
		if(options.save_refpoints):
			n.obs.refpoints = refpoints

		log.close()

	nodes.sort(key = lambda n: n.obs.A) # sort in ascending order by free energy values		
	for (n1, n2) in zip(nodes[1:], nodes[:-1]): # calculate and normalize weights
		n1.tmp['weight'] = np.exp(-nodes[0].pool.thermo_beta*( n1.obs.A - n2.obs.A )) * n2.tmp['weight']
	

#===============================================================================
def reweight_presampling(nodes, options):
	print "Presampling analysis reweighting: see formula 18 in Fackeldey, Durmaz, Weber 2011"

	custom_energy_terms = None
	if(options.e_nonbonded in ("run_custom", "rerun_custom")):
		assert(path.exists(options.custom_energy))
		custom_energy_terms = [entry.strip() for entry in open(options.custom_energy).readlines() if entry != "\n"]
	
	# presampling data
	presampling_internals = nodes[0].pool.root.trajectory # alternatively pool[0].trajectory
	
	# presampling and sampling beta
	beta_samp = nodes[0].pool.thermo_beta
	beta_presamp = 1/(options.presamp_temp*BOLTZMANN*AVOGADRO)
		
	# calculate free energy per node 
	for n in nodes:
		log = open(n.reweighting_log_fn, "a") # using separate log-file
		def output(message):
			print(message)
			log.write(message+"\n")
			
		output("======= Starting node reweighting %s"%datetime.now())
		
		# get potential V and substract penalty potential
		energies = load_energy(n, options.e_bonded, options.e_nonbonded, custom_energy_terms)

		frame_weights = n.frameweights
		phi_values = n.phi_values
		phi_weighted_energies = energies + get_phi_potential(n.trajectory, n)

		# calculate mean V and standard deviation
		n.obs.mean_V = np.average(phi_weighted_energies, weights=frame_weights)
		n.tmp['weight'] = 1.0
		n.obs.std_V = np.sqrt(np.average(np.square(phi_weighted_energies - n.obs.mean_V), weights=frame_weights))
			
		# number of presampling points in node i => free energy at high temperature
		n.tmp['presamp_weight'] = np.sum(get_phi(presampling_internals, n))
		n.tmp['presamp_A']= -1/beta_presamp * np.log(n.tmp['presamp_weight'])
			
		# estimate global optimum potential energy
		factor= 1.0
		n.tmp['opt_pot_energy']= n.obs.mean_V - 3.0 * factor * n.obs.std_V
			
		# compute free energy and entropy at sampling temperature
		n.obs.S = 0.0 #TODO can we get separate entropy from the term below?
		n.obs.A = (beta_samp - beta_presamp) / beta_samp * n.tmp['opt_pot_energy'] + np.log(beta_samp / beta_presamp) * factor * n.obs.std_V + (beta_presamp / beta_samp) * n.tmp['presamp_A']
		if('refpoints' in n.obs):
			del n.obs['refpoints']

		log.close()

	nodes.sort(key = lambda n: n.obs.A) # sort in ascending order by free energy values
	for (n1, n2) in zip(nodes[1:], nodes[:-1]): # calculate and normalize weights
		n1.tmp['weight'] = np.exp(-nodes[0].pool.thermo_beta*( n1.obs.A - n2.obs.A )) * n2.tmp['weight']


#===============================================================================
def load_energy(node, e_bonded_type, e_nonbonded_type, custom_e_terms=None):
	
	if(e_bonded_type != "none"):
		# get bonded energy
		if(e_bonded_type == "run_standard"):
			edr_fn = "ener.edr"
		elif(e_bonded_type == "rerun_standard"):
			edr_fn = "rerun.edr"
		else:
			raise(Exception("Method unkown: "+e_bonded_type))

		e_bonded_terms = ["Bond", "Angle", "Proper-Dih.", "Ryckaert-Bell.", "Improper-Dih."]

		xvg_fn = mktemp(suffix=".xvg", dir=node.dir)
		cmd = ["g_energy", "-dp", "-f", node.dir+"/"+edr_fn, "-o", xvg_fn, "-sum"]

		print("Calling: "+(" ".join(cmd)))
		p = Popen(cmd, stdin=PIPE)
		p.communicate(input=("\n".join(e_bonded_terms)+"\n"))
		assert(p.wait() == 0)

		# skipping over "#"-comments at the beginning of xvg-file 
		e_bonded = np.loadtxt(xvg_fn, comments="@", usecols=(1,), skiprows=10) 
		os.remove(xvg_fn)
	else:
		e_bonded = np.zeros(node.trajectory.n_frames)

	if(e_nonbonded_type != "none"):
		# get non-bonded energy
		if(e_nonbonded_type in ("run_standard","run_moi","run_moi_sol_sr","run_moi_sol_lr","run_custom")):
			edr_fn = "ener.edr"
		elif(e_nonbonded_type in ("rerun_standard","rerun_moi","rerun_moi_sol_sr","rerun_moi_sol_lr","rerun_custom")):
			edr_fn = "rerun.edr"
		else:
			raise(Exception("Method unkown: "+e_nonbonded_type))

		if(e_nonbonded_type in ("run_standard", "rerun_standard")):
			e_nonbonded_terms = ["LJ-14", "Coulomb-14", "LJ-(SR)", "LJ-(LR)", "Disper.-corr.", "Coulomb-(SR)", "Coul.-recip."]

		if(e_nonbonded_type in ("run_moi", "rerun_moi")):
			e_nonbonded_terms = ["Coul-SR:MOI-MOI", "LJ-SR:MOI-MOI", "LJ-LR:MOI-MOI", "Coul-14:MOI-MOI", "LJ-14:MOI-MOI"]

		if(e_nonbonded_type in ("run_moi_sol_sr", "rerun_moi_sol_sr")):
			e_nonbonded_terms = ["Coul-SR:MOI-MOI", "LJ-SR:MOI-MOI", "LJ-LR:MOI-MOI", "Coul-14:MOI-MOI", "LJ-14:MOI-MOI", "Coul-SR:MOI-SOL", "LJ-SR:MOI-SOL"]

		if(e_nonbonded_type in ("run_moi_sol_lr", "rerun_moi_sol_lr")):
			e_nonbonded_terms = ["Coul-SR:MOI-MOI", "LJ-SR:MOI-MOI", "LJ-LR:MOI-MOI", "Coul-14:MOI-MOI", "LJ-14:MOI-MOI", "Coul-SR:MOI-SOL", "LJ-SR:MOI-SOL", "LJ-LR:MOI-SOL"]

		if(e_nonbonded_type in ("run_custom", "rerun_custom")):
			assert(custom_e_terms)
			e_nonbonded_terms = custom_e_terms
	
		xvg_fn = mktemp(suffix=".xvg", dir=node.dir)
		cmd = ["g_energy", "-dp", "-f", node.dir+"/"+edr_fn, "-o", xvg_fn, "-sum"]

		print("Calling: "+(" ".join(cmd)))
		p = Popen(cmd, stdin=PIPE)
		p.communicate(input=("\n".join(e_nonbonded_terms)+"\n"))
		assert(p.wait() == 0)
	
		# skipping over "#"-comments at the beginning of xvg-file 
		e_nonbonded = np.loadtxt(xvg_fn, comments="@", usecols=(1,), skiprows=10) 
		os.remove(xvg_fn)
	else:
		e_nonbonded = np.zeros(node.trajectory.n_frames)

	assert(len(e_bonded) == len(e_nonbonded) == node.trajectory.n_frames)

	return(e_bonded+e_nonbonded)


#===============================================================================
def check_restraint_energy(node):
	""" Uses U{g_energy <http://www.gromacs.org/Documentation/Gromacs_Utilities/g_energy>}
		to read the distance- and dihedral-restraint energies
		used by gromacs	for every frame of the node's trajectory and compares them
		with our own values, which are calulated in L{ZIBMolPy.restraint}.
		This is a safety measure to ensure that L{ZIBMolPy.restraint} is consistent with gromacs."""
		
	#TODO: move next two lines into Node? 
	has_dih_restraints = any([isinstance(r, DihedralRestraint) for r in node.restraints])
	has_dis_restraints = any([isinstance(r, DistanceRestraint) for r in node.restraints])
	
	# Caution: g_energy ignores the given order of energy_terms and instead uses its own  
	energy_terms = []
	if(has_dis_restraints):
		#energy_terms += ["Dis.-Rest."]
		energy_terms += ["Restraint-Pot."]
	if(has_dih_restraints):
		energy_terms += ["Dih.-Rest."]
	
	#xvg_fn = mktemp(suffix=".xvg", dir=node.dir)
	xvg_fn = mktemp(suffix=".xvg")
	cmd = ["g_energy", "-dp", "-f", node.dir+"/ener.edr", "-o", xvg_fn]
	print("Calling: "+(" ".join(cmd)))
	p = Popen(cmd, stdin=PIPE)
	p.communicate(input=("\n".join(energy_terms)+"\n"))
	assert(p.wait() == 0)
	
	# skipping over "#"-comments at the beginning of xvg-file 
	energies = np.loadtxt(xvg_fn, comments="@", skiprows=10)
	os.remove(xvg_fn)
	
	assert(energies.shape[0] == node.trajectory.n_frames)
	assert(energies.shape[1] == len(energy_terms)+1)
	
	dih_penalty = np.zeros(node.trajectory.n_frames)
	dis_penalty = np.zeros(node.trajectory.n_frames)
	
	for i, r in enumerate(node.restraints):
		c = node.pool.converter[i]
		p = r.energy(node.trajectory.getcoord(i))
		
		if(isinstance(r, DihedralRestraint)):
			dih_penalty += p
		elif(isinstance(r, DistanceRestraint)):
			dis_penalty += p
		else:
			warn("Unkown Restraint-type: "+str(r))

	dih_penalty_gmx = np.zeros(node.trajectory.n_frames)
	dis_penalty_gmx = np.zeros(node.trajectory.n_frames)
	
	if(has_dih_restraints):
		i = energy_terms.index("Dih.-Rest.") + 1 # index 0 = time of frame
		dih_penalty_gmx = energies[:,i]
		dih_diffs = np.abs(dih_penalty - dih_penalty_gmx)
		max_diff = np.argmax(dih_diffs)
		dih_diff = dih_diffs[max_diff]
		bad_diff = max(0.006*energies[max_diff,i], 0.006)

		print "dih_diff: ", dih_diff
		assert(dih_diff < bad_diff)  #TODO: is this reasonable? deviations tend to get bigger with absolute energy value, so I think yes
		# TODO compare if we get the same dihedral angles from g_angle as we get from our internals
		
	if(has_dis_restraints):
		#i = energy_terms.index("Dis.-Rest.") + 1 # index 0 = time of frame
		i = energy_terms.index("Restraint-Pot.") + 1 # index 0 = time of frame
		dis_penalty_gmx = energies[:,i]
		dis_diff = np.max(np.abs(dis_penalty - dis_penalty_gmx))
		print "dis_diff: ", dis_diff
		assert(dis_diff < 1e-3)

	return( dih_penalty_gmx + dis_penalty_gmx ) # values are returned for optional plotting


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

