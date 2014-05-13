#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
What it does
============

This tool concatenates trr and edr files for unrestrained nodes as well as multistart nodes.
Please note: This functionality has also been integrated into zgf_mdrun. This tool is merely meant to provide this function for older node pools.

How it works
============
	At the command line, type::
		$ zgf_concatentate_stuff

"""

from ZIBMolPy.utils import check_call
from ZIBMolPy.pool import Pool
from ZIBMolPy.ui import Option, OptionsList
from ZIBMolPy.io.trr import TrrFile

import sys
import os
import re
import numpy as np

from subprocess import Popen, PIPE

options_desc = OptionsList([
	Option("t", "trr", "bool", "concatenate trr files", default=False),
	Option("e", "edr", "bool", "concatenate edr files", default=False),
])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return( len(pool.where("state == 'merge-able'")) > 0 )

#===============================================================================
def main():

	options = options_desc.parse_args(sys.argv)[0]
	pool = Pool()

	needy_nodes = pool.where("state == 'merge-able'").multilock()

	if(len(needy_nodes) == 0):
		return
	
	# find out about trr time step
	dt = 0	
	for fn in os.listdir(needy_nodes[0].dir):
		if re.match("^node.+run\d+\.trr", fn):
			trr = TrrFile(needy_nodes[0].dir+"/"+fn)			
			dt = trr.first_frame.next().t - trr.first_frame.t
			trr.close()
			break

	# dt is sometimes noisy in the final digits (three digits is femtosecond step = enough)
	dt = np.around(dt, decimals=3)
	
	for n in needy_nodes:

		if(options.trr):
			# merge sampling trajectories
			trr_fns = sorted([ fn for fn in os.listdir(n.dir) if re.match("[^#].+run\d+.trr", fn) ])
			cmd = ["trjcat", "-f"]
			cmd += trr_fns
			cmd += ["-o", "../../"+n.trr_fn, "-cat"]
			print("Calling: %s"%" ".join(cmd))
			check_call(cmd, cwd=n.dir)

		if(options.edr):
			# merge edr files
			# get list of edr-files
			edr_fnames = sorted([n.dir+"/"+fn for fn in os.listdir(n.dir) if re.match("[^#].+run\d+.edr", fn)])
			assert( len(edr_fnames) ==  n.extensions_counter+1 )
			assert( len(edr_fnames) ==  n.extensions_max+1 )

			time_offset = n.sampling_length+dt

			for edr_fn in edr_fnames[1:]:	
				# adapt edr starting times
				cmd = ["eneconv", "-f", edr_fn, "-o", edr_fn, "-settime"]
				print("Calling: "+(" ".join(cmd)))
				p = Popen(cmd, stdin=PIPE)
				p.communicate(input=(str(time_offset)+"\n"))
				assert(p.wait() == 0)

				time_offset += n.extensions_length+dt

			# concatenate edr files with adapted starting times
			cmd = ["eneconv", "-f"] + edr_fnames + ["-o", n.dir+"/ener.edr"]
			print("Calling: "+(" ".join(cmd)))
			p = Popen(cmd)
			retcode = p.wait()
			assert(retcode == 0)

	needy_nodes.unlock()


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
