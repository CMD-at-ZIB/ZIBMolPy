#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============

bla

How it works
============
	At the command line, type::
		$ zgf_export_nodes

"""

from ZIBMolPy.pool import Pool
from ZIBMolPy.ui import OptionsList, Option

import sys


#===============================================================================
options_desc = OptionsList([
	Option("o", "outfile", "file", default="pool.out"),
])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return( pool.where("isa_partition and state != 'mdrun-failed'") > 0 )

	
#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]

	outfile = open(options.outfile,"w")
	
	pool = Pool()
	needy_nodes = pool.where("isa_partition and state not in ('refined','mdrun-failed')")
	
	for n in needy_nodes:
		outfile.write("%s, state: '%s':\n"%(n.name,n.state))
		outfile.write(str(n.internals.array)+"\n")
		outfile.write("mean pot.: %f, std pot.: %f, free energy estimate: %f\n"%(n.obs.mean_V,n.obs.std_V,n.obs.A))
		outfile.write("#========================================================================#\n")

	outfile.close()
	print "Pool info was written to %s."%options.outfile


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

