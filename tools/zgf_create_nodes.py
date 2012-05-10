#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the second step of ZIBgridfree.}

	This tool will generate a discretization of conformational space specified by certain internal coordinates from a supplied ZIBgridfree sampling node. If the node pool is empty, the root node (i. e. the presampling) will be used in order to generate an initial discretization. Later on, new nodes can be created from arbitrary nodes in the node pool: L{zgf_create_nodes} is also called from L{zgf_refine}. 

	Radial basis functions are used to form a (more or less) soft partitioning of the conformational space. The function S{Phi}_i(q) (taking values between zero and one) gives the membership of configuration q to basis function i. The potential modifications representing the basis functions during the sampling are approximated by standard Gromacs restraint potentials. 

	You should use L{zgf_browser} to check if you are happy with the discretization (coverage of conformational space, i. e. the number of nodes), and the quality of the S{Phi} function fit.

	B{The next step is L{zgf_setup_nodes}.}

How it works
============
	At the command line, type::
		$ zgf_create_nodes [options]

Discretization parameters
=========================
  - B{S{alpha} (alpha)} specifies the stiffness of the discretization: Larger S{alpha} values mean harder basis functions and less overlap. S{alpha} is either specified directly by the user or calculated via S{theta}. In general, S{alpha} will increase with the number of nodes, as with increasing number of nodes, each individual node has to cover less conformational space. Under normal conditions, higher S{alpha} values will lead to better convergence of the sampling.
	
  - B{S{theta} (theta)} is calculated as the average of the distances of each node to its nearest neighbor: High minimum distances will lead to soft basis funtions, small minimum distances will lead to hard basis functions.

	Note that very large S{alpha} values may lead to infinitely large force constants in the Gromacs restraint potentials. This indicates that the density of nodes (which is usually strongly related to the number of nodes) is too high.
	
	Currently, for averaging we use the B{median} of minimum distances. This will result in harder basis functions compared to when using the B{mean}, as exceptionally large minimum distances do not weigh in.
"""

from ZIBMolPy.internals import DihedralCoordinate, LinearCoordinate
from ZIBMolPy.phi import get_phi_contrib, get_phi_contrib_potential
from ZIBMolPy.algorithms import kmeans
from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.restraint import DihedralRestraint, DistanceRestraint
from ZIBMolPy.ui import userinput, Option, OptionsList
from ZIBMolPy.io.trr import TrrFile
import zgf_cleanup

import sys
import os
from pprint import pformat
from datetime import datetime
from tempfile import mktemp
from subprocess import Popen, PIPE
import numpy as np


# ZIBgridfree quasi-constant parameters
EPSILON2 = 1E-3

#PLATEAU_THRESHOLD = 0.001
PLATEAU_THRESHOLD = 0.02   # for phifit 'switch': smaller value = smaller plateaus
PLATEAU_BREAK = (np.pi/180)*2 # for phifit 'switch': change in dihedral that breaks plateau

# fun parameters
THE_BIG_NUMBER = 99999.0 # is measured in [Chuck]

#===============================================================================
options_desc = OptionsList([
	Option("N", "methodnodes", "choice", "method to determine nodes", choices=("kmeans","equidist", "all")),
	Option("A", "methodalphas", "choice", "method to determine alphas", choices=("theta", "user") ),
	Option("K", "numnodes", "int", "number of nodes to create", default=10, min_value=1),
	Option("E", "ext-max", "int", "max. number of extensions if not converged", default=5, min_value=0),
	Option("L", "ext-length", "int", "length per extension in ps", default=100, min_value=1),
	Option("P", "methodphifit", "choice", "method to determine phi fit", choices=("switch", "harmonic", "leastsq") ),
	Option("p", "parent-node", "node", "parent-node", default="root"),
	Option("w", "write-preview", "bool", "write frames of new nodes as pdb-trajectory", default=False),
	Option("l", "sampling-length", "int", "length of the normal sampling in ps", default=100, min_value=0),
	Option("s", "random-seed", "str", "seed for random number generator"),
	
])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc


def is_applicable():
	pool = Pool()
	return( len(pool)>0 )

#===============================================================================
# This method is also called from zgf_refine
def main(argv=None):
	if(argv==None): 
		argv = sys.argv
	options = options_desc.parse_args(argv)[0]
	
	print("Options:\n%s\n"%pformat(eval(str(options))))

	if(options.random_seed):
		# using numpy-random because python-random differs beetween 32 and 64 bit
		np.random.seed(hash(options.random_seed))
	
	pool = Pool()
	old_pool_size = len(pool)
	print "pool", pool
	
	if(options.parent_node == "root"):
		parent = pool.root
	else:
		found = [n for n in pool if n.name == options.parent_node]
		assert(len(found) == 1)
		parent = found[0]
	
	
	print "### Generate nodes: %s ###" % options.methodnodes
	if(options.methodnodes == "kmeans"):
		chosen_idx = mknodes_kmeans(parent, options.numnodes)
	elif(options.methodnodes == "equidist"):
		chosen_idx = mknodes_equidist(parent, options.numnodes)
	elif(options.methodnodes == "all"):
		chosen_idx = mknodes_all(parent)
	else:
		raise(Exception("Method unknown: "+options.methodnodes))

	chosen_idx.sort() # makes preview-trajectory easier to understand 
	if(options.write_preview):
		write_node_preview(pool, parent, chosen_idx)
	
	for i in chosen_idx:
		n = Node()
		n.parent_frame_num = i
		n.parent = parent
		n.state = "creating-a-partition" # will be set to "created" at end of script
		n.extensions_counter = 0
		n.extensions_max = options.ext_max
		n.extensions_length = options.ext_length
		n.sampling_length = options.sampling_length	
		n.internals = parent.trajectory.getframe(i)
		pool.append(n)
		
	print "\n### Obtain alpha: %s ###" % options.methodalphas
	old_alpha = pool.alpha
	if(options.methodalphas == "theta"):
		pool.alpha = calc_alpha_theta(pool)
	elif(options.methodalphas == "user"):
		pool.alpha = userinput("Please enter a value for alpha", "float")
	else:
		raise(Exception("Method unknown: "+options.methodalphas))
	
	pool.history.append({'refined_node': (parent.name, parent.state), 'size':old_pool_size, 'alpha':old_alpha, 'timestamp':datetime.now()})
	
	pool.save() # alpha might have changed
	
	print "\n### Obtain phi fit: %s ###" % options.methodphifit
	if(options.methodphifit == "harmonic"):
		do_phifit_harmonic(pool)
	elif(options.methodphifit == "switch"):
		do_phifit_switch(pool)
	elif(options.methodphifit == "leastsq"):
		do_phifit_leastsq(pool)
	else:
		raise(Exception("Method unkown: "+options.methodphifit))

	for n in pool.where("state == 'creating-a-partition'"):
		n.state = "created"
		n.save()
		print "saving " +str(n)
		
	zgf_cleanup.main()


#==========================================================================
def mknodes_kmeans(parent, numnodes):
	frames_int = parent.trajectory
	fixed_clusters = [n.internals for n in parent.children]
	means = kmeans(frames_int, numnodes, fixed_clusters=fixed_clusters)
	# k-means finished - examine results
	chosen_idx = [ np.argmin( (frames_int-m).norm2() ) for m in means ]	
	
	print "\nDiscretization overview:"
	frames_chosen = frames_int.getframes(chosen_idx)
	print "- Variance per int of presampling trajectory:"
	print frames_int.var().array
	print "- Variance per int of chosen nodes:"
	print frames_chosen.var().array
	print "- Relative variance per int of chosen nodes:"
	print (frames_chosen.var() / frames_int.var()).array
	
	return(chosen_idx)

#==========================================================================
def mknodes_equidist(parent, numnodes):

	if(parent.state == "refined" and len(parent.pool) > 1):
		sys.exit("Error. Cannot refine a refined node with method 'equidist'.")

	frames_int = parent.trajectory
	initial_node = 0
	# sorted distances (increasing order) from initial node to all frames
	diffs = (frames_int - frames_int.getframe(initial_node)).norm()
	sorted_diffs_idx = np.argsort( diffs )
	
	def identify_nodes(frames_int, initial_node, theta, sorted_diffs, sorted_diffs_idx):		
		chosen_idx = []

		while True:
			node = sorted_diffs_idx[0]
			chosen_idx.append(node)

			dist2initial = (frames_int.getframe(initial_node) - frames_int.getframe(node)).norm()
			dump = np.where((sorted_diffs - dist2initial) < theta)[0]

			# crop diffs and indices
			sorted_diffs = sorted_diffs[len(dump):]
			sorted_diffs_idx = sorted_diffs_idx[len(dump):]	
		
			if len(sorted_diffs) == 0:
				break

		return chosen_idx

	# binary search: tune theta so that 'numnodes' nodes are chosen
	theta_low = 0.0
	theta_high = np.max(diffs)
	theta = theta_high/2.0 # initial guess

	while True:
		chosen_idx = identify_nodes(frames_int, initial_node, theta, diffs[sorted_diffs_idx][:], sorted_diffs_idx[:])
		print "theta: %f, theta_high: %f, theta_low: %f, current numnodes: %d"%(theta, theta_high, theta_low, len(chosen_idx))

		if len(chosen_idx) < numnodes:
			theta_high = theta
		else:
			theta_low = theta
		if (len(chosen_idx) == numnodes) or (theta_high - theta_low < 2E-6):
			break

		theta = (theta_low + theta_high)/2.0

	frames_chosen = frames_int.getframes(chosen_idx)
	
	print "\nDiscretization overview:"
	print "- Variance per int of presampling trajectory:"
	print frames_int.var().array
	print "- Variance per int of chosen nodes:"
	print frames_chosen.var().array
	print "- Relative variance per int of chosen nodes:"
	print (frames_chosen.var() / frames_int.var()).array
	
	return(chosen_idx)
	

#==========================================================================
def mknodes_all(parent):
	frames_int = parent.trajectory
	print("loaded trr-file with %d frames"%len(frames_int))
	return(range(len(frames_int)))
	

	
#==========================================================================
def calc_alpha_theta(pool):
	# calculate theta and alpha
	active_nodes = pool.where("isa_partition")
	theta = calc_theta(active_nodes)
	assert(theta[1] > 0.00001) #TODO: apparently fails sometimes
	alpha = -np.log( EPSILON2/len(active_nodes) ) / (3.0*theta[1]*theta[1]) # using theta_median
	print("theta_mean: %f, theta_median: %f\nalpha (from theta_median): %f" % (theta[0], theta[1], alpha))
	return(alpha)


#==========================================================================
def calc_theta(active_nodes):
	# compute theta = average of the distances from each node to its nearest neighbor
	min_dists = []
	for n in active_nodes:
		diffs = (active_nodes.internals - n.internals).norm()
		nj = np.argsort(diffs)[1] # taking the second result (not the node itself)
		min_dists.append(diffs[nj])
	# return theta twice: 1. calculated as mean, 2. calculated as median of min_dists
	return [np.mean(min_dists), np.median(min_dists)]



#===============================================================================
def get_force_constant(node):
	#gamma = node.gammas[ coordinate.index ]
	#k = gamma * node.alpha / get_beta(node.temperature) # in kJ/(mol rad^2)
	#k = node.alpha / get_beta(node.temperature) # in kJ/(mol rad^2)
	#k = node.pool.alpha / get_beta(node.pool.temperature) # in kJ/(mol rad^2)
	k = node.pool.alpha / node.pool.thermo_beta # in kJ/(mol rad^2)
	#TODO: keine node-dependence
	#TODO: evtl in Pool auslagern
	return(k)


#==========================================================================
def do_phifit_leastsq(pool):
	from scipy.optimize import leastsq
	
	new_nodes = pool.where("state == 'creating-a-partition'")
		
	for n in new_nodes:
		n.restraints = []
		for c in pool.converter:
			k0 = get_force_constant(n)
			pos0 = n.internals.getcoord(c)
			all_values = pool.coord_range(c)
					
			if(isinstance(c, DihedralCoordinate)):
				p0 = [pos0, 2, k0] # Initial guess for parameters
				restraint_class = DihedralRestraint
				
			elif(isinstance(c, LinearCoordinate)):
				p0 = [pos0, pos0, 0.1, k0]  # Initial guess for parameters
				restraint_class = DistanceRestraint
			else:
				raise(Exception("Unkown Coordinate-Type"))
			
			#phi_values = get_phi_contrib(all_values, n, active_nodes, c)
			phi_values = get_phi_contrib(all_values, n, c)
			phi_potential = get_phi_contrib_potential(all_values, n, c)
			node_value = n.internals.getcoord(c)
			node_index = np.argmin(np.square(c.sub(all_values, node_value)))
			#phi_potential -= phi_potential[node_index] # gauge: set phi_potential[node] = 0

			# contiguous function = smooth penalty-surface 
			def heaviside(x): return 1/(1 + np.exp(-500*x))
			phi_on = heaviside(phi_values - 0.01)
			
			def errfunc(p):
				p[1:] = [ max(i, 0) for i in p[1:] ] #all but p[0] should be positiv
				
				restraint = restraint_class.calc_energy(p, all_values)
				#penalties = (phi_values+0.01)*(phi_potential - restraint) # weich
				#penalties = (phi_values+0.001)*(phi_potential - restraint) # also weich
				#penalties = (phi_values+0.1)*(phi_potential - restraint) # hard
				diff = restraint - phi_potential
				restr_too_high = heaviside(diff)
				penalties = np.abs(diff)
				penalties += 15*phi_on*restr_too_high*np.abs(diff)
				penalties += 10*abs(restraint[node_index])
				return(penalties)
			
			p1, success = leastsq(errfunc, p0)
			assert(success)
			print("p1 = "+str(p1))
			new_restraint = restraint_class(c.atoms, *p1)
			n.restraints.append(new_restraint)
			
	
#==========================================================================
def do_phifit_harmonic(pool):
	new_nodes = pool.where("state == 'creating-a-partition'")
	for n in new_nodes:
		n.restraints = []
		for c in pool.converter:
			k = get_force_constant(n)
			if(isinstance(c, DihedralCoordinate)):
				phi0 = n.internals.getcoord(c)
				dphi = 0.0
				n.restraints.append( DihedralRestraint(c.atoms, phi0, dphi, k) )
				
			elif(isinstance(c, LinearCoordinate)):
				r0 = r1 = n.internals.getcoord(c)
				r2 = THE_BIG_NUMBER # = using only harmonic part of restraint
				n.restraints.append( DistanceRestraint(c.atoms, r0, r1, r2, k) )
			
			else:
				raise(Exception("Unkown Coordinate-Type"))
#==========================================================================
def do_phifit_switch(pool):
	new_nodes = pool.where("state == 'creating-a-partition'")
	
	for n in new_nodes:
		n.restraints = []
		for c in pool.converter:
			# analyze phi for this coordinate
			all_values = pool.coord_range(c, lin_slack=False)
			all_phi_pot = get_phi_contrib_potential(all_values, n, c)

			norm_phi_pot = abs(all_phi_pot - np.min(all_phi_pot)) # we normalize all_phi_pot to a minimum of zero
			max_phi_pot = np.max(norm_phi_pot)
			argmax_phi_pot = np.argmax(norm_phi_pot)

			plateau = np.where( norm_phi_pot < (max_phi_pot*PLATEAU_THRESHOLD) )[0]
			node_value = n.internals.getcoord(c)
			
			if isinstance(c, DihedralCoordinate):
				if len(plateau) == 0: # constant phi: no restraint
					phi0 = dphi = k = 0.0
					print "Constant phi (no restraint) for coordinate %s of node %s." % (c, n.name)
				else:
					dih_plateau = np.take( all_values, plateau )

					dih_plateau_left = dih_plateau[0] # 1st edge of plateau
					dih_plateau_right = dih_plateau[len(plateau)-1] # 2nd edge of plateau

					#TODO idea from Ole: transfer plateau_left to -pi first, calculate everything, then transfer back... could get rid of the part below
					if (dih_plateau_left == -np.pi) and (dih_plateau_right == np.pi): # if plateau transcends +180 degrees, adjust edges
						for i in range(1, len(dih_plateau)):
							if abs(abs(dih_plateau[i])-abs(dih_plateau[i-1])) >= PLATEAU_BREAK:
								dih_plateau_right = dih_plateau[i-1]
								dih_plateau_left = dih_plateau[i]
								break

					diff_node2right = abs(DihedralCoordinate.sub(dih_plateau_right, node_value))
					diff_node2left = abs(DihedralCoordinate.sub(dih_plateau_left, node_value))
					plateau_size = np.radians(len(dih_plateau))
	
					if (diff_node2right > plateau_size) or (diff_node2left > plateau_size): # node_value not on plateau
						#print "extension necessary"
						if diff_node2right < diff_node2left:
							old_dih_plateau_right = dih_plateau_right
							#print "old dih_plateau_right: %f" % old_dih_plateau_right
							dih_plateau_right = node_value # extend plateau to the right
							#print "new dih_plateau_right: %f" % dih_plateau_right
							plateau_size_diff = abs(DihedralCoordinate.sub(old_dih_plateau_right, dih_plateau_right))
						else:
							old_dih_plateau_left = dih_plateau_left
							#print "old dih_plateau_left: %f" % old_dih_plateau_left
							dih_plateau_left = node_value # extend plateau to the left
							#print "new dih_plateau_left: %f" % dih_plateau_left
							plateau_size_diff = abs(DihedralCoordinate.sub(old_dih_plateau_left, dih_plateau_left))
						#print "old plateau size: %f" % np.degrees(plateau_size)
						plateau_size += plateau_size_diff
						#print "new plateau size: %f" % np.degrees(plateau_size) 
						#print "plateau_size_diff: %f" % np.degrees(plateau_size_diff) 
						
					dphi = plateau_size/2
					phi0 = DihedralCoordinate.sub(dih_plateau_right, dphi)
				
					# get k via Steigungsdreieck
					dih_phi_pot_max = all_values[argmax_phi_pot]

					flank1 = np.abs( dih_phi_pot_max - dih_plateau_left )
					flank1 = np.minimum( flank1, 2*np.pi-flank1 )
					flank2 = np.abs( dih_phi_pot_max - dih_plateau_right )
					flank2 = np.minimum( flank2, 2*np.pi-flank2 )
					k = max_phi_pot/max(flank1, flank2)
				
				n.restraints.append( DihedralRestraint(c.atoms, phi0, dphi, k) )

			elif isinstance(c, LinearCoordinate):
				if len(plateau) == 0: # constant phi: no restraint
					r0 = r1 = r2 = k = 0.0
					print "Constant phi (no restraint) for coordinate %s of node %s." % (c, n.name)
				else:
					lin_plateau = np.take( all_values, plateau )
					
					r0 = lin_plateau[0] # 1st edge of plateau
					r1 = lin_plateau[len(plateau)-1] # 2nd edge of plateau
					r2 = THE_BIG_NUMBER # = using only harmonic part of restraint
					
					# node_value not on plateau
					if node_value > r1:
						r1 = node_value # extend plateau to the right
					elif node_value < r0:	
						r0 = node_value # extend plateau to the left
				
					# get k via Steigungsdreieck
					lin_phi_pot_max = all_values[argmax_phi_pot]

					flank1 = np.abs(lin_phi_pot_max - r0)
					flank2 = np.abs(lin_phi_pot_max - r1)
					k = max_phi_pot/max(flank1, flank2)

				n.restraints.append( DistanceRestraint(c.atoms, r0, r1, r2, k) )
			else:
				raise(Exception("Unkown Coordinate-Type"))

#===============================================================================
def write_node_preview(pool, parent, chosen_idx):
	assert(chosen_idx == sorted(chosen_idx))
	
	print "chosen_idx", chosen_idx
	trr_out_tmp_fn = mktemp(suffix='.trr')
	trr_out_tmp = open(trr_out_tmp_fn, "wb")
	
	trr_in = TrrFile(parent.trr_fn)
	curr_frame = trr_in.first_frame
	for i in chosen_idx:
		for dummy in range(i - curr_frame.number):
			curr_frame = curr_frame.next()
		assert(curr_frame.number == i)
		trr_out_tmp.write(curr_frame.raw_data)
	trr_in.close()
	trr_out_tmp.close()
	
	node_preview_fn = "node_preview_from_" + parent.name + ".pdb"	
	cmd = ["trjconv", "-f", trr_out_tmp_fn, "-o", node_preview_fn, "-s", parent.pdb_fn, "-n", pool.ndx_fn] 
	p = Popen(cmd, stdin=PIPE)
	p.communicate(input="MOI\n")
	assert(p.wait() == 0)
	os.remove(trr_out_tmp_fn)

	print "Node preview (MOI only) written to file: %s" % node_preview_fn		

#==========================================================================
if(__name__=="__main__"):
	main()

#EOF

