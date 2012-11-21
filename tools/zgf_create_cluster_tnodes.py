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
	Option("c", "coreset-power", "float", "ignore nodes with chi value higher than coreset-power", default=0.9, min_value=0.5),	
	Option("n", "num-neighbours", "int", "number of neighbours per node", default=1, min_value=1),	
	Option("l", "sampling-length", "int", "length of sampling per run in ps", default=100, min_value=0),
	Option("r", "num-runs", "int", "number of runs", default=5, min_value=0)
	])

#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]

	default_cluster_threshold = options.coreset_power

	pool = Pool()
	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']
	node_names = npz_file['node_names']
	n_clusters = npz_file['n_clusters']
	active_nodes = [Node(nn) for nn in node_names]

	#determine Cluster
	#amount_phi[j]=amount of phi in cluster j #TODO discrete value? So amount of basis functions per cluster???
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
	show_cluster=np.argwhere(sort_cluster > 0.5 )

	# from the above it could be clear
	# that the amount of phi function
	# of cluster i is given by x where x the number so that 
	# [x i] is in show_cluster and for all 
	# [y i] in show_cluster we have x>y 
	# we define amount_phi[i]=x	
	for element in show_cluster:
		print element
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
			#if (j < amount_phi[i] + 3):
				cluster_set.append(arg_sort_cluster[j][i])	
		cluster.append(cluster_set)

	for i in range(len(cluster)):
		counter = 0
		for node_index in cluster[i]:
			# go through at least 3 nodes
			# and ignore nodes which have a higher chi value then default_cluster_threshold
			if( chi_matrix[node_index][i] > default_cluster_threshold and counter>2):
				continue
				
			counter = counter + 1

			node = active_nodes[node_index]
			trajectory= node.trajectory
			
			print "-----"
			print "printing neighbours for node %s"%node.name
			
			neighbour_frames = get_indices_equidist(node, options.num_neighbours)
		
			# create transition node for node_index
			for frame_number in neighbour_frames:
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
			print "%d neighbour nodes generated."%options.num_neighbours
			print "-----"

	zgf_setup_nodes.main()
	zgf_grompp.main()
	
	instructionFile = "analysis/instruction-cluster.txt"	

	f = open(instructionFile, "w")
	f.write("{'power': '"+str(options.coreset_power)+"','neighbour': '"+str(options.num_neighbours)+"','runs': '"+str(options.num_runs)+"'}")
	f.close()

	cluster_dict = {}
	for (ic,c) in enumerate(cluster):
		cluster_dict['cluster_%d'%ic] = c

	# save cluster
	np.savez(pool.analysis_dir+"core_set_cluster.npz", **cluster_dict)


#===============================================================================
# get equidistant indices 
def get_indices_equidist(node, n_neighbours):
	return np.linspace(0, len(node.trajectory)-1, num=n_neighbours).astype(int)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

