#!/usr/bin/python
# -*- coding: utf-8 -*-

""" """ #TODO


from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.ui import userinput, Option, OptionsList

import sys
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
	Option("K", "numnodes", "int", "number of nodes to create", default=4, min_value=1),
	Option("p", "parent-node", "node", "parent-node"),
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
			
	
	
	chosen_idx = np.linspace(start=0, stop=parent.trajectory.n_frames-1, num=options.numnodes).astype(int) 
	
	print "choosen_idx: ",chosen_idx
	
	for i in chosen_idx:
		n = Node()
		n.parent_frame_num = i
		n.parent = parent
		n.state = "created"
		n.extensions_counter = 0
		n.extensions_max = 0
		n.extensions_length = 0
		n.sampling_length = parent.sampling_length * 3
		n.internals = parent.trajectory.getframe(i)
		pool.append(n)
		n.save()
	
#==========================================================================
if(__name__=="__main__"):
	main()

#EOF

