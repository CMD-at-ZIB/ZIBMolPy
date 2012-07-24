#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============

This optional tool will use trjconv to remove everything except group "MOI" from the node sampling trajectories. Periodic boundary conditions will not be treated. It is meant to save disk space and gain speed in data handling after the sampling of the node pool is concluded.

The tool should not be used if you plan on doing further node refinement. 

B{The next step is L{zgf_grompp}. Afterwards, ions can be added by using L{zgf_genion}.}

How it works
============
	At the command line, type::
		$ zgf_discard_solvent

"""

from ZIBMolPy.ui import userinput, Option, OptionsList
from ZIBMolPy.pool import Pool, NodeList

from subprocess import Popen, PIPE
from tempfile import mktemp
from os import path
import traceback
import sys
import os


options_desc = OptionsList([
	Option("c", "ignore-convergence", "bool", "discard solvent despite not-converged", default=False),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return( len(pool) > 1  and len(pool.where("is_sampled")) == len(pool) )


#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	pool = Pool()
	
	choice = "state in ('converged', 'refined')"
	if(options.ignore_convergence):
		choice = "state in ('converged', 'not-converged', 'refined')"	

	needy_nodes = NodeList([n for n in pool.where(choice) if not n == pool.root]) # we won't touch the root

	if not(userinput("Once the solvent has been removed, further refinement of the pool is not possible. Continue?", "bool")):
		sys.exit("Quit by user.")
		
	assert(len(needy_nodes) == len(needy_nodes.multilock())) # make sure we lock ALL nodes

	try:
		for n in needy_nodes:	
			discard_solvent(n, "pdb")
			discard_solvent(n, "trr")

		for n in needy_nodes:
			n.unlock()
	except:
		traceback.print_exc()


#===============================================================================
def discard_solvent(node, format):
	if(format == "pdb"):
		in_fn = node.pdb_fn
		tmp_out_fn = mktemp(suffix=".pdb", dir=node.dir)
	elif(format == "trr"):
		in_fn = node.trr_fn
		tmp_out_fn = mktemp(suffix=".trr", dir=node.dir)
	else:
		raise(Exception("Format unknown: "+format))

	cmd = ["trjconv", "-f", in_fn, "-o", tmp_out_fn, "-s", node.tpr_fn, "-n", node.pool.ndx_fn]			

	print("Calling: "+(" ".join(cmd)))
	p = Popen(cmd, stdin=PIPE)
	p.communicate(input=("MOI\n"))
	assert(p.wait() == 0)

	assert( path.exists(tmp_out_fn) and path.getsize(tmp_out_fn) ), "output file should exist and be non-empty"

	# discard/overwrite original file (may only work on Unix)
	os.rename(tmp_out_fn, in_fn)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

