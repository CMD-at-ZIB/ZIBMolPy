#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the ninth step of ZIBgridfree.}

	This tool creates additional nodes to the pool called transition nodes. They are essential to find out the probability to move from one set of conformations to another set of conformation. In general one assumes that more transition nodes lead to closer probability information. After creating transition nodes one may start  L{zgf_mdrun} and finally to observe the probability between sets one may call L{zgf_create_pmatrix}. If one starts L{zgf_mdrun} then from each transition node there are going to be L{num-runs} trajectories calculated of L{sampling-length} ps. The amount of created transition nodes depends on the user input and is described in the following. 

How it works
============
	At the command line, type::
		$ zgf_create_tnodes [options]

Grid Mode
=========
	Grid Mode determines the set of conformations where you may calculate the probability between. If one decide's to choose L{cluster} then one gets soft sets where each conformation does only belong with a certain probability to a specific set. If one chooses L{nodes} than one gets a hard clustering in a voronoi diagram, where the center of each voronoi cell is represented by a node of the pool.

Cluster
=======
	After execution of L{zgf_analyse} ZIBGridFree determines $n$ Chi-Functions. Each Chi-Function represents a cluster. A node belongs to such a cluster if his corresponding Chi-Value is above 0.5. In general for each node that belongs to a cluster this method generates L{num-tnodes}. To avoid unnecessary computing power one can avoid creating L{num-tnodes} for those nodes where the Chi-Value is already very close to 1 since one can assume that trajectories starting from those points may not move. The user may only gernerate L{num-tnodes} for a node that belongs to a cluster with a percantage between 0.5 and X where X is the L{coreset-power}. Each node that belongs to a cluster will get L{num-tnodes} transition nodes.

Voronoi Cells
=============
	Each Voronoi Cell becomes L{num-tnodes} transition nodes.	

Save Mode
=========
	After execution of L{zgf_mdrun} each transition node creates .trr, .edr and log files. These files are not needed to calcultae the mentioned probability. If one is going to choose the L{only pdb} option than the .tt,.edr and log files are deleted. If for any reasons those files are needed that one can avoid deletion by the L{complete} option. 
"""


from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import userinput, Option, OptionsList

import zgf_setup_nodes
import zgf_grompp

import sys

import os

import numpy as np

options_desc = OptionsList([	
	Option("c", "coreset-power", "float", "ignore nodes with chi value higher than coreset-power", default=0.9, min_value=0.5),	
	Option("n", "num-tnodes", "int", "number of tnodes per node", default=1, min_value=1),	
	Option("l", "sampling-length", "int", "length of sampling per run in ps", default=100, min_value=0),
	Option("r", "num-runs", "int", "number of runs", default=5, min_value=0),
	Option("s", "save-mode", "choice", "What files do you want to save", choices=("only pdb","complete") ),
	Option("g", "grid-mode", "choice", "Get Transitionpropability of nodes or clusters?", choices=("cluster","nodes") )
	])

def is_applicable():
	pool = Pool()
	return(os.path.exists(pool.chi_mat_fn))
	

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
	

	if options.grid_mode == "cluster":
		#determine Cluster
		#amount_phi[j]=amount of phi in cluster j #TODO discrete value? So amount of basis functions per cluster??? -- Answer:Yes!
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
			
				neighbour_frames = get_indices_equidist(node, options.num_tnodes)
		
				# create transition node for node_index
				for frame_number in neighbour_frames:
					print frame_number
					n = Node()
					n.parent_frame_num = frame_number
					n.parent = node
					n.state = "created"
					n.extensions_counter = 0
					n.extensions_max = options.num_runs-1
					n.extensions_length = options.sampling_length
					n.sampling_length = options.sampling_length
					n.internals = trajectory.getframe(frame_number)
					n.save_mode = options.save_mode
					pool.append(n)
					n.save()
				print "%d neighbour nodes generated."%options.num_tnodes
				print "-----"

		zgf_setup_nodes.main()
		zgf_grompp.main()
	
		cluster_dict = {}
		for (ic,c) in enumerate(cluster):
			cluster_dict['cluster_%d'%ic] = c

		# save cluster
		np.savez(pool.analysis_dir+"core_set_cluster.npz", **cluster_dict)

	elif options.grid_mode == "nodes":
		for node in active_nodes:   # TODO make nicer
			trajectory= node.trajectory
			
			print "-----"
			print "printing neighbours for node %s"%node.name

			neighbour_frames = get_indices_equidist(node, options.num_tnodes)

			#create transition point for node_index
			for frame_number in neighbour_frames:
				print frame_number
				n = Node()
				n.parent_frame_num = frame_number
				n.parent = node
				n.state = "created"
				n.extensions_counter = 0
				n.extensions_max = options.num_runs-1
				n.extensions_length = options.sampling_length
				n.sampling_length = options.sampling_length
				n.internals = trajectory.getframe(frame_number)
				n.save_mode = options.save_mode
				pool.append(n)
				n.save()
			print "%d neighbour nodes generated."%options.num_tnodes
			print "-----"

		zgf_setup_nodes.main()
		zgf_grompp.main()

	
	instructionFile = "analysis/instruction.txt"	

	f = open(instructionFile, "w")
	f.write("{'power': '"+str(options.coreset_power)+"','tnodes': '"+str(options.num_tnodes)+"','grid': '"+str(options.grid_mode)+"'}")
	f.close()


#===============================================================================
# get equidistant indices 
def get_indices_equidist(node, n_neighbours):
	return np.linspace(0, len(node.trajectory)-1, num=n_neighbours).astype(int)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

