#!/usr/bin/python
# -*- coding: utf-8 -*-

""" """ #TODO

from ZIBMolPy.internals import DihedralCoordinate, LinearCoordinate
from ZIBMolPy.utils import get_phi_contrib, get_phi_contrib_potential
from ZIBMolPy.algorithms import kmeans
from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.restraint import DihedralRestraint, DistanceRestraint
from ZIBMolPy.ui import userinput, Option, OptionsList
from ZIBMolPy.io.trr import TrrFile
import zgf_cleanup

import sys
import os
from pprint import pformat
from datetime import datetime
from tempfile import mktemp
from subprocess import Popen, PIPE
import numpy as np


# ZIBgridfree quasi-constant parameters
EPSILON2 = 1E-3

#PLATEAU_THRESHOLD = 0.001
PLATEAU_THRESHOLD = 0.02   # for phifit 'switch': smaller value = smaller plateaus
PLATEAU_BREAK = (np.pi/180)*2 # for phifit 'switch': change in dihedral that breaks plateau

# fun parameters
THE_BIG_NUMBER = 99999.0 # is measured in [Chuck]

#===============================================================================
options_desc = OptionsList([
#	Option("N", "methodnodes", "choice", "method to determine nodes", choices=("kmeans","equidist", "all")),
#	Option("A", "methodalphas", "choice", "method to determine alphas", choices=("theta", "user") ),
	Option("K", "numnodes", "int", "number of nodes to create", default=10, min_value=1),
#	Option("E", "ext-max", "int", "max. number of extensions if not converged", default=5, min_value=0),
#	Option("L", "ext-length", "int", "length per extension in ps", default=100, min_value=1),
#	Option("P", "methodphifit", "choice", "method to determine phi fit", choices=("switch", "harmonic", "leastsq") ),
	Option("p", "parent-node", "node", "parent-node"),
#	Option("w", "write-preview", "bool", "write frames of new nodes as pdb-trajectory", default=False),
#	Option("s", "random-seed", "str", "seed for random number generator"),
	
])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc


def is_applicable():
	pool = Pool()
	return( len(pool)>0 )

#===============================================================================
# This method is also called from zgf_refine
def main(argv=None):
	if(argv==None): 
		argv = sys.argv
		options = options_desc.parse_args(argv)[0]
	
	pool = Pool()
	
	found_parents = [n for n in pool if n.name == options.parent_node]
	assert(len(found_parents) == 1)
	parent = found_parents[0]
			
	print "parent trr length: ", parent.trajectory.n_frames
	chosen_idx = range(0, parent.trajectory.n_frames, 2)
	print "choosen_idx: ",chosen_idx
	
	for i in chosen_idx:
		n = Node()
		n.parent_frame_num = i
		n.parent = parent
		n.state = "created"
		n.extensions_counter = 0
		n.extensions_max = 0
		n.extensions_length = 0
		n.internals = parent.trajectory.getframe(i)
		pool.append(n)
		n.save()
	
#==========================================================================
if(__name__=="__main__"):
	main()

#EOF

