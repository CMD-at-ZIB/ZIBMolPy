#!/usr/bin/python
# -*- coding: utf-8 -*-


from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import userinput, Option, OptionsList

import zgf_setup_nodes
import zgf_grompp

import sys

import numpy as np

options_desc = OptionsList([	
	Option("n", "coreset-power", "float", "concentration of coresets (Close to 0 means contains all phis , Close to 1 means contains almost np phis",
		 default=0.9, min_value=0.0001),
	Option("r", "num-neighbours", "int", "number of neighbours between coresets", default=10, min_value=1)
	])


#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]

	# the value for which phi_i does chi(i) belong to a cluster
	default_cluster_threshold = options.coreset_power

	# how many neighbours between coresets?
	neighbours_threshold = options.num_neighbours

	pool = Pool()
	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']
	node_names = npz_file['node_names']
	n_clusters = npz_file['n_clusters']
	active_nodes = [Node(nn) for nn in node_names]

	#determine Cluster
	#amount_phi[j]=amount of phi in cluster j
	amount_phi=np.ones(n_clusters,dtype=np.uint64)
	amount_phi=amount_phi*len(chi_matrix)
	amount_phi_total=len(chi_matrix)
	

	# sort columns of chi and return new sorted args
	arg_sort_cluster=np.argsort(chi_matrix,axis=0)
	# sort columns of chi and return new sorted chi
	# notice that the last row has to be [1 ... 1]
	sort_cluster=np.sort(chi_matrix,axis=0)
	# show_cluster contains arrays of the type [a b] where a is the row
	# and b the column of the entry from chi matrix  where 
	# chi_sorted(a,b) > default_cluster_threshold
	show_cluster=np.argwhere(sort_cluster > default_cluster_threshold)
	
	# from the above it is clear
	# that the amount of phi function
	# of cluster i is given by x where x the number so that 
	# [x i] is in show_cluster and for all 
	# [y i] in show_cluster we have x>y 
	# we define amount_phi[i]=x	
	for element in show_cluster:
		index=element[0]
		cluster=element[1]
		if amount_phi[cluster]>index:
			amount_phi[cluster]=index

	# create cluster list which contains arrays
	# each array consinst of a set of numbers corresponding to 
	# the phi function of node_number
	cluster=[]
	for i in range(0,n_clusters):
		cluster_set=[]		
		for j in range(amount_phi[i],amount_phi_total):
			cluster_set.append(arg_sort_cluster[j][i])	
		cluster.append(np.array(cluster_set))

	cluster=np.array(cluster)

	# get transition states
	transition_state=[]
	for i in range(1,amount_phi_total):
		it_is_transition=True
		for element in cluster:
			for phi_index in element:
				if phi_index ==i :
					it_is_transition=False

		if it_is_transition:
			transition_state.append(i)


	#print "CLUSTER:"
	#print cluster	

	#print "Transition_state"
	#print transition_state

	for cluster_set in cluster:
		print ""
		print "NEXT CLUSTER:"
		print cluster_set
		count_neighbour_in_total=0
		for node_index in cluster_set:
			current_trajectory = active_nodes[node_index].trajectory
			current_array 	   = check_membership_to_cluster(current_trajectory,cluster_set,active_nodes)

			count_steps=0;
			# todo momentan ist membership >1 THEORETISCH möglich..
			membership_threshold_upper = 1
			membership_threshold	   = 0.9
			membership_threshold_lower = 0
			amount_neighbours 	   = len(np.argwhere(current_array < membership_threshold))
			
			neighbours_threshold_for_node = np.round(neighbours_threshold / len(cluster_set))
			if neighbours_threshold_for_node == 0:
				neighbours_threshold_for_node = 1
			
			while amount_neighbours !=neighbours_threshold_for_node:
				if amount_neighbours > neighbours_threshold_for_node:
					membership_threshold_upper 	= membership_threshold
					membership_threshold		= (membership_threshold + membership_threshold_lower)/2
				else:	
					
					membership_threshold_lower 	= membership_threshold
					membership_threshold		= (membership_threshold + membership_threshold_upper)/2

				count_steps = count_steps + 1 
				if count_steps > 1000:
					print "TOO MANY STEPS ######BREAK######"
					break

				amount_neighbours =len(np.argwhere(current_array < membership_threshold))
				#print membership_threshold
				#print "--"
				#print amount_neighbours
				
			

			if amount_neighbours > neighbours_threshold_for_node:
				neighbours_arg = np.argwhere(current_array < membership_threshold)[0:neighbours_threshold_for_node]
			else:
				neighbours_arg = np.argwhere(current_array < membership_threshold)
			create_neighbours(active_nodes[node_index],neighbours_arg ,pool)

			count_neighbour_in_total=count_neighbour_in_total+len(neighbours_arg)
		print "SET HAS SO MANY NEIGHBOURS:"		
		print count_neighbour_in_total
		print " - -- - done - -- -"

	#create nodes
	zgf_setup_nodes.main()
	zgf_grompp.main()

	#save cluster
	np.savez(pool.analysis_dir+"core_set_cluster.npz", clustering = cluster)
	
def create_neighbours(node, list_of_neighbours,pool):
	for index in list_of_neighbours:
		n = Node()
		n.parent_frame_num = index[0]
		n.parent = node
		n.state = "created"
		n.extensions_counter = 0
		n.extensions_max = 1#options.num_runs
		n.extensions_length = 50#options.sampling_length
		n.sampling_length = 50#options.sampling_length
		n.internals = node.trajectory.getframe(index[0])
		pool.append(n)
		n.save()		

def check_membership_to_cluster(x,cluster,active_nodes):
	membership_value=0.
	#print "phi_values"
	for i in cluster:
		node 		  = active_nodes[i]
		membership_value  = membership_value + get_phi(x,node)

	return membership_value
		
#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF


