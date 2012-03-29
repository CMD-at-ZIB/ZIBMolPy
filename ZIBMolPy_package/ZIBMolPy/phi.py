# -*- coding: utf-8 -*-

r"""
Everything related to the nodes' phi-function $\phi_i(\vec x)$.

Each node $i$ has a phi-function $\phi_i(\vec x)$, which determines for each
position $\vec x$ the membership to that node.

The phi-functions partition the internal coordinate space. For all $\vec x$
holds the following condition:
\[  \sum_i \phi_i(\vec x) = 1 \]

The phi-function can be written as a node-dependend numerator $\chi_i(\vec x)$ divided by
a normalisation-factor:
\[ \phi_i(\vec x) = \frac{\chi_i(\vec x)}{\sum_j \chi_j(\vec x)} \]

This numerator is defined as:
\[ \chi_i(\vec x) = \exp(- \alpha \operatorname{dist}(\vec x, \vec q_i)) \]

The node's position $\vec q_i$ is stored in the internal-attribute of the L{Node}-object.
The $\alpha$-value is stored in the L{Pool}.
The dist-function depends on the type of coordinates used.	
For details look at L{InternalCoordinate.sub}.

Please note, that not all nodes contained in the pool participate in the partition
of the internal coordinate space.
If a node participates in the partition is determined by the property L{Node.isa_partition}.  
"""	

import numpy as np

#===============================================================================
def get_phi_contrib(x, node_i, coord):
	all_nodes = node_i.pool.where("isa_partition")
	other_nums = [ get_phi_num_contrib(x, node_i, n, coord) for n in all_nodes ]
	denom = np.sum(other_nums, axis=0)
	num = get_phi_num_contrib(x, node_i, node_i, coord)
	return( num / denom )
	
def get_phi_num_contrib(x, ref_node, node_i, coord):
	#TODO: implement InternalArray.__setslice__ and use norm2() instead
	r""" Takes all values from ref_node.internals except for coordinate coord. \
		There it uses the values x. """ 	
	# #calc normal diff
	# diffs = (ref_node.internals - node_i.internals).array
	# #ignore results for coordinate coord
	# print diffs.shape
	# diffs[coord.index] = 0 #this will be counted in diff2
	# diff1 = np.sum(np.square(diffs))
	# 
	
	diffs = ref_node.internals - node_i.internals
	diffs[:, coord] = 0  #this will be counted in diff2
	diff1 = diffs.norm2()
	
	#calc result for coodinate coord
	diff2 = np.square(coord.sub(x, node_i.internals.getcoord(coord)))
	#add those two and take advantage of broadcasting
	diff12 = diff1 + diff2 #using broadcasting
	return( np.exp( -node_i.pool.alpha * diff12 ) )


#===============================================================================
def get_phi_contrib_potential(x, node_i, coord, epsilon=0):
#	r""" Calculates $\frac{-1}{\beta \log( getphicontrib(x, node_i, coord) )}$,
#	where $\beta$ is L{Pool.thermo_beta} """
	
	return( -1/node_i.pool.thermo_beta*np.log( get_phi_contrib(x, node_i, coord) + epsilon ) )


#===============================================================================
def get_phi(x, node_i):
	r""" Calculates the phi-function $\phi_i(\vec x)$ of node_i at the positions given by x.
	
	The participating nodes are found via L{Node.isa_partition}""" 	
	return( get_phi_num(x, node_i) / get_phi_denom( x, node_i.pool.where("isa_partition") ) )
	

def get_phi_num(x, node_i):
	r""" Calculates the numerator $\chi_i(\vec x)$ of the phi-function of node_i at the positions given by x. """ 
	return( np.exp(-node_i.pool.alpha*( (x - node_i.internals).norm2() ) ) )


def get_phi_denom(x, nodes):
	r""" Calculates the denominator $\sum_i \chi_i(\vec x)$ of the phi-function.
	
	This is the sum over the numerators of the given nodes at the positions given by x. """
	return( np.sum( get_phi_num(x, node) for node in nodes) )


#===============================================================================
def get_phi_potential(x, node_i, epsilon=0):
	r""" Calculates $-\beta^{-1} \log \phi_i(\vec x)$,
	where $\beta$ is L{Pool.thermo_beta} """
	
	return( -1/node_i.pool.thermo_beta*np.log( get_phi(x, node_i) + epsilon ) )

#EOF