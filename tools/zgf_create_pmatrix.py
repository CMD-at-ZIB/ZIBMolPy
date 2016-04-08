#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the final step of ZIBgridfree.}

	This tool will calculate the transition probability matrices $P_c(\\tau)$ (transitions between metastable subsets, i.e. the clusters identified by PCCA+) or $P(\\tau)$ (transitions between all nodes), depending on what was chosen in L{zgf_create_tnodes}.

How it works
============
	At the command line, type::
		$ zgf_create_pmatrix [options]
"""

from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.ui import Option, OptionsList

import sys
import os
import re

import numpy as np
from scipy.io import savemat

options_desc = OptionsList([
	Option("m", "export-matlab", "bool", "export matrices as mat-files", default=False),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return(len(pool.where("state == 'ready'"))>0)

#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	pool = Pool()
	active_nodes = pool.where("isa_partition")

	# check if zgf_create_tnodes was executed before
	assert(os.path.exists(pool.analysis_dir+"instruction.txt"))
	try:
		f = open(pool.analysis_dir+"instruction.txt")
		command = f.read()
		instructions = eval(command)
	except:			
		raise(Exception("Could not parse: "+pool.analysis_dir+"instruction.txt"))

	transition_level = instructions['level']
	n_tnodes = instructions['tnodes'] 

	all_ready_nodes = pool.where("state == 'ready'")
	n_runs = all_ready_nodes[0].extensions_max + 1

	assert(all_ready_nodes[0].sampling_length == all_ready_nodes[0].extensions_length)
	tau = all_ready_nodes[0].sampling_length

	# let's calculate a Pc matrix
	if transition_level=="clusters":
		default_cluster_threshold = instructions['power']
		min_nodes = instructions['min_nodes']

		npz_file = np.load(pool.chi_mat_fn)
		chi_matrix = npz_file['matrix']

		npz_file = np.load(pool.analysis_dir+"core_set_cluster.npz")
		cluster = [npz_file[c] for c in sorted(npz_file.files)]

		Pc = np.zeros(shape=(len(cluster),len(cluster)))

		print "For each node, sample %d tnodes with %d runs"%(n_tnodes, n_runs)
		# start calculating matrix
		cluster_index_i=0 #TODO maker nicer
		for i in range(len(cluster)):
				print "\n CLUSTER %d contains the following nodes:"%i
				print cluster[i]
				counter = 0
				for node_index in cluster[i]:
					counter=counter+1
					node = active_nodes[node_index]	
					frameweights_of_node_i= node.frameweights

					# and nodes which have a higher chi value then default_cluster_threshold	
					if( chi_matrix[node_index][i] > default_cluster_threshold and counter>min_nodes):
						print "Node "+str(node_index) #TODO this index is not the global node index... somewhat misleading
						print "chi value: "+str(chi_matrix[node_index][i])
						print "counter:   "+str(counter)
						print "cluster:   "+str(cluster_index_i)
						print "no tnodes"
						print "- - - -"
						# for other nodes add corresponding Pc value - assuming those cluster are metastable
						trajectory= node.trajectory
						tnode_frames=get_indices_equidist(node, n_tnodes) 
						for frame_number in tnode_frames:
							# behave like node would not move in simulation
							weight = frameweights_of_node_i[frame_number]
							#TODO: add option for calculat Matrix without soft chi_matrix
							Pc[cluster_index_i,cluster_index_i] += n_runs*weight*node.obs.weight_corrected*chi_matrix[node_index][cluster_index_i]*chi_matrix[node_index][cluster_index_i]		
						continue
				
				
					ready_nodes = pool.where("state == 'ready' and parent!=None and parent.name=='%s'"%node.name)

					print "Node "+str(node_index) #TODO this index is not the global node index... somewhat misleading
					print "chi value: "+str(chi_matrix[node_index][i])
					print "counter:   "+str(counter)
					print "cluster:   "+str(cluster_index_i)
					print "#tnodes:   "+str(len(ready_nodes))
					print "- - - -"

				
					for ready_node in ready_nodes:	
						weight = frameweights_of_node_i[ready_node.parent_frame_num]
						#frame_value = pool.converter.read_pdb(ready_node.pdb_fn)
						#temp_dist=(frame_value - node_i.internals).norm2()
			
						#iterate pdb files			
						for fn in os.listdir(ready_node.dir):
							if(re.match(".+.pdb",fn)):
								# add radius feature in future 
								frame_value = pool.converter.read_pdb(ready_node.dir+"/"+fn)
								#calculate distances
								temp_val=np.zeros(len(active_nodes))
								index_temp=0
								for node_temp in active_nodes:
									temp_val[index_temp]=(frame_value - node_temp.internals).norm2()
									index_temp=index_temp +1

								# which node has closest distance?
								index_j=np.argsort(temp_val)[0]
							
								#which cluster has highest chi value?
								cluster_index_j = np.argsort(chi_matrix[index_j][:])[len(cluster)-1]

								#calc Pc entry
								Pc[cluster_index_i,cluster_index_j] += weight*node.obs.weight_corrected*chi_matrix[node_index][cluster_index_i]*chi_matrix[index_j][cluster_index_j]
			
					
				cluster_index_i=cluster_index_i+1

		for i in range(0,len(cluster)):
			factor = sum(Pc[i,:])
			Pc[i,:] = (1/factor) * Pc[i,:]

		# store final results
		np.savez(pool.pc_mat_fn, matrix=Pc, node_names=[n.name for n in active_nodes]) #TODO store additional info?
		if options.export_matlab:		
			savemat(pool.analysis_dir+"pc_mat.mat", {"Pc_matrix":Pc})


	# let's calculate a P matrix
	elif transition_level=="nodes":
		P = np.zeros(shape=(len(active_nodes),len(active_nodes)))
		P_hard = np.zeros(shape=(len(active_nodes),len(active_nodes)))

		index_i=0
		for node_i in active_nodes:
			# get frameweights and ready_nodes
			ready_nodes = pool.where("state == 'ready' and parent!=None and parent.name=='%s'"%node_i.name)
			frameweights_of_node_i= node_i.frameweights

			for ready_node in ready_nodes:	
				weight = frameweights_of_node_i[ready_node.parent_frame_num]
				frame_value = pool.converter.read_pdb(ready_node.pdb_fn)
				temp_dist=(frame_value - node_i.internals).norm2()
			
				legal_ready_node=True
				for node_temp in active_nodes:
					if (temp_dist>(frame_value - node_temp.internals).norm2()):
						legal_ready_node=False
						print "strange ready node!"				
			
				#iterate pdb files
				#if(temp_dist <= p_radius):
				if(legal_ready_node):			
					for fn in os.listdir(ready_node.dir):
						if(re.match("[^#].+.pdb",fn)):
							# add radius feature in future
							#print "Filedirectory"
							#print ready_node.dir+"/"+fn 
							frame_value = pool.converter.read_pdb(ready_node.dir+"/"+fn)
							#calculate distances
							temp_val=np.zeros(len(active_nodes))
							index_temp=0
							for node_temp in active_nodes:
								temp_val[index_temp]=(frame_value - node_temp.internals).norm2()
								index_temp=index_temp +1						
							
							index_j=np.argsort(temp_val)[0]				
							
							#calc P entry
							#if(temp_val[index_j] <= p_radius):					
							P[index_i,index_j] += weight*node_i.obs.weight_corrected 
							P_hard[index_i,index_j] += 1
							
			index_i=index_i+1
		
		for i in range(0,len(active_nodes)):
			factor = sum(P[i,:])
			P[i,:] = (1/factor) * P[i,:]

		# store final results
		np.savez(pool.p_mat_fn, matrix=P, node_names=[n.name for n in active_nodes]) #TODO store additional info?
		if options.export_matlab:		
			savemat(pool.analysis_dir+"p_mat.mat", {"P_matrix":P})

	
	if transition_level=="clusters":
		print "Clusters: " + str(cluster)
		print "Transition matrix Pc for tau = %d ps:"%tau
		print Pc
	elif transition_level=="nodes":
		print "Nodes: " + str(active_nodes)
		print "Transition matrix P for tau = %d ps:"%tau
		print P


#===============================================================================
# get equidistant indices 
def get_indices_equidist(node, n):
	return np.linspace(0, len(node.trajectory)-1, num=n).astype(int)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

