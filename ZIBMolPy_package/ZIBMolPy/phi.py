# -*- coding: utf-8 -*-

import numpy as np

#===============================================================================
def get_phi_contrib(x, curr_node, coord):
	all_nodes = curr_node.pool.where("isa_partition")
	other_nums = [ get_phi_num_contrib(x, curr_node, n, coord) for n in all_nodes ]
	denom = np.sum(other_nums, axis=0)
	num = get_phi_num_contrib(x, curr_node, curr_node, coord)
	return( num / denom )
	
def get_phi_num_contrib(x, ref_node, curr_node, coord):
	#TODO: implement InternalArray.__setslice__ and use norm2() instead
	""" Takes all values from ref_node.internals except for coordinate coord. \
		There it uses the values x. """ 	
	# #calc normal diff
	# diffs = (ref_node.internals - curr_node.internals).array
	# #ignore results for coordinate coord
	# print diffs.shape
	# diffs[coord.index] = 0 #this will be counted in diff2
	# diff1 = np.sum(np.square(diffs))
	# 
	
	diffs = ref_node.internals - curr_node.internals
	diffs[:, coord] = 0  #this will be counted in diff2
	diff1 = diffs.norm2()
	
	#calc result for coodinate coord
	diff2 = np.square(coord.sub(x, curr_node.internals.getcoord(coord)))
	#add those two and take advantage of broadcasting
	diff12 = diff1 + diff2 #using broadcasting
	return( np.exp( -curr_node.pool.alpha * diff12 ) )


#===============================================================================
def get_phi_contrib_potential(x, curr_node, coord):
	#return( -1/get_beta(curr_node.pool.temperature)*np.log( get_phi_contrib(x, curr_node, coord) ) )
	return( -1/curr_node.pool.thermo_beta*np.log( get_phi_contrib(x, curr_node, coord) ) )





			

#===============================================================================
def get_phi(frames, curr_node):
	""" Considers only active nodes (isa_partition) """ 	
	return( get_phi_num(frames, curr_node) / get_phi_denom( frames, curr_node.pool.where("isa_partition") ) )
	

def get_phi_num(frames, curr_node):	
	return( np.exp(-curr_node.pool.alpha*( (frames - curr_node.internals).norm2() ) ) )


def get_phi_denom(frames, nodes):
	return( np.sum( get_phi_num(frames, node) for node in nodes) )


#===============================================================================
def get_phi_potential(frames, curr_node):
	#return( -1/get_beta(curr_node.pool.temperature)*np.log( get_phi(frames, curr_node) ) )
	return( -1*curr_node.pool.thermo_beta*np.log( get_phi(frames, curr_node) ) )

#EOF
