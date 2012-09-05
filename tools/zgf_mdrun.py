#!/usr/bin/python -u
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the fifth step of ZIBgridfree.}

	This tool is a worker script that will process a pool of 'mdrun-able' nodes in node-wise manner. If the script finds a node that is not locked, it will lock the node and process it by initiating a sampling with Gromacs mdrun. After the sampling is finished, the worker will check for convergence by applying the Gelman-Rubin (GR) convergence criterion to the timeseries of internal coordinates. If all internal coordinates satisfy the GR criterion, the node does not need further processing and will be filed as 'converged'. If one or more internal coordinates do not satisfy the GR criterion, the node will remain in state 'mdrun_able' for further processing. If the node has already exceeded the maximum number of sampling extensions, it will be filed as 'not-converged'. Finally, the node will be unlocked.

	The sampling progress and current node status can be monitored with L{zgf_browser}.

	Note that several workers can process the same node pool simultaneously.
	
	B{The next step is L{zgf_refine}, if you want to refine or extend nodes where convergence has not been achieved. Otherwise, you can proceed with L{zgf_reweight}.}

How it works
============
	At the command line, type::
		$ zgf_mdrun [options]

Stale node locks
================
	If a worker process hits the wall time while it is sampling a certain node, or the sampling crashes for some unforeseen reason, B{the affected node will remain in a locked state} ("stale node lock"). While the node lock remains, the affected node cannot be sampled by another worker process. If you encounter a stale node lock, you can use L{zgf_cleanup} to have it removed. Afterwards, normal processing of the node can be resumed.

Convergence
===========
	Information about the convergence properties of individual internal coordinates can be found in the convergence log file named 'node0042_convergence.log' stored in the node directory. B{Note that convergence as indicated by the GR criterion does not necessarily mean that the sampling is sufficient}. If, at the end of the day, not all of the nodes in the pool have converged, you can use L{zgf_browser} to get an impression where convergence was not achieved. Generally, if a node is situated in a transition region, convergence may not be achieved at all and refinement is the only option.

Automatic refinement
====================
	If you use this option, L{zgf_mdrun} will automatically call L{zgf_refine} at most n times (where n is an option specified by you) in order to resolve nodes that have not converged. Refinement is performed using default parameters from L{zgf_create_nodes}.

Nodes with state "mdrun-failed"
===============================
	If something goes wrong during the sampling of a node, it will adapt the state "mdrun-failed". After the problem is resolved (see below), you have to recover the node back to state "mdrun-able" by calling the tool L{zgf_recover_failed}. Failed node samplings are often related to domain decomposition problems in systems with explicit solvent and L{linear coordinates<ZIBMolPy.internals>}:

		- B{Problem:} Domain decomposition does not fit number of nodes/PME nodes. B{Solution:} Change number of nodes/PME nodes, or change PME grid dimension, or use particle decomposition.
		- B{Problem:} Domain decomposition does not work due to (long) distance restraints (L{linear coordinates<ZIBMolPy.internals>}). B{Solution:} Change number of nodes/PME nodes, or change PME grid dimension, or use particle decomposition. Using particle decomposition and a relatively low number of processors per node (preferably sharing the same memory) works best in difficult cases.
		- B{Problem:} Unspecific crashes when L{linear coordinates<ZIBMolPy.internals>} are used. B{Solution:} Make periodic box bigger (at least double the size of the largest L{linear coordinate<ZIBMolPy.internals>}).

	A recovered node sampling will be resumed at the latest Gromacs checkpoint file (state.cpt).
"""

from ZIBMolPy.utils import check_call
from ZIBMolPy.pool import Pool
from ZIBMolPy.algorithms import gelman_rubin
from ZIBMolPy.ui import Option, OptionsList
from ZIBMolPy.io.trr import TrrFile

import zgf_refine
import zgf_grompp

from subprocess import call, Popen, PIPE
from warnings import warn
import traceback
import sys
import os
import re
import numpy as np

options_desc = OptionsList([ 
	Option("s", "seq", "bool", "Suppress MPI", default=False),
	Option("n", "np", "int", "Number of processors to be used for MPI", default=4, min_value=1),
	Option("t", "nt", "int", "Number of threads to start, 0 is guess", default=0, min_value=0),
	Option("p", "npme", "int", "Number of separate processors to be used for PME, -1 is guess", default=-1, min_value=-1),
	Option("r", "reprod", "bool", "Avoid mdrun optimizations that affect binary reproducibility", default=False),
	Option("d", "pd", "bool", "Use particle decomposition", default=False),
	Option("c", "convtest", "bool", "Test if nodes are converged - does not simulate", default=False),
	Option("a", "auto-refines", "int", "Number of automatic refinements", default=0, min_value=0),
	Option("m", "multistart", "bool", "Sampling is restarted instead of extended", default=False),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc


def is_applicable():
	pool = Pool()
	return(len(pool.where("state in ('em-mdrun-able', 'mdrun-able', 'converged', 'not-converged', 'rerun-able-converged', 'rerun-able-not-converged')")) > 0)
	

#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	pool = Pool()
	
	if(options.convtest):
		for n in pool.where("state in ('converged', 'not-converged')"):
			print("\n\nRunning Gelman-Rubin on %s"%n)
			conv_check_gelman_rubin(n)
		return # exit

	auto_refines_counter = 0
	while(True):		
		pool.reload()
		pool.reload_nodes()
		for n in pool:
			n.reload()

		active_node = None
		for n in pool.where("state in ('em-mdrun-able', 'mdrun-able', 'rerun-able-converged', 'rerun-able-not-converged')"):
			if(n.lock()):
				active_node = n
				break

		if(active_node == None):
			if(auto_refines_counter < options.auto_refines):
				auto_refines_counter += 1
				print("\n\nRunning 'zgf_refine --refine-all' for the %d time..."%auto_refines_counter)
				zgf_refine.main(["--refine-all"])
				continue
			else:
				break # we're done - exit
	
		try:
			process(active_node, options)
			active_node.save()
			active_node.unlock()
		except:
			active_node.state = "mdrun-failed"
			active_node.save()
			active_node.unlock()
			traceback.print_exc()
			continue
			

#===============================================================================
def process(node, options):
	
	cmd1 = ["mdrun"]
	cmd1 += ["-s", "../../"+node.tpr_fn]
	
	if(node.state == "em-mdrun-able"):
		cmd1 += ["-c", "../../"+node.pdb_fn]
		cmd1 += ["-o", "../../"+node.dir+"/em.trr"]
		cmd1 += ["-e", "../../"+node.dir+"/em.edr"]
		cmd1 += ["-g", "../../"+node.dir+"/em.log"]
	elif(node.state in ('rerun-able-converged','rerun-able-not-converged')):
		cmd1 += ["-c", "../../"+node.pdb_fn]
		cmd1 += ["-o", "../../"+node.dir+"/rerun.trr"]
		cmd1 += ["-e", "../../"+node.dir+"/rerun.edr"]
		cmd1 += ["-g", "../../"+node.dir+"/rerun.log"]
		cmd1 += ["-rerun", "../../"+node.trr_fn]
	else:
		cmd1 += ["-o", "../../"+node.trr_fn]

	cmd1 += ["-append", "-cpi", "state.cpt"] # continue previouly state, if exists
	if(options.npme != -1):
		cmd1 += ["-npme", str(options.npme)]
	if(options.nt != 0):
		cmd1 += ["-nt", str(options.nt)]
	if(options.reprod):
		cmd1 += ["-reprod"]
	if(options.pd):
		cmd1 += ["-pd"]
	
	# use mpiexec and mdrun_mpi if available
	if(not options.seq and call(["which","mpiexec"])==0):
		if(call(["which","mdrun_mpi"])==0):
			cmd1[0] = "mdrun_mpi"
		cmd1 = ["mpiexec", "-np", str(options.np)] + cmd1
		
	#http://stackoverflow.com/questions/4554767/terminating-subprocess-in-python
	#alternative
	#p = Popen(...)
	#pp = psutil.Process(p.pid)
	#for child in pp.get_children():
	#	child.send_signal(signal.SIGINT)
	
	#ensure, that childprocess dies when parent dies. Alternative: write own signal-handler e.g for atexit-module
	#http://stackoverflow.com/questions/1884941/killing-the-child-processes-with-the-parent-process
	implant_bomb = None
	try:
		import ctypes
		libc = ctypes.CDLL('libc.so.6')
		PR_SET_PDEATHSIG = 1; TERM = 15
		implant_bomb = lambda: libc.prctl(PR_SET_PDEATHSIG, TERM)
	except:
		warn("Child process might live on when parent gets terminated (feature requires python 2.6).")
	
	print("Calling: %s"%" ".join(cmd1))
	check_call(cmd1, cwd=node.dir, preexec_fn=implant_bomb)

	# if we were just rerunnning, we go back to original state now
	if(node.state == "em-mdrun-able"):
		node.state = "grompp-able"
		return

	# if we were just minimizing, we go back to grompp-able now
	if(node.state in ('rerun-able-converged','rerun-able-not-converged')):
		node.state = node.state.rsplit("rerun-able-", 1)[1]
		return

	if(node.has_restraints and not options.multistart):
		# check for convergence
		converged = conv_check_gelman_rubin(node)
	else:
		# stow away sampling data
		converged = False
		os.remove(node.dir+"/state.cpt")
		for fn in [node.trr_fn, node.dir+"/ener.edr", node.dir+"/md.log"]:
			archive_file(fn, node.extensions_counter)

	# decide what to do next
	if(converged):
		node.state = "converged"

	elif(node.extensions_counter >= node.extensions_max):
		if(node.has_restraints and not options.multistart):
			node.state = "not-converged"
		else:
			# merge sampling trajectories
			trr_fns = sorted([ fn for fn in os.listdir(node.dir) if re.match(".+run\d.trr", fn) ])
			cmd2 = ["trjcat", "-f"]
			cmd2 += trr_fns
			cmd2 += ["-o", "../../"+node.trr_fn, "-cat"]
			print("Calling: %s"%" ".join(cmd2))
			check_call(cmd2, cwd=node.dir)
			# merge edr files
			get_merged_edr(node)
			node.state = "ready"

	else:
		node.extensions_counter += 1
		node.state = "mdrun-able" # actually it should still be in this state
	
		if(node.has_restraints and not options.multistart):
			cmd0 = ["tpbconv", "-s", node.tpr_fn, "-o", node.tpr_fn, "-extend", str(node.extensions_length)]
			print("Calling: %s"%" ".join(cmd0))
			check_call(cmd0) # tell Gromacs to extend the tpr file for another round
		else:
			node.state = "grompp-able"
			zgf_grompp.call_grompp(node) # re-grompp to obtain new random impulse


#===============================================================================
def archive_file(fn, count):
	assert( os.path.exists(fn) )
	out_fn = fn.rsplit(".", 1)[0] + "_run" + str(count) + "." + fn.rsplit(".", 1)[1]
	os.rename(fn, out_fn)


#===============================================================================
def conv_check_gelman_rubin(node):
	frames = node.trajectory
	n_chains = node.pool.gr_chains
	threshold = node.pool.gr_threshold
	log = open(node.convergence_log_fn, "a")
	is_converged = gelman_rubin(frames, n_chains, threshold, log)
	log.close()
	return(is_converged)


#===============================================================================
def get_merged_edr(node):
	# get list of edr files
	edr_fnames = sorted([node.dir+"/"+fn for fn in os.listdir(node.dir) if re.search('.edr', fn)])
	assert( len(edr_fnames) ==  node.extensions_max+1 )

	# find out about trr time step
	trr = TrrFile(node.trr_fn)
	dt = trr.first_frame.next().t - trr.first_frame.t
	trr.close()
	# dt is sometimes noisy in the final digits (three digits is femtosecond step = enough)
	dt = np.around(dt, decimals=3)

	time_offset = node.sampling_length+dt

	for edr_fn in edr_fnames[1:]:	
		# adapt edr starting times
		cmd = ["eneconv", "-f", edr_fn, "-o", edr_fn, "-settime"]
		print("Calling: "+(" ".join(cmd)))
		p = Popen(cmd, stdin=PIPE)
		p.communicate(input=(str(time_offset)+"\n"))
		assert(p.wait() == 0)

		time_offset += node.extensions_length+dt

	# concatenate edr files with adapted starting times
	cmd = ["eneconv", "-f"] + edr_fnames + ["-o", node.dir+"/ener.edr"]
	print("Calling: "+(" ".join(cmd)))
	p = Popen(cmd)
	retcode = p.wait()
	assert(retcode == 0)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

