#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============

This optional tool adds a number of ions specified by the user to nodes with state 'em-mdrun-able' by calling the Gromacs tool genion.

The node topologies will be updated accordingly. Finally, L{zgf_grompp} will be called in order to compile a new tpr-file.

B{The next step is L{zgf_mdrun}, or L{zgf_submit_job_HLRN}, if you are working on HLRN.}

How it works
============
	At the command line, type::
		$ zgf_genion

"""


from ZIBMolPy.pool import Pool
from ZIBMolPy.ui import OptionsList, Option

import sys
import re
from subprocess import Popen, PIPE
import numpy as np
import shutil

import zgf_solvate_nodes
import zgf_grompp


#===============================================================================
options_desc = OptionsList([
	Option("p", "np", "int", "Number of positive ions", default=0, min_value=0),
	Option("P", "pname", "str", "Name of the positive ion", default="NA"),
	Option("n", "nn", "int", "Number of negative ions", default=0, min_value=0),
	Option("N", "nname", "str", "Name of the negative ion", default="CL"),
	Option("s", "random-seed", "str", "Seed for random number generator", default="1993"),
])

# reuse option from zgf_solvate_nodes
options_desc.append(zgf_solvate_nodes.options_desc["grompp"]) 

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return(len(pool.where("state == 'em-mdrun-able'")) > 0)

	
#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	pool = Pool()
	needy_nodes = pool.where("state == 'em-mdrun-able'")
	assert(len(needy_nodes) == len(needy_nodes.multilock())) # make sure we lock ALL nodes


	# add ions to simulation boxes
	call_genion(pool, options.np, options.pname, options.nn, options.nname, options.random_seed)

	
	for n in needy_nodes:
		n.state = "em-grompp-able"
		zgf_grompp.call_grompp(n, mdp_file=options.grompp, final_state="em-mdrun-able") # re-grompp to get a tpr for energy minimization
		n.unlock()


#===============================================================================
def call_genion(pool, np, pname, nn, nname, random_seed):
	
	for n in pool.where("state == 'em-mdrun-able'"):

		cmd = ["genion", "-s", n.tpr_fn, "-o", n.pdb_fn, "-p", n.top_fn, "-np", str(np), "-pname", pname, "-nn", str(nn), "-nname", nname, "-seed", random_seed, "-g", n.dir+"/genion.log" ]
		print("Calling: %s"%" ".join(cmd))
		p = Popen(cmd, stdin=PIPE)
		p.communicate(input=("SOL\n"))
		assert(p.wait() == 0)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

