#!/usr/bin/python
# -*- coding: utf-8 -*-


from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import userinput, Option, OptionsList

import sys

import os
import re

import numpy as np


#===============================================================================
def main():
	
	pool = Pool()
	
	# check if create_neighbours was executed before
	assert(os.path.exists(pool.analysis_dir+"instruction-cluster.txt"))

	try:
		f = open(pool.analysis_dir+"instruction-cluster.txt")
		command = f.read()
		instructions = eval(command)
		
	except:			
		raise(Exception("Could not parse: "+pool.analysis_dir+"instruction.txt"))

	default_cluster_threshold = float(instructions['power'])
	amount_neighbour = float(instructions['neighbour'])
	runs = float(instructions['runs'])

	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']
	node_names = npz_file['node_names']
	n_clusters = npz_file['n_clusters']
	active_nodes = [Node(nn) for nn in node_names]

	npz_file = np.load(pool.analysis_dir+"core_set_cluster.npz")
	cluster = npz_file['clustering']

	# transition matrix
	P = np.zeros(shape=(len(cluster),len(cluster)))

	print "Chi Matrix:"
	print chi_matrix
	print "Cluster:"
	print cluster

	print " For each node sample "+str(amount_neighbour)+" neighbours, with "+str(runs)+" runs"
	#start calculating matrix
	cluster_index_i=0	
	for i in range(len(cluster)):
			print ""
			print " CLUSTER "+str(i)
			print cluster[i]
			counter = 0
			for node_index in cluster[i]:
				counter=counter+1
				node = active_nodes[node_index]	
				frameweights_of_node_i= node.frameweights

				# go through at least 3 nodes
				# and nodes which have less chi value then default_cluster_threshold	
				if( chi_matrix[node_index][i] > default_cluster_threshold and counter>3):
					print "Node "+str(node_index)
					print "chi value: "+str(chi_matrix[node_index][i])
					print "counter:   "+str(counter)
					print "cluster:   "+str(cluster_index_i)
					print "no neighbours"
					print "- - - -"
					# for other nodes add correspondig P value - assuming those cluster are metastable
					trajectory= node.trajectory
					neighbours=get_neighbours_steinzeit(node, trajectory, amount_neighbour)
					for frame_number in neighbours:
						# behave like node would not move in simulation
						weight = frameweights_of_node_i[frame_number]
						P[cluster_index_i,cluster_index_i] += runs*weight*node.obs.weight_corrected*chi_matrix[node_index][cluster_index_i]*chi_matrix[node_index][cluster_index_i]
						#print "fram_weight "+str(weight)
						#print "node_weight "+str(node.obs.weight_corrected)
						#print "chi_start   "+str(chi_matrix[node_index][cluster_index_i])
						#print "chi_end     "+str(chi_matrix[node_index][cluster_index_i])
						#print "result:     "+str(weight*node.obs.weight_corrected*chi_matrix[node_index][cluster_index_i]*chi_matrix[node_index][cluster_index_i])	
					
					continue
				
				
				ready_nodes = pool.where("state == 'ready' and parent!=None and parent.name=='%s'"%node.name)

				print "Node "+str(node_index)
				print "chi value: "+str(chi_matrix[node_index][i])
				print "counter:   "+str(counter)
				print "cluster:   "+str(cluster_index_i)
				print "Amount neighbours: "+str(len(ready_nodes))
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

							#calc P entry
							#print "fram_weight "+str(weight)
							#print "node_weight "+str(node.obs.weight_corrected)
							#print "chi_start   "+str(chi_matrix[node_index][cluster_index_i])
							#print "chi_end     "+str(chi_matrix[index_j][cluster_index_j])
							#print "result:     "+str(weight*node.obs.weight_corrected*chi_matrix[node_index][cluster_index_i]*chi_matrix[index_j][cluster_index_j])
							#if(temp_val[index_j] <= p_radius):	
							P[cluster_index_i,cluster_index_j] += weight*node.obs.weight_corrected*chi_matrix[node_index][cluster_index_i]*chi_matrix[index_j][cluster_index_j]
			
					
			cluster_index_i=cluster_index_i+1
		
			
	for i in range(0,len(cluster)):
		factor = sum(P[i,:])
		P[i,:] = (1/factor) * P[i,:]

	print "Cluster :" + str(cluster)
	print "Transitionmatrix :" + str(P)
	
	np.savez(pool.analysis_dir+"p_pdb.npz", matrix=P)
		
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
	return neighbours

#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF


