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
	Information about the convergence properties of individual internal coordinates can be found in the convergence log file named 'node0042_convergence.log' stored in the node directory. B{Note that convergence as indicated by the GR criterion does not necessarily mean that the sampling is sufficient}. If, at the end of the day, not all of the nodes in the pool have converged, you can use  L{zgf_browser} to get an impression where convergence was not achieved.

	In case that convergence keeps on failing due to a certain internal coordinate, or due to a certain internal coordinate type (such as linears), you might want to modify the U{internal coordinate weights <http://www.zib.de/cmd-debian/ZIBMolPy/apidocs/ZIBMolPy.internals-module.html>}.

Automatic refinement
====================
	If you use this option, L{zgf_mdrun} will automatically call L{zgf_refine} at most n times (where n is an option specified by you) in order to resolve nodes that have not converged. Refinement is performed using default parameters from L{zgf_create_nodes}.

Nodes with state "mdrun-failed"
===============================
	If something goes seriously wrong during the sampling of a node, it will adapt the state "mdrun-failed". You have to manually set the node back to state "mdrun-able" after the problem is resolved. Possible causes for failed node samplings are:

		- B{Problem:} Domain decomposition does not fit number of nodes/PME nodes. B{Solution:} Change number of nodes/PME nodes, or change PME grid dimension, or use particle decomposition.
		- B{Problem:} Domain decomposition does not work with restraints. B{Solution:} Change number of nodes/PME nodes, or change PME grid dimension, or use particle decomposition.
		- B{Problem:} Unspecific crashes when Linear Coordinates are used. B{Solution:} Make periodic box bigger (at least double the size of the largest Linear Coordinate).
"""

from ZIBMolPy.utils import check_call
from ZIBMolPy.pool import Pool
from ZIBMolPy.algorithms import gelman_rubin
from ZIBMolPy.ui import Option, OptionsList
import zgf_refine

from subprocess import call
from warnings import warn
import traceback
import sys

options_desc = OptionsList([ 
	Option("s", "seq", "bool", "Suppress MPI", default=False),
	Option("n", "np", "int", "Number of processors to be used for MPI", default=4, min_value=1),
	Option("t", "nt", "int", "Number of threads to start, 0 is guess", default=0, min_value=0),
	Option("p", "npme", "int", "Number of separate processors to be used for PME, -1 is guess", default=-1, min_value=-1),
	Option("r", "reprod", "bool", "Avoid mdrun optimizations that affect binary reproducibility", default=False),
	Option("d", "pd", "bool", "Use particle decomposition", default=False),
	Option("c", "convtest", "bool", "Test if nodes are converged - does not simulate", default=False),
	Option("a", "auto-refines", "int", "Number of automatic refinements", default=0, min_value=0),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc


def is_applicable():
	pool = Pool()
	return(len(pool.where("state in ('em-mdrun-able', 'mdrun-able','converged', 'not-converged')")) > 0)
	

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
		for n in pool.where("state in ('em-mdrun-able', 'mdrun-able')"):
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
			#sys.exit("Error: mdrun failed.")
			continue
			

#===============================================================================
def process(node, options):
	
	if(node.extensions_counter > 0):
		cmd0 = ["tpbconv", "-s", node.tpr_fn, "-o", node.tpr_fn, "-extend", str(node.extensions_length)]
		print("Calling: %s"%" ".join(cmd0))
		check_call(cmd0)
	
	cmd1 = ["mdrun"]
	cmd1 += ["-s", "../../"+node.tpr_fn]
	
	if(node.state == "em-mdrun-able"):
		cmd1 += ["-c", "../../"+node.pdb_fn]
		cmd1 += ["-o", "../../"+node.dir+"/em.trr"]
		cmd1 += ["-e", "../../"+node.dir+"/em.edr"]
		cmd1 += ["-g", "../../"+node.dir+"/em.log"]
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

	# if we were just minimizing, we go back to grompp-able now
	if(node.state == "em-mdrun-able"):
		node.state = "grompp-able"
		return
	
	# check for convergence
	converged = conv_check_gelman_rubin(node)

	# decide what to do next
	if(converged):
		node.state = "converged"

	elif(node.extensions_counter >= node.extensions_max):
		node.state = "not-converged"

	else:
		node.extensions_counter += 1
		node.state = "mdrun-able" # actually it should still be in this state


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
if(__name__ == "__main__"):
	main()

#EOF

