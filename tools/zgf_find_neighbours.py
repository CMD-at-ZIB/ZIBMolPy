#!/usr/bin/python
# -*- coding: utf-8 -*-


from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import userinput, Option, OptionsList

import sys

import numpy as np



# upper threshold is threshold_default value has to be between 0.0 and 1.0
# lower threshold is given as 1-upper_threshold
threshold_default=0.6

#how many transition sampling points per node ?
default_amount_transition_nodes = 1


options_desc = OptionsList([
	
	Option("n", "num-neighbours", "int", "number of neighbours per node", default=1, min_value=1),
	
	])

#===============================================================================
def main():

	options = options_desc.parse_args(sys.argv)[0]

	default_amount_transition_nodes = options.num_neighbours

	pool = Pool()
	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']
	node_names = npz_file['node_names']
	n_clusters = npz_file['n_clusters']
	active_nodes = [Node(nn) for nn in node_names]
	pool = Pool()

	
	for node_index in range(0,len(active_nodes)):
			trajectory= active_nodes[node_index].trajectory
			
			print "			             ----				"
			print "			          ----------				"
			print "			     --------------------			"
			print "			 printing neighbours for node " + str(node_index)
			print "			     --------------------			"
			print "			           ---------				"		
			print "			              ---				"

			neighbours=get_neighbours(node_index,trajectory,active_nodes)

			
			#create transition point for node_index
			for element in neighbours:
				print element
				n = Node()
				n.parent_frame_num = element[1]
				n.parent = active_nodes[node_index]
				n.state = "created"
				n.extensions_counter = 0
				n.extensions_max = 0
				n.extensions_length = 0
				n.sampling_length = n.parent.sampling_length * 3
				n.internals = trajectory.getframe(element[1])
				pool.append(n)
				n.save()
			print "-----"



def get_neighbours(current_node,trajectory,other_nodes):
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
	while len(neighbours)!=default_amount_transition_nodes and step_counter < 1000:
		if len(neighbours) > default_amount_transition_nodes:
			print "too many neighbours   - decrease upper_threshold:" +str(upper_threshold)
			mid = (upper_threshold + lower_threshold ) /2
			upper_threshold=  (upper_threshold + mid) / 2
			lower_threshold = 1 - upper_threshold
		
		if len(neighbours) < default_amount_transition_nodes:
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

	if len(neighbours) == default_amount_transition_nodes:
		print "FOUND " + str(len(neighbours)) + " NEIGHBOURS - WELL DONE"
	else:
		print "WARNING: FOUND " + str(len(neighbours)) + " NEIGHBOURS AFTER " + str(step_counter) +" STEPS INSTEAD OF " + str(default_amount_transition_nodes)

	return neighbours




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


