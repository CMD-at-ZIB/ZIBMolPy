#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============

In order to give you an idea what your metastable clusters look like, this tool picks out the nodes that represent your clusters "best".
A better (but more time-consuming) way to evaluate the clusters is to use L{zgf_extract_conformations}.

How it works
============
	At the command line, type::
		$ zgf_show_cluster_representatives

"""

from ZIBMolPy.ui import OptionsList
from ZIBMolPy.node import Node
from ZIBMolPy.pool import Pool

import numpy as np
import sys
from os import path

options_desc = OptionsList()

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc
	
def is_applicable():
	pool = Pool()
	return( path.exists(pool.chi_mat_fn) )


#===============================================================================
def main():
	
	pool = Pool()

	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']
	node_names = npz_file['node_names']

	argmax_chi = np.argmax(chi_matrix, axis=0)
	
	for (ni, n) in enumerate( Node(nn) for nn in node_names[argmax_chi] ):
		print "Cluster %d is represented by node %s (%s)."%(ni+1, n.name, str(n.internals.array))


	#TODO make option to open all cluster representatives as molecules in VMD


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
