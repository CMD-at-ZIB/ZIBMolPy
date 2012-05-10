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
	return(len(pool.where("state == 'grompp-able'")) > 0 or len(pool.where("state == 'em-grompp-able'")) > 0)

#===============================================================================
def main():
	pool = Pool()

	if(len(pool.where("state == 'grompp-able'")) > 0):
		call_grompp(pool)
		
	if(len(pool.where("state == 'em-grompp-able'")) > 0):
		assert(path.exists("em.mdp")) #TODO that's not super nice yet
		call_grompp(pool, mode='em')



	#needy_nodes = pool.where("state == 'grompp-able'").multilock()
		
	#try:
	#	for n in needy_nodes:
	#		cmd = ["grompp"]
	#		cmd += ["-f", "../../"+n.mdp_fn]
	#		cmd += ["-n", "../../"+pool.ndx_fn]
	#		cmd += ["-c", "../../"+n.pdb_fn]
	#		cmd += ["-p", "../../"+n.top_fn]
	#		cmd += ["-o", "../../"+n.tpr_fn]			
	#		print("Calling: %s"%" ".join(cmd))
	#		p = Popen(cmd, cwd=n.dir)
	#		retcode = p.wait()
	#		assert(retcode == 0) # grompp should never fail
	#		n.state = "mdrun-able"
	#		n.save()
	#except:
	#	traceback.print_exc()

	#for n in needy_nodes:
	#	n.unlock()


#===============================================================================
def call_grompp(pool, mode='run'):
	try:
		if(mode =='run'):
			needy_nodes = pool.where("state == 'grompp-able'").multilock()
			final_state = "mdrun-able"
		elif(mode =='em'):
			needy_nodes = pool.where("state == 'em-grompp-able'").multilock()
			final_state = "em-mdrun-able"
		else:
			raise(Exception("Unknown grompp mode: "+mode))

		for n in needy_nodes:
			cmd = ["grompp"]
			if(mode =='run'):
				cmd += ["-f", "../../"+n.mdp_fn]
			elif(mode =='em'):
				cmd += ["-f", "../../em.mdp"] #TODO that's not super nice yet
			cmd += ["-n", "../../"+pool.ndx_fn]
			cmd += ["-c", "../../"+n.pdb_fn]
			cmd += ["-p", "../../"+n.top_fn]
			cmd += ["-o", "../../"+n.tpr_fn]			
			print("Calling: %s"%" ".join(cmd))
			p = Popen(cmd, cwd=n.dir)
			retcode = p.wait()
			assert(retcode == 0) # grompp should never fail
			n.state = final_state
			n.save()

		for n in needy_nodes:
			n.unlock()
	except:
		traceback.print_exc()
	

#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

