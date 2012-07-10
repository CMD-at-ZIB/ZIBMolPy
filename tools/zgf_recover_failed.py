#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============

This tool recovers nodes with state 'mdrun-failed' to a state specified by the user.

How it works
============
	At the command line, type::
		$ zgf_recover_failed

"""


from ZIBMolPy.pool import Pool
from ZIBMolPy.ui import Option, OptionsList

import zgf_cleanup

import sys

options_desc = OptionsList([
	Option("r", "recover-state", "choice", "node state to recover", choices=("mdrun-able", "em-mdrun-able")),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return( len(pool.where("state == 'mdrun-failed'")) > 0 )

#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	zgf_cleanup.main()

	pool = Pool()

	needy_nodes = pool.where("state == 'mdrun-failed'").multilock()

	for n in needy_nodes:
		print "Recovering node %s with state %s to state %s ..."%(n.name, n.state, options.recover_state)
		n.state = options.recover_state
		n.save()		
		n.unlock()


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
