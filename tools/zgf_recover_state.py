#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============

This tool recovers all nodes that are currently in state 'current-state' (to be specified by the user, e.g 'mdrun-failed') to the state 'recover-state' (likewise to be specified by the user, e.g. 'mdrun-able').

How it works
============
	At the command line, type::
		$ zgf_recover_state

"""


from ZIBMolPy.pool import Pool
from ZIBMolPy.ui import Option, OptionsList

import zgf_cleanup

import sys

options_desc = OptionsList([
	Option("c", "current-state", "choice", "current state of nodes to recover", choices=("mdrun-failed", "ready", "converged", "not-converged")),
	Option("r", "recover-state", "choice", "state that is to be recovered", choices=("mdrun-able", "em-mdrun-able", "converged", "not-converged", "ready")),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	return( True )

#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	zgf_cleanup.main()

	pool = Pool()

	needy_nodes = pool.where("state == '%s'"%options.current_state).multilock()

	for n in needy_nodes:
		print "Recovering node %s with state %s to state %s ..."%(n.name, n.state, options.recover_state)
		n.state = options.recover_state
		n.save()		
		n.unlock()


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
