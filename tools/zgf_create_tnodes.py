#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the ninth step of ZIBgridfree.}

	This tool adds additional nodes to the pool called transition (or 'T') nodes. They are essential to find out the probability to move either
		1. from one metastable cluster to another (transition-level 'clusters', matrix $P_c(\\tau)$) or
		2. from one node to another (transition-level 'nodes', matrix $P(\\tau)$).

	If one decides to choose 'cluster', one gets soft clusters in the spirit of PCCA+, where each configuration belongs to a specific cluster with a certain probability. If one chooses 'nodes', than one gets a hard clustering in terms of a Voronoi tesselation, where the center of each Voronoi cell is represented by a node of the pool.

	In general, one assumes that more transition nodes lead to more accurate probability information. After creating transition nodes, L{zgf_mdrun} has to be run again in order to perform the transition sampling, namely 'num-runs' trajectories of 'sampling-length' ps length. Finally, the transition matrix can be computed by calling L{zgf_create_pmatrix}. The amount of transition nodes that is created depends on the user input and is described in the following.

	B{The next step is L{zgf_create_pmatrix}.}

How it works
============
	At the command line, type::
		$ zgf_create_tnodes [options]

Clusters
========
	The clusters identified by PCCA+ are described in terms of the $\chi$ matrix. For the transition probability computation, a node is assumed to belong to such a cluster if its $\chi$-Value is larger than 0.5. For each node that belongs to a given cluster, this method generates 'num-tnodes' transition nodes. To avoid unnecessary computational cost, one can avoid creating 'num-tnodes' for those nodes where the $\chi$-Value is already very close to 1 since one can assume that trajectories starting from those points will most likely not undergo a transition. The user may only generate 'num-tnodes' for a node that belongs to a cluster with a percentage between 0.5 and X where X is the 'coreset-power'. Each node that belongs to a cluster will spawn 'num-tnodes' transition nodes.

Nodes (Voronoi cells)
=====================
	Each Voronoi cell gets 'num-tnodes' transition nodes.	

Save mode
=========
	After execution of L{zgf_mdrun}, each transition node creates trr, edr and log files. These files require disk space, but are not needed to calculate the transition probability. If one is going to choose the 'pdb' option, then the trr, edr and log files are deleted. If for any reasons those files are needed, deletion can be avoided by choosing the value 'complete'. 
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
	Option("t", "transition-level", "choice", "transition level", choices=("clusters","nodes") ),
	Option("n", "num-tnodes", "int", "number of tnodes per node", default=1, min_value=1),
	Option("r", "num-runs", "int", "number of runs", default=5, min_value=0),
	Option("l", "sampling-length", "int", "length of sampling per run in ps", default=100, min_value=0),
	Option("s", "save-mode", "choice", "files to store", choices=("pdb","complete") ),
	Option("c", "coreset-power", "float", "ignore nodes with chi value higher than coreset-power ('clusters' only)", default=0.9, min_value=0.5),	
	Option("m", "min-nodes", "int", "min number of nodes to consider ('clusters' only)", default=3, min_value=1),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return(os.path.exists(pool.chi_mat_fn))
	

#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]

	pool = Pool()
	active_nodes = pool.where("isa_partition")

	if options.transition_level == "clusters":
		npz_file = np.load(pool.chi_mat_fn)
		chi_matrix = npz_file['matrix']
		n_clusters = npz_file['n_clusters']

		default_cluster_threshold = options.coreset_power

		# determine cluster
		#TODO this part is too cryptic
		# amount_phi[j] = amount of basis functions per cluster j
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
				counter += 1
				# and ignore nodes which have a higher chi value then default_cluster_threshold
				if( chi_matrix[node_index][i] > default_cluster_threshold and counter>options.min_nodes):
					continue
				
				node = active_nodes[node_index]
				trajectory= node.trajectory
			
				print "-----"
				print "Generating transition nodes for node %s..."%node.name
			
				neighbour_frames = get_indices_equidist(node, options.num_tnodes)
		
				# create transition node for node_index
				for frame_number in neighbour_frames:
					print "Using frame %d as starting configuration."%frame_number
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
				print "%d transition nodes generated."%options.num_tnodes
				print "-----"

		zgf_setup_nodes.main()
		zgf_grompp.main()
	
		cluster_dict = {}
		for (ic,c) in enumerate(cluster):
			cluster_dict['cluster_%d'%ic] = c

		# save cluster
		np.savez(pool.analysis_dir+"core_set_cluster.npz", **cluster_dict)

	elif options.transition_level == "nodes":
		for node in active_nodes:
			trajectory= node.trajectory
			
			# TODO duplicate code... use the one above
			print "-----"
			print "Generating transition nodes for node %s..."%node.name

			neighbour_frames = get_indices_equidist(node, options.num_tnodes)

			# create transition point for node_index
			for frame_number in neighbour_frames:
				print "Using frame %d as starting configuration."%frame_number
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
			print "%d transition nodes generated."%options.num_tnodes
			print "-----"

		zgf_setup_nodes.main()
		zgf_grompp.main()


	instructionFile = pool.analysis_dir+"instruction.txt"

	f = open(instructionFile, "w")
	f.write("{'power': %f, 'tnodes': %d, 'level': '%s', 'min_nodes': %d}"%(options.coreset_power, options.num_tnodes, options.transition_level, options.min_nodes))
	f.close()


#===============================================================================
# get equidistant indices 
def get_indices_equidist(node, n_neighbours):
	return np.linspace(0, len(node.trajectory)-1, num=n_neighbours).astype(int)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

