#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the fourth step of ZIBgridfree.}

	This tool will run grompp for every node, using the mdp file given to L{zgf_create_pool}. It will fail if grompp produces an error. You should also watch out for any NOTE that grompp may have for you.

	B{The next step is L{zgf_mdrun}, or L{zgf_submit_job_HLRN}, if you are working on HLRN.}

How it works
============
	At the command line, type::
		$ zgf_grompp

"""
from ZIBMolPy.ui import OptionsList
from ZIBMolPy.pool import Pool

from subprocess import Popen
import traceback
import sys
from os import path


options_desc = OptionsList()

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return(len(pool.where("state == 'grompp-able'")) > 0)

#===============================================================================
def main():
	pool = Pool()
	needy_nodes = pool.where("state == 'grompp-able'").multilock()
		
	try:
		for n in needy_nodes:
			call_grompp(n)			
	except:
		traceback.print_exc()

	for n in needy_nodes:
		n.unlock()


#===============================================================================
# this method is called by zgf_solvate_nodes, zgf_genion, and zgf_mdrun
def call_grompp(node, mdp_file="", final_state="mdrun-able"):
	
	cmd = ["grompp"]
	
	mdp_fn = node.mdp_fn
	if(mdp_file):
		mdp_fn = mdp_file

	cmd += ["-f", "../../"+mdp_fn]
	cmd += ["-n", "../../"+node.pool.ndx_fn]
	cmd += ["-c", "../../"+node.pdb_fn]
	cmd += ["-p", "../../"+node.top_fn]
	cmd += ["-o", "../../"+node.tpr_fn]			
	print("Calling: %s"%" ".join(cmd))
	p = Popen(cmd, cwd=node.dir)
	retcode = p.wait()
	assert(retcode == 0) # grompp should never fail
	node.state = final_state
	node.save()


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

