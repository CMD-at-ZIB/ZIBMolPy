#!/usr/bin/python
# -*- coding: utf-8 -*-

from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import Option, OptionsList

import zgf_setup_nodes
import zgf_grompp

import sys
import numpy as np

# upper threshold is threshold_default value has to be between 0.0 and 1.0
# lower threshold is given as 1-upper_threshold
threshold_default=0.6


options_desc = OptionsList([	
	Option("n", "num-neighbours", "int", "number of neighbours per node", default=1, min_value=1),	
	Option("l", "sampling-length", "int", "length of sampling per run in ps", default=100, min_value=0),
	Option("r", "num-runs", "int", "number of runs", default=5, min_value=0),
	Option("s", "save velocity", "bool", "save first and last velocity in trajectory", default=False),
	Option("o", "only-chi-nodes", "bool", "Select only nodes with high chi value", default=False),
	Option("u", "only-user-nodes", "bool", "Select only  user nodes", default=False)
	])

#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]

	pool = Pool()
	npz_file = np.load(pool.chi_mat_fn) #TODO why?
	chi_matrix = npz_file['matrix']
	node_names = npz_file['node_names']
	n_clusters = npz_file['n_clusters']
	active_nodes = [Node(nn) for nn in node_names]	# TODO make nicer

	if options.only_chi_nodes :
		# extract highest chi nodes
		arg_sort_cluster=np.argsort(chi_matrix,axis=0)

		epic_row = arg_sort_cluster[len(arg_sort_cluster)-1]
		new_active_nodes=[]
		new_internals=[]

		for i in range(0,len(epic_row)):
			new_active_nodes.append(active_nodes[epic_row[i]])
	
		active_nodes = new_active_nodes
		print "# CHI NODES #"
		for i in active_nodes:
			print i.internals.array

	if options.only_user_nodes :
		npz_choosen_file = np.load(pool.analysis_dir+"user_cluster.npz")
		active_nodes = npz_choosen_file['the_choosen_nodes']
		print active_nodes
		print "# USER NODES #"
		for i in active_nodes:
			print i.internals.array

	
	
	for node in active_nodes:   # TODO make nicer
		trajectory= node.trajectory
			
		print "			             ----				"
		print "			          ----------				"
		print "			     --------------------			"
		print "			 printing neighbours for node " + str(node)
		print "			     --------------------			"
		print "			           ---------				"		
		print "			              ---				"

		#neighbours=get_neighbours_steinzeit(node_index, trajectory, active_nodes, options.num_neighbours)
		neighbours=get_neighbours_steinzeit(node, trajectory, options.num_neighbours)
		
		print len(trajectory)
		#create transition point for node_index
		for frame_number in neighbours:
			print frame_number
			n = Node()
			n.parent_frame_num = frame_number
			n.parent = node
			n.state = "created"
			n.extensions_counter = 0
			n.extensions_max = options.num_runs
			n.extensions_length = options.sampling_length
			n.sampling_length = options.sampling_length
			n.internals = trajectory.getframe(frame_number)
			pool.append(n)
			n.save()
		print str(options.num_neighbours)+" neighbours found. This program is just absolutly awesome. Be happy that you can use it."
		print "-----"

	zgf_setup_nodes.main()
	zgf_grompp.main()

#===============================================================================
# get amount of neighbours 
def get_neighbours_steinzeit(current_node,trajectory, num_neighbours):
	total_length = len(trajectory)
	step_size = total_length / num_neighbours

	frame_number = 0
	neighbours=[]
	while frame_number< total_length:
		# floor returns an integer in float format
		# in python 3 it actually returns an integer
		# since we use pythen 2.x we need to fix it
		neighbours.append(np.int(np.floor(frame_number)))
		frame_number += step_size
	print neighbours
	return neighbours
	


#===============================================================================
def get_neighbours(current_node, trajectory, other_nodes, num_neigbours):
	# neighbours is a list of the type 
	#[ [neighbour_node1,neighbour_node2,...],[corr. timestep]] , [[neighbour_node1,neighbour_node2,...],[corr. timestep]] ... ]
	
	upper_threshold=threshold_default
	lower_threshold=1-threshold_default
	
	collection = [ get_phi(trajectory, n) for n in other_nodes ]

	#find neighbours
	neighbours=[find_transition_states(collection,i,current_node,lower_threshold,upper_threshold) 
			for i in range(0,len(trajectory)) if len(find_transition_states(collection,i,current_node,lower_threshold,upper_threshold))!=0]

	# change threshold and search for more neighbours until we found enough, or give up after 1000 steps
	step_counter = 0
	mid = 0
	while len(neighbours)!=num_neigbours and step_counter < 1000:
		if len(neighbours) > num_neigbours:
			print "too many neighbours   - decrease upper_threshold:" +str(upper_threshold)
			mid = (upper_threshold + lower_threshold ) /2
			upper_threshold=  (upper_threshold + mid) / 2
			lower_threshold = 1 - upper_threshold
		
		if len(neighbours) < num_neigbours:
			print "not enough neighbours - increase upper_threshold:" +str(upper_threshold)
			if mid==0:
				upper_threshold=  (upper_threshold + 1) / 2
				lower_threshold = (lower_threshold + 0) / 2
			else:
			# say u = upper_threshold_old and u'=upper_threshold_new 
			# we can reconstruct u by u' via  u = 2u' - mid
			# and obtain u_new = (u + u')/2
				mid_new = upper_threshold
				upper_threshold = ((2*upper_threshold -mid) + upper_threshold)/2
				lower_threshold = 1 - upper_threshold
				mid = mid_new



		step_counter = step_counter +1

		neighbours=[find_transition_states(collection,i,current_node,lower_threshold,upper_threshold) 
			for i in range(0,len(trajectory)) if len(find_transition_states(collection,i,current_node,lower_threshold,upper_threshold))!=0]

	if len(neighbours) == num_neigbours:
		print "FOUND " + str(len(neighbours)) + " NEIGHBOURS - WELL DONE"
	else:
		print "WARNING: FOUND " + str(len(neighbours)) + " NEIGHBOURS AFTER " + str(step_counter) +" STEPS INSTEAD OF " + str(num_neigbours)

	return neighbours


#===============================================================================
def find_transition_states(collection,frame_num,current_node,lower_threshold,upper_threshold):
	i=frame_num
	neighbours=[]
	# check if frame i belongs to current_node
	if collection[current_node][i]> lower_threshold and collection[current_node][i]<upper_threshold:
			for j in range(0,len(collection)):
				# check if this frame also belongs to an other node
				if collection[j][i]> lower_threshold and collection[j][i]<upper_threshold and current_node!=j:
					# if it does, save it as a neighbour
					neighbours.append(j)
	
	if (len(neighbours)!=0):
		return  [neighbours,frame_num]
	else:
		return []
	
	
#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

