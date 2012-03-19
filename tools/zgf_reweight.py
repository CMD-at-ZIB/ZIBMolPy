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
"""

from ZIBMolPy.constants import AVOGADRO, BOLTZMANN
from ZIBMolPy.restraint import DihedralRestraint, DistanceRestraint
from ZIBMolPy.ui import Option, OptionsList
from ZIBMolPy.utils import get_phi
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


CRITICAL_FRAME_WEIGHT = 5.0


options_desc = OptionsList([
	Option("s", "sol-energy", "bool", "include SOL energy contribution", default=False),
	Option("c", "ignore-convergence", "bool", "reweight despite not-converged", default=False),
	Option("m", "method", "choice", "reweighting method", choices=("entropy", "direct", "presampling")),
	Option("t", "presamp-temp", "float", "presampling temp", default=1000),
	Option("r", "save-refpoints", "bool", "save refpoints in observables", default=False),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return( len(pool) > 1  and len(pool.where("is_sampled")) == len(pool) )




#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	zgf_cleanup.main()
	
	pool = Pool()

	#not_reweightable = "state not in ('refined','converged')"
	not_reweightable = "isa_partition and state!='converged'"
	if options.ignore_convergence:
		not_reweightable = "isa_partition and state not in ('converged','not-converged')"

	if pool.where(not_reweightable):
		print "Pool can not be reweighted due to the following nodes:"		
		for bad_guy in pool.where(not_reweightable):
			print "Node %s with state %s."%(bad_guy.name, bad_guy.state)
		sys.exit("Aborting.")
		
	active_nodes = pool.where("isa_partition")
	assert(len(active_nodes) == len(active_nodes.multilock())) # make sure we lock ALL nodes

	for n in active_nodes:
		check_restraint_energy(n)

	# find out about number of energygrps
	mdp_file = gromacs.read_mdp_file(pool.mdp_fn)
	energygrps = [str(egrp) for egrp in re.findall('[\S]+', mdp_file["energygrps"])]
	moi_energies = True	
	if len(energygrps) < 2:
		moi_energies = False # Gromacs energies are named differently when there are less than two energygrps :(

	if(options.method == "direct"): 
		reweight_direct(active_nodes, moi_energies, options.sol_energy, options.save_refpoints)
	elif(options.method == "entropy"):
		reweight_entropy(active_nodes, moi_energies, options.sol_energy, options.save_refpoints)
	elif(options.method == "presampling"):
		reweight_presampling(active_nodes, options.presamp_temp, moi_energies, options.sol_energy)
	else:
		raise(Exception("Method unkown: "+options.method))
	
	weight_sum = np.sum([n.tmp['weight'] for n in active_nodes])
	
	print "Thermodynamic weights calculated by method '%s' (sol-energy=%s):"%(options.method, options.sol_energy)
	for n in active_nodes:
		n.obs.weight_direct = n.tmp['weight'] / weight_sum
		if(options.method == "direct"):
			print("  %s with mean_V: %f [kJ/mol], %d refpoints and weight: %f" % (n.name, n.obs.mean_V, n.tmp['n_refpoints'], n.obs.weight_direct))
		else:
			print("  %s with A: %f [kJ/mol] and weight: %f" % (n.name, n.obs.A, n.obs.weight_direct))

	for n in active_nodes:
		n.save()

	active_nodes.unlock()


#===============================================================================
def reweight_direct(nodes, moi_energies, sol_energy, save_ref=False):
	print "Direct free energy reweighting: see Klimm, Bujotzek, Weber 2011"
	
	beta = nodes[0].pool.thermo_beta
	
	for n in nodes:
		# get potential V and substract penalty potential
		energies = load_energies(n, with_penalty=False, with_sol=sol_energy, with_moi_energies=moi_energies)

		frame_weights = n.frameweights
		phi_values = n.phi_values
		#phi_weighted_energies = energies - (1/beta)*np.log(phi_values)
		#phi_weighted_energies = energies - (1/get_beta(nodes[0].pool.temperature))*np.log(phi_values+1.0e-40) # avoid log(0.0) TODO Marcus-check
		phi_weighted_energies = energies - (1/nodes[0].pool.thermo_beta)*np.log(phi_values+1.0e-40) # avoid log(0.0) TODO Marcus-check

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
		if(save_ref):
			n.obs.refpoints = refpoints
		
		log.close()


#===============================================================================
def reweight_entropy(nodes, moi_energies, sol_energy, save_ref=False):
	print "Entropy reweighting: see Klimm, Bujotzek, Weber 2011"
	
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
		energies = load_energies(n, with_penalty=False, with_sol=sol_energy, with_moi_energies=moi_energies)

		frame_weights = n.frameweights
		phi_values = n.phi_values

		#phi_weighted_energies = energies - (1/get_beta(nodes[0].pool.temperature))*np.log(phi_values)
		#phi_weighted_energies = energies - (1/get_beta(nodes[0].pool.temperature))*np.log(phi_values+1.0e-40) # avoid log(0.0) TODO Marcus-check
		phi_weighted_energies = energies - (1/nodes[0].pool.thermo_beta)*np.log(phi_values+1.0e-40) # avoid log(0.0) TODO Marcus-check
	
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
		if(save_ref):
			n.obs.refpoints = refpoints

		log.close()

	nodes.sort(key = lambda n: n.obs.A) # sort in ascending order by free energy values		
	for (n1, n2) in zip(nodes[1:], nodes[:-1]): # calculate and normalize weights
		#n1.tmp['weight'] = np.exp(-get_beta(nodes[0].pool.temperature)*( n1.obs.A - n2.obs.A )) * n2.tmp['weight']
		n1.tmp['weight'] = np.exp(-nodes[0].pool.thermo_beta*( n1.obs.A - n2.obs.A )) * n2.tmp['weight']
	

#===============================================================================
def reweight_presampling(nodes, presamp_temp, moi_energies, sol_energy):
	print "Presampling analysis reweighting: see formula 18 in Fackeldey, Durmaz, Weber 2011"
	
	# presampling data
	presampling_internals = nodes[0].pool.root.trajectory # alternatively pool[0].trajectory
	
	# presampling and sampling beta
	#beta_samp = get_beta(nodes[0].pool.temperature)
	beta_samp = nodes[0].pool.thermo_beta
	beta_presamp = 1/(presamp_temp*BOLTZMANN*AVOGADRO)
		
	# calculate free energy per node 
	for n in nodes:
		log = open(n.reweighting_log_fn, "a") # using separate log-file
		def output(message):
			print(message)
			log.write(message+"\n")
			
		output("======= Starting node reweighting %s"%datetime.now())
		
		# get potential V and substract penalty potential
		energies = load_energies(n, with_penalty=False, with_sol=sol_energy, with_moi_energies=moi_energies)

		frame_weights = n.frameweights
		phi_values = n.phi_values
		#phi_weighted_energies = energies - (1/beta_samp)*np.log(phi_values)
		phi_weighted_energies = energies - (1/nodes[0].pool.thermo_beta)*np.log(phi_values+1.0e-40) # avoid log(0.0) TODO Marcus-check

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
		#n1.tmp['weight'] = np.exp(-get_beta(nodes[0].pool.temperature)*( n1.obs.A - n2.obs.A )) * n2.tmp['weight']
		n1.tmp['weight'] = np.exp(-nodes[0].pool.thermo_beta*( n1.obs.A - n2.obs.A )) * n2.tmp['weight']
		


#===============================================================================
def load_energies(node, with_penalty=True, with_sol=True, with_moi_energies=True):
	# bonded
	# TODO watch out, bonded terms may become problem for more than one molecule in the system
	# TODO we will need "mdrun -rerun" here to get the potential for MOI in complexes/waterboxes
	energy_terms = ["Bond", "Angle", "Proper-Dih.", "Ryckaert-Bell.", "Improper-Dih."]
	# non-bonded
	if(with_moi_energies):
		energy_terms += ["Coul-SR:MOI-MOI", "LJ-SR:MOI-MOI", "LJ-LR:MOI-MOI", "Coul-14:MOI-MOI", "LJ-14:MOI-MOI"]
	else:
		energy_terms += ["Coulomb-(SR)", "LJ-(SR)", "Coulomb-14", "LJ-14"]
	if(with_sol):
		energy_terms += ["Coul-SR:MOI-SOL", "LJ-SR:MOI-SOL", "LJ-LR:MOI-SOL"]
	
	# restraint
	if(with_penalty):
		if(any([isinstance(r, DihedralRestraint) for r in node.restraints])):
			energy_terms += ["Dih.-Rest."]
		if(any([isinstance(r, DistanceRestraint) for r in node.restraints])):
			energy_terms += ["Dis.-Rest."]
	
	xvg_fn = mktemp(suffix=".xvg", dir=node.dir)
	cmd = ["g_energy", "-dp", "-f", node.dir+"/ener.edr", "-o", xvg_fn, "-sum"]

	print("Calling: "+(" ".join(cmd)))
	p = Popen(cmd, stdin=PIPE)
	p.communicate(input=("\n".join(energy_terms)+"\n"))
	assert(p.wait() == 0)
	
	# skipping over "#"-comments at the beginning of xvg-file 
	energies = np.loadtxt(xvg_fn, comments="@", usecols=(1,), skiprows=10) 
	os.remove(xvg_fn)

	if(len(energies) != node.trajectory.n_frames):
		raise(Exception("Number of frames in %s (%d) unequal to number of energy values in %s\ener.edr (%s).\n"%(node.trr_fn, node.trajectory.n_frames, node.dir, len(energies)))) 

	return(energies)

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
	
	xvg_fn = mktemp(suffix=".xvg", dir=node.dir)
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
		p = r.energy(node.trajectory.getcoord(i))
		if(isinstance(r, DihedralRestraint)):
			dih_penalty += p
		elif(isinstance(r, DistanceRestraint)):
			dis_penalty += p
		else:
			warn("Unkown Restraint-type: "+str(r))
	
	if(has_dih_restraints):
		i = energy_terms.index("Dih.-Rest.") + 1 # index 0 = time of frame
	
		dih_diffs = np.abs(dih_penalty - energies[:,i])
		max_diff = np.argmax(dih_diffs)
		dih_diff = dih_diffs[max_diff]
		bad_diff = max(0.006*energies[max_diff,i], 0.006)

		print "dih_diff: ", dih_diff
		assert(dih_diff < bad_diff)  #TODO: is this reasonable? deviations tend to get bigger with absolute energy value, so I think yes
		# TODO compare if we get the same dihedral angles from g_angle as we get from our internals
		
	if(has_dis_restraints):
		#i = energy_terms.index("Dis.-Rest.") + 1 # index 0 = time of frame
		i = energy_terms.index("Restraint-Pot.") + 1 # index 0 = time of frame
		dis_diff = np.max(np.abs(dis_penalty - energies[:,i]))
		print "dis_diff: ", dis_diff
		#assert(dis_diff < 1e-6) #TODO: set reasonable threshold
		assert(dis_diff < 1e-4) #TODO: set reasonable threshold

#===============================================================================
if(__name__ == "__main__"):
	main()


#EOF

