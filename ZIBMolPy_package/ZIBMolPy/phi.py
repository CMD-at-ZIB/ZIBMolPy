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
\[ \chi_i(\vec x) = \exp(- \alpha \operatorname{dist}^2(\vec x, \vec q_i)) \]

Calculation of $\phi_i(\vec x)$ might lead to division by zero for large alpha. In order to calculate $\phi_i(\vec x)$ numerically stable it is helpful to cancel fractions and obtain:
\[ \phi_i(\vec x) = \frac{1}{\sum_j \exp(- \alpha (\operatorname{dist}^2(\vec x, \vec q_j) - \operatorname{dist}^2(\vec x, \vec q_i)))}= \frac{1}{1 + \sum_{j\neq i} \exp(- \alpha (\operatorname{dist}^2(\vec x, \vec q_j) - \operatorname{dist}^2(\vec x, \vec q_i)))} \]

This is an improvement since the denominator is always greater than one. 

The node's position $\vec q_i$ is stored in the internal-attribute of the L{Node}-object.
The $\alpha$-value is stored in the L{Pool}.
The dist-function depends on the type of coordinates used.	
For details look at L{InternalCoordinate.sub<ZIBMolPy.internals.InternalCoordinate.sub>}.

Please note, that not all nodes contained in the pool participate in the partition
of the internal coordinate space.
If a node participates in the partition is determined by the property L{Node.isa_partition<ZIBMolPy.node.Node.isa_partition>}.  
"""

import numpy as np

#===============================================================================
def get_phi(x, node_i):
	r""" Calculates the phi-function $\phi_i(\vec x)$ of node_i at the positions given by x.
	
	The participating nodes are found via L{Node.isa_partition<ZIBMolPy.node.Node.isa_partition>}
	@type x: L{InternalCoordinate}
	@type node_i: L{Node}
	@rtype: 1D numpy.ndarray of length x.n_frames
	""" 	
	nodes = node_i.pool.where("isa_partition")
	return(1/ np.sum( np.exp(-node.pool.alpha*( (x - node.internals).norm2() - (x - node_i.internals).norm2() ) ) for node in nodes))


#===============================================================================
# unstable version
#def get_phi(x, node_i):
#	r""" Calculates the phi-function $\phi_i(\vec x)$ of node_i at the positions given by x.
#	
#	The participating nodes are found via L{Node.isa_partition<ZIBMolPy.node.Node.isa_partition>}
#	@type x: L{InternalCoordinate}
#	@type node_i: L{Node}
#	@rtype: 1D numpy.ndarray of length x.n_frames
#	""" 	
#	return( get_phi_num(x, node_i) / get_phi_denom( x, node_i.pool.where("isa_partition") ) )
	

def get_phi_num(x, node_i):
	r""" Calculates the numerator $\chi_i(\vec x)$ of the phi-function of node_i at the positions given by x.
	@type x: L{InternalCoordinate}
	@type node_i: L{Node}
	@rtype: 1D numpy.ndarray of length x.n_frames	
	""" 
	return( np.exp(-node_i.pool.alpha*( (x - node_i.internals).norm2() ) ) )


def get_phi_denom(x, nodes):
	r""" Calculates the denominator $\sum_i \chi_i(\vec x)$ of the phi-function.
	
	This is the sum over the numerators of the given nodes at the positions given by x. 
	@type x: L{InternalCoordinate}
	@param nodes: these are sumed over
	@type nodes: list of L{Node} objects
	@rtype: 1D numpy.ndarray of length x.n_frames	
	"""
	return( np.sum( get_phi_num(x, node) for node in nodes) )


#===============================================================================
def get_phi_contrib(x_k, node_i, coord_k):
	r""" Calculates the phi-function $\phi_i(\vec x)$ 
	with $\vec x = (q_1, \dots, q_{k-1}, x_k, q_{k+1}, \dots, q_{n})$
	
	Where $\vec q_i = (q_1,\dots, q_n)$ denotes the components of the position of node_i.
	@type x_k: 1D numpy.ndarray
	@type node_i: L{Node}
	@type coord_k: L{InternalCoordinate}
	@rtype: 1D numpy.ndarray of length x_k.size
	"""
	
	all_nodes = node_i.pool.where("isa_partition")
	other_nums = [ get_phi_num_contrib(x_k, node_i, n, coord_k) for n in all_nodes ]
	

	a=node_i.pool.alpha*np.square(coord_k.sub(x_k, node_i.internals.getcoord(coord_k)))
	other_nums=np.add(other_nums,a)
	other_nums=np.exp(other_nums)

	denom = np.sum(other_nums, axis=0)	
	return( 1 / denom )

# old method - not in use
#~ def get_phi_num_contrib(x_k, node_i, node_j, coord_k):
	#~ #TODO: implement InternalArray.__setslice__ and use norm2() instead
	#~ r"""  Calculates the numerator $\chi_j(\vec x)$ of the phi-function of node_j
	#~ at $\vec x = (q_1, \dots, q_{k-1}, x_k, q_{k+1}, \dots, q_{n})$
		#~ 
	#~ Where $\vec q_i = (q_1,\dots, q_n)$ denotes the components of the position of node_i.
	#~ @type x_k: 1D numpy.ndarray
	#~ @param node_i: reference node
	#~ @type node_i: L{Node}
	#~ @type node_j: L{Node}
	#~ @type coord_k: L{InternalCoordinate}
	#~ @rtype: 1D numpy.ndarray of length x_k.size
	#~ """
	#~ 
	#~ assert(x_k.ndim == 1)
	#~ 
	#~ diffs = node_i.internals - node_j.internals
	#~ diffs[:, coord_k] = 0  #this will be counted in diff2
	#~ diff1 = diffs.norm2()
	#~ 
	#~ #calc result for coodinate coord
	#~ diff2 = np.square(coord_k.sub(x_k, node_j.internals.getcoord(coord_k)))
	#~ #add those two and take advantage of broadcasting
	#~ diff12 = diff1 + diff2 #using broadcasting
	#~ return( np.exp( -node_j.pool.alpha * diff12 ) )

def get_phi_num_contrib(x_k, node_i, node_j, coord_k):
	#TODO: implement InternalArray.__setslice__ and use norm2() instead
	r"""  Calculates the numerator $\chi_j(\vec x)$ of the phi-function of node_j
	at $\vec x = (q_1, \dots, q_{k-1}, x_k, q_{k+1}, \dots, q_{n})$
		
	Where $\vec q_i = (q_1,\dots, q_n)$ denotes the components of the position of node_i.
	@type x_k: 1D numpy.ndarray
	@param node_i: reference node
	@type node_i: L{Node}
	@type node_j: L{Node}
	@type coord_k: L{InternalCoordinate}
	@rtype: 1D numpy.ndarray of length x_k.size
	"""
	
	assert(x_k.ndim == 1)
	
	diffs = node_i.internals - node_j.internals
	diffs[:, coord_k] = 0  #this will be counted in diff2
	diff1 = diffs.norm2()
	
	#calc result for coodinate coord
	diff2 = np.square(coord_k.sub(x_k, node_j.internals.getcoord(coord_k)))
	#add those two and take advantage of broadcasting
	diff12 = diff1 + diff2 #using broadcasting
	return( -node_j.pool.alpha * diff12 )

#===============================================================================
# numerically problematic variant
#def get_phi_potential(x, node_i):
#	r""" Calculates $-\beta^{-1} \log \phi_i(\vec x)$, 
#	where $\beta$ is L{Pool.thermo_beta<ZIBMolPy.pool.Pool.thermo_beta>} 
#	@type x: L{InternalArray}
#	@type node_i: L{Node}
#	@rtype: 1D numpy.ndarray of length x.n_frames
#	"""
#	return( -1/node_i.pool.thermo_beta*np.nan_to_num(np.log(get_phi(x, #node_i))))

def get_phi_potential(x, node_i):
#	r""" Calculates $-\beta^{-1} \log \phi_i(\vec x)$, 
#	where $\beta$ is L{Pool.thermo_beta<ZIBMolPy.pool.Pool.thermo_beta>} 
#	@type x: L{InternalArray}
#	@type node_i: L{Node}
#	@rtype: 1D numpy.ndarray of length x.n_frames
#	"""
	all_nodes = node_i.pool.where("isa_partition")

	
	other_nums=  [ -node.pool.alpha*( (x - node.internals).norm2() - (x - node_i.internals).norm2() )  for node in all_nodes ]

	# N=amount of nodes
	# usually x_j is given as an array with 360 entries. 
	# other_nums consist then of N arrays each of size 360 
	# if you imagine other_nums as a matrix with 360 columns and N rows,
	# then max_value[j] gives you the maximum of the j-column of the matrix
	max_value = np.max(other_nums,axis=0)
	for i in range(len(other_nums)):
		for j in range(len(max_value)):
			other_nums[i][j]=np.add(other_nums[i][j],-max_value[j])

	other_nums=np.exp(other_nums)

	denom = np.sum(other_nums, axis=0)

	
	return( -1/node_i.pool.thermo_beta*(-max_value-np.log(denom)))

# numerically problematic variant
#def get_phi_contrib_potential(x_j, node_i, coord_k):
#	r""" Calculates $\beta^{nuj-1} \log $ L{get_phi_contrib}(x_j, node_i, coord_k),
#	where $\beta$ is L{Pool.thermo_beta<ZIBMolPy.pool.Pool.thermo_beta>}
#	@type x_j: 1D numpy.ndarray
#	@type node_i: L{Node}
#	@type coord_k: L{InternalCoordinate}
#	@rtype: 1D numpy.ndarray if length x_j.size
#	"""
#	return( -1/node_i.pool.thermo_beta*np.nan_to_num(np.log(get_phi_contrib(x_j, node_i, coord_k))))


def get_phi_contrib_potential(x_j, node_i, coord_k):
	r""" Calculates $\beta^{-1} \log $ L{get_phi_contrib}(x_j, node_i, coord_k),
	where $\beta$ is L{Pool.thermo_beta<ZIBMolPy.pool.Pool.thermo_beta>}
	@type x_j: 1D numpy.ndarray
	@type node_i: L{Node}
	@type coord_k: L{InternalCoordinate}
	@rtype: 1D numpy.ndarray if length x_j.size
	"""
	assert(x_j.ndim == 1)
	
	a=node_i.pool.alpha*np.square(coord_k.sub(x_j, node_i.internals.getcoord(coord_k)))
	
	all_nodes = node_i.pool.where("isa_partition")
	other_nums = [ get_phi_num_contrib(x_j, node_i, n, coord_k) for n in all_nodes ]
	
	other_nums=np.add(other_nums,a)
	
	# N=amount of nodes
	# usually x_j is given as an array with 360 entries. 
	# other_nums consist then of N arrays each of size 360 
	# if you imagine other_nums as a matrix with 360 columns and N rows,
	# then max_value[j] gives you the maximum of the j-column of the matrix
	max_value = np.max(other_nums,axis=0)

	for i in range(len(other_nums)):
		for j in range(len(max_value)):
			other_nums[i][j]=np.add(other_nums[i][j],-max_value[j])

	other_nums=np.exp(other_nums)
	denom = np.sum(other_nums, axis=0)
	
	return( -1/node_i.pool.thermo_beta*(-max_value-np.log(denom)))


#EOF
