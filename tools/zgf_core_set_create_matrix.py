#!/usr/bin/python
# -*- coding: utf-8 -*-


from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import userinput, Option, OptionsList

import sys

import numpy as np

options_desc = OptionsList([	
	Option("n", "timestep", "int", "Timestep tau", default=30, min_value=1)
	])

#===============================================================================
def main():
	
	options = options_desc.parse_args(sys.argv)[0]

	pool = Pool()
	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']
	node_names = npz_file['node_names']
	n_clusters = npz_file['n_clusters']
	active_nodes = [Node(nn) for nn in node_names]

	npz_file = np.load(pool.analysis_dir+"core_set_cluster.npz")
	cluster = npz_file['clustering']

	#calc row
	row = 0

	# transition core set matrix
	P = np.zeros(shape=(len(cluster),len(cluster)))
	M = np.zeros(shape=(len(cluster),len(cluster)))
	T = np.zeros(shape=(len(cluster),len(cluster)))

	# tau 
	tau 	= options.timestep
	tau_t   = 10
	
	#start calculating matrix	
	for cluster_set in cluster:
		print "calc row " + str(row+1)
		
		print cluster_set
		count_neighbour_in_total=0
		for node_index in cluster_set:
			node_i=active_nodes[node_index]
			ready_nodes = pool.where("state == 'ready' and parent!=None and parent.name=='%s'"%node_i.name)

			for ready_node in ready_nodes:
				column=0
				x_t	= ready_node.trajectory.getframe(tau_t)
				x_tau_t	= ready_node.trajectory.getframe(tau + tau_t)			
				for cluster_set_row in cluster:
					M[row , column] = M[row , column] + check_membership_to_cluster(x_t,cluster_set_row,active_nodes)
					T[row , column] = T[row , column] + check_membership_to_cluster(x_tau_t,cluster_set_row,active_nodes)
					column = column + 1

		row = row + 1 	

	# normalise M, T
	for i in range(0,len(cluster)):
		factor = sum(M[i,:])
		M[i,:] = (1/factor) * M[i,:]

		factor = sum(T[i,:])
		T[i,:] = (1/factor) * T[i,:]

	# obtain P as P = T * M^(-1)
	P = T * np.linalg.inv(M)
	print "M :" +str(M)
	print "T :" + str(T)
	print "P :" + str(P)

	for i in range(0,len(cluster)):
		factor = sum(P[i,:])
		P[i,:] = (1/factor) * P[i,:]

	print "Final P :" + str(P)

def check_closest_cluster(x,cluster,active_nodes):
	cluster_index=0
	final_cluster=0
	max_membership=check_membership_to_cluster(x,cluster[0],active_nodes)
	for cluster_set in cluster:
		cluster_index = cluster_index + 1
		value_temp = check_membership_to_cluster(x,cluster_set,active_nodes)
		if max_membership < value_temp :
			max_membership = value_temp
			final_cluster = cluster_index
	return final_cluster
		

def check_membership_to_cluster(x,cluster_set,active_nodes):
	membership_value=0.
	#print "phi_values"
	for i in cluster_set:
		node 		  = active_nodes[i]
		membership_value  = membership_value + get_phi(x,node)

	return membership_value
		
#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF


