#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	
	This tool will prepare desolvated trajectories and topologies in order to allow energy reruns for your molecule of interest (MOI).
	Your node samplings can then be rerun with L{zgf_mdrun}. After the rerun is complete, the rerun energies can be used by L{zgf_reweight}.

How it works
============
	At the command line, type::
		$ zgf_rerun [options]

"""

from ZIBMolPy.ui import Option, OptionsList
from ZIBMolPy.pool import Pool

from subprocess import Popen, PIPE
import zgf_grompp

import sys
import re
from os import path

options_desc = OptionsList([
	Option("c", "ignore-convergence", "bool", "rerun despite not-converged", default=False),
	Option("p", "pbc-removal", "choice", "method of pbc removal for desolvation", choices=("whole", "mol", "nojump", "none")),
	Option("g", "grompp", "file", extension="mdp", default="rerun.mdp"),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return( len(pool) > 1 and len(pool.where("isa_partition and state in ('converged','not-converged','mdrun-failed')")) == len(pool.where("isa_partition")) )


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
		# desolvate trr
		if not( path.exists(node.dir+"/rerun_me.trr") ):
			cmd = ["trjconv", "-f", node.trr_fn, "-o", node.dir+"/rerun_me.trr", "-s", node.tpr_fn, "-n", node.pool.ndx_fn, "-pbc", options.pbc_removal]			
			print("Calling: "+(" ".join(cmd)))
			p = Popen(cmd, stdin=PIPE)
			p.communicate(input=("MOI\n"))
			assert(p.wait() == 0)

		# desolvate pdb
		if not( path.exists(node.dir+"/rerun_me.pdb") ):
			cmd = ["trjconv", "-f", node.pdb_fn, "-o", node.dir+"/rerun_me.pdb", "-s", node.tpr_fn, "-n", node.pool.ndx_fn, "-pbc", options.pbc_removal]			
			print("Calling: "+(" ".join(cmd)))
			p = Popen(cmd, stdin=PIPE)
			p.communicate(input=("MOI\n"))
			assert(p.wait() == 0)

		# desolvate topology
		infile = open(node.top_fn, "r").readlines()
		mol_section = False
		out_top = []

		for line in infile:
			if( re.match("\s*\[\s*(molecules)\s*\]\s*", line.lower()) ):
				# we are past the "molecules" section
				mol_section = True
			if(mol_section):
				# comment out lines that belong to solvent (SOL, CL, NA)... add more if necessary
				if( re.match("\s*(sol|cl|na|tsl|tcm|mth)\s*\d+", line.lower()) ):
					line = ";"+line
			out_top.append(line)
		outfile = open(node.dir+"/rerun_me.top","w").writelines(out_top)	

		grompp2state = "rerun-able-"+node.state

		# get rid of old checkpoint file (it might mess up the rerun)
		if( path.exists(node.dir+"/state.cpt") ):
			os.remove(node.dir+"/state.cpt")

		#zgf_grompp.call_grompp(node, mdp_file=options.grompp, final_state=grompp2state)
		#TODO code borrowed from zgf_grompp
		#TODO make the original method fit for grompping reruns
		cmd = ["grompp"]
		cmd += ["-f", "../../"+options.grompp]
		cmd += ["-n", "../../"+node.pool.ndx_fn]
		cmd += ["-c", "../../"+node.dir+"/rerun_me.pdb"]
		cmd += ["-p", "../../"+node.dir+"/rerun_me.top"]
		cmd += ["-o", "../../"+node.dir+"/rerun_me.tpr"]			
		print("Calling: %s"%" ".join(cmd))
		p = Popen(cmd, cwd=node.dir)
		retcode = p.wait()
		assert(retcode == 0) # grompp should never fail
		node.state = grompp2state
		node.save()

		node.unlock()


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

