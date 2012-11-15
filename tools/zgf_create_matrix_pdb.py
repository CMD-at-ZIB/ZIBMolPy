#!/usr/bin/python
# -*- coding: utf-8 -*-


from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import Option, OptionsList


#import matplotlib.pyplot as plt

import sys
import os
import re
import numpy as np

from ZIBMolPy.gromacs import read_mdp_file

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
	
	#load chi_matrix		
	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']		
	active_nodes = pool.where("isa_partition")

	if instructions['p_nodes']=="chi" or True:
		# extract highest chi nodes
		arg_sort_cluster=np.argsort(chi_matrix,axis=0)
		epic_row = arg_sort_cluster[len(arg_sort_cluster)-1]
		new_active_nodes=[]
		new_internals=[]

		for i in range(0,len(epic_row)):
			new_active_nodes.append(active_nodes[epic_row[i]])
		
		active_nodes = new_active_nodes
		print "# ONLY CHI NODES #"
		for i in active_nodes:
			print i.internals.array

	elif instructions['p_nodes']=="user":
		npz_choosen_file = np.load(pool.analysis_dir+"user_cluster.npz")
		active_nodes = npz_choosen_file['the_choosen_nodes']
		print "# USER NODES #"
		for i in active_nodes:
			print i.internals.array


	#mdp = read_mdp_file(pool.mdp_fn)
	#dt= float(mdp['dt'])
	
	#initiliase Schuette Matrix P

	
	# ignore set based for the moment
	#p_radius = userinput("Please enter distance r, that indicates which state belongs to a certan node", "int", "x>0")
	#p_radius = 100000
	
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
			
			leagel_ready_node=True
			for node_temp in active_nodes:
				if (temp_dist>(frame_value - node_temp.internals).norm2()):
					leagel_ready_node=False
					print "strange ready node!"				
			
			
			
			#iterate pdb files
			#if(temp_dist <= p_radius):
			if(leagel_ready_node):			
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
						if(True):						
							P[index_i,index_j] += weight 
							P_hard[index_i,index_j] += 1
							
		index_i=index_i+1
		
		
	
			
	#normalise P
	for i in range(0,len(active_nodes)):
		factor = sum(P[i,:])
		P[i,:] = (1/factor) * P[i,:]
	print "and normalised"
	print P
	print "just counting"
	print P_hard

	np.savez(pool.analysis_dir+"p_pdb.npz", matrix=P ,count=P_hard)

		
#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF


