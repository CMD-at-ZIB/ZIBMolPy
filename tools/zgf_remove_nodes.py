#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ZIBMolPy.pool import Pool, NodeList
from ZIBMolPy.ui import userinput, Option, OptionsList
import shutil
import sys
from datetime import datetime

import zgf_create_nodes
import zgf_cleanup

options_desc = OptionsList([
	Option("n", "doomed_nodes", "node-list", "Nodes to remove", default=""),
	Option("A", "methodalphas", "choice", "method to determine alphas", choices=("theta", "user") ),
])

def is_applicable():
	pool = Pool()
	return( len(pool)>1 )
	
#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	#TODO put somehow into Options, e.g. min_value=1 or required=True
	if(not options.doomed_nodes):
		sys.exit("Option --doomed_nodes is required.")
		
	pool = Pool()
	old_pool_size = len(pool)
	old_alpha = pool.alpha

	doomed_nodes = NodeList()
	
	#TODO: maybe this code should go into ZIBMolPy.ui 
	for name in options.doomed_nodes.split(","):
		found = [n for n in pool if n.name == name]
		if(len(found) != 1):
			sys.exit("Coult not find node '%s'"%(name))
		doomed_nodes.append(found[0])
	
	for n in doomed_nodes:
		if(n == pool.root):
			sys.exit("Node %s is the root. Removal not allowed."%(n.name))		
		#if(len(n.children) > 0):
		#	sys.exit("Node %s has children. Removal not allowed."%(n.name)) #TODO why should we forbid this?

	if not(userinput("The selected node(s) will be removed permanently. Continue?", "bool")):
		sys.exit("Quit by user.")

	assert(len(doomed_nodes) == len(doomed_nodes.multilock()))
	for n in doomed_nodes:
		print("Removing directory: "+n.dir)
		shutil.rmtree(n.dir)

	pool.reload_nodes()
	
	#TODO: this code-block also exists in zgf_create_node
	if(len(pool.where("isa_partition")) < 2):
		pool.alpha = None
	elif(options.methodalphas == "theta"):
		pool.alpha = zgf_create_nodes.calc_alpha_theta(pool)
	elif(options.methodalphas == "user"):
		pool.alpha = userinput("Please enter a value for alpha", "float")
	else:
		raise(Exception("Method unkown: "+options.methodalphas))

	pool.history.append({'removed_nodes': [(n.name, n.state) for n in doomed_nodes], 'size':old_pool_size, 'alpha':old_alpha, 'timestamp':datetime.now()})
	pool.save()

	#TODO: deal with analysis dir and dependencies
	zgf_cleanup.main()	


#==========================================================================
if(__name__=="__main__"):
	main()

#EOF

