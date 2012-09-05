#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	
	Bla

How it works
============
	At the command line, type::
		$ zgf_rerun [options]

"""

from ZIBMolPy.ui import Option, OptionsList
from ZIBMolPy.pool import Pool

import zgf_grompp

import sys

options_desc = OptionsList([
	Option("c", "ignore-convergence", "bool", "reweight despite not-converged", default=False),
	Option("g", "grompp", "file", extension="mdp", default="rerun.mdp"),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return( len(pool) > 1  and len(pool.where("is_sampled")) == len(pool) )


#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	pool = Pool()

	if options.ignore_convergence:
		needy_nodes = pool.where("state in ('converged','not-converged')")
	else:
		needy_nodes = pool.where("state == 'converged'")

	assert(len(needy_nodes) == len(needy_nodes.multilock())) # make sure we lock ALL nodes

	for node in needy_nodes:
		grompp2state = "rerun-able-"+node.state
		zgf_grompp.call_grompp(node, mdp_file=options.grompp, final_state=grompp2state)
		node.unlock()


#===============================================================================
if(__name__ == "__main__"):
	main()


#EOF
