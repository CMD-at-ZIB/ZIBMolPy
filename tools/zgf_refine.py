#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the (optional) sixth step of ZIBgridfree.}

	This tool scans the node pool for nodes that have not converged, or that have converged by mistake. For every non-converged node, two alternatives exist:

		- Refinement: Create new nodes from the node sampling and discard the original node. This is useful if the node sampling has come upon an additional minimum.
		- Extension: Keep the original node and extend the node sampling.

	L{zgf_refine} calls L{zgf_create_nodes} in order to add new nodes to the node pool. Therefore, it inherits several options from L{zgf_create_nodes}. For more information, please refer to the L{zgf_create_nodes} documentation. 
	
	B{The next step is L{zgf_mdrun}, or L{zgf_submit_job_HLRN}, if you are working on HLRN.}

How it works
============
	At the command line, type::
		$ zgf_refine [options]

"""

from ZIBMolPy.ui import userinput, userchoice, Option, OptionsList
from ZIBMolPy.algorithms import kmeans
from ZIBMolPy.pool import Pool
import zgf_create_nodes
import zgf_setup_nodes
import zgf_grompp
import zgf_cleanup

from copy import copy
import sys

options_desc = OptionsList([
	Option("r", "refine-all", "bool", "refine all not-converged nodes", default=False), 
	Option("e", "extend-all", "bool", "extend all not-converged nodes", default=False),
	])

# reuse some options from zgf_create_nodes
FORWARDED_ZGF_CREATE_NODES_OPTIONS = ("numnodes", "methodnodes", "methodalphas", "methodphifit", "random-seed")
for x in FORWARDED_ZGF_CREATE_NODES_OPTIONS:
	options_desc.append(copy(zgf_create_nodes.options_desc[x])) # need copy to safely ...
options_desc["numnodes"].default = 2 # ... change default values

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return(len(pool.where("isa_partition and is_sampled")) > 0)

	
#===============================================================================
# This method is also called from zgf_mdrun
def main(argv=None):
	if(argv==None):
		argv = sys.argv
	options = options_desc.parse_args(argv)[0]

	assert(not(options.refine_all and options.extend_all)) 
	
	pool = Pool()
	needy_nodes = pool.where("isa_partition and is_sampled").multilock()
	
	# 1. Trying to detect fake convergence
	for n in pool.where("state == 'converged'"):
		means = kmeans(n.trajectory, k=2)
		d = (means[0] - means[1]).norm2()
		if(d > 2.0 and (options.refine_all or userinput("%s has converged but appears to have a bimodal distribution.\nDo you want to refine?"%n.name, "bool"))): #TODO decide upon threshold (per coordinate?)
			refine(n, options)
	
	# 2. Dealing with not-converged nodes
	for n in pool.where("state == 'not-converged'"):
		if(not(options.refine_all or options.extend_all)):
			choice = userchoice("%s has not converged. What do you want to do?"%n.name, ['_refine', '_extend', '_ignore'])
		if(options.refine_all or choice=="r"):
			refine(n, options)
		elif(options.extend_all or choice=="e"):
			extend(n)
		elif(choice=="i"):
			continue
	
	for n in needy_nodes:
		n.save()
		n.unlock()
			
	zgf_setup_nodes.main()
	zgf_grompp.main()
	zgf_cleanup.main()	


#===============================================================================
def refine(node, options):
	print "refining node %s..."%node.name
	args = ["-p", node.name ]
	for x in FORWARDED_ZGF_CREATE_NODES_OPTIONS:
		args += options_desc[x].forward_value(options)
	zgf_create_nodes.main(args)

	node.state = "refined"
	
	
#===============================================================================
def extend(node):
	print "extending node %s..."%node.name
	node.extensions_counter += 1
	node.state = "mdrun-able"


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

