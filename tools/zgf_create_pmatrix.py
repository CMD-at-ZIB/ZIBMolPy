#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	Calculate probabilty between sets of conformation choosen in L{zgf_create_tnodes}. Prints P matrix.
"""
from ZIBMolPy.ui import OptionsList
from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import userinput, Option, OptionsList

import sys

import os
import re

import numpy as np

options_desc = OptionsList()

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc


def is_applicable():
	pool = Pool()
	return(len(pool.where("state == 'ready'"))>0)

#===============================================================================
def main():
	
	pool = Pool()
	
	# check if create_neighbours was executed before
	assert(os.path.exists(pool.analysis_dir+"instruction.txt"))

	try:
		f = open(pool.analysis_dir+"instruction.txt")
		command = f.read()
		instructions = eval(command)
	except:			
		raise(Exception("Could not parse: "+pool.analysis_dir+"instruction.txt"))

	grid = instructions['grid']
	default_cluster_threshold = float(instructions['power'])
	n_tnodes = int(instructions['tnodes']) 

	# find amount of runs
	all_ready_nodes = pool.where("state == 'ready'")
	runs = all_ready_nodes[0].extensions_max + 1

	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']
	node_names = npz_file['node_names']
	
	active_nodes = [Node(nn) for nn in node_names]

	if grid=="cluster":
		npz_file = np.load(pool.analysis_dir+"core_set_cluster.npz")
		cluster = [npz_file[c] for c in sorted(npz_file.files)]

		# transition matrix
		P = np.zeros(shape=(len(cluster),len(cluster)))

		print "Chi Matrix:"
		print chi_matrix
		print "Cluster:"
		print cluster

		print " For each node sample "+str(n_tnodes)+" tnodes, with "+str(runs)+" runs"
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
						neighbours=get_indices_equidist(node, n_tnodes) 
						for frame_number in neighbours:
							# behave like node would not move in simulation
							weight = frameweights_of_node_i[frame_number]
							#todo: add option for calculat Matrix without soft chi_matrix
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
	elif grid=="nodes":
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
							P[index_i,index_j] += weight*node.obs.weight_corrected 
							P_hard[index_i,index_j] += 1
							
			index_i=index_i+1
		
			
	for i in range(0,len(cluster)):
		factor = sum(P[i,:])
		P[i,:] = (1/factor) * P[i,:]

	if grid=="cluster":
		print "Cluster :" + str(cluster)
	elif grid=="nodes":
		print "Nodes :" + str(active_nodes)

	print "Transitionmatrix :" + str(P) #TODO some info about tau would be nice
	
	np.savez(pool.pc_mat_fn, matrix=P, node_names=node_names)

		
#===============================================================================
# get equidistant indices 
def get_indices_equidist(node, n_neighbours):
	return np.linspace(0, len(node.trajectory)-1, num=n_neighbours).astype(int)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF


