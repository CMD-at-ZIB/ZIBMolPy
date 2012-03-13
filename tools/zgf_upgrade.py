#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	This upgrades a pool, which was created with an earlier version of the software.

"""


from ZIBMolPy.utils import pformat
from ZIBMolPy.ui import OptionsList

#needed to eval pool-desc.txt
import datetime #pylint: disable=W0611

import os
import sys
from os import path
from glob import glob
import re

options_desc = OptionsList([])
def is_applicable(): 
	return(False) # run from command-line only
	
#===============================================================================
def main():
	#(options, args) = options_desc.parse_args(sys.argv)
	
	if(not path.isfile("pool-desc.txt")):
		sys.exit("Error: could not find pool-desc.txt")
	
	if(not path.isdir("nodes")):
		sys.exit("Error: could not find pool-desc.txt")
	
	for n in glob("nodes/*"):
		if(path.exists(n+"/lock")):
			sys.exit("Error: found lock in "+n)
	
	
	f = open("pool-desc.txt", "r")
	pool_desc = eval(f.read())
	f.close()
	
	v = pool_desc['format_version']
	if(v == 1):
		upgrade_1to2()
		set_pool_format_version(2)	
		
	elif(v == 2):
		print("Pool has latest format version")
		sys.exit(0)
	
	else:
		print("Error: Pool has unkown format version: "+v)
		sys.exit(1)

#===============================================================================
def set_pool_format_version(v):
	f = open("pool-desc.txt", "r")
	pool_desc = eval(f.read())
	f.close()

	pool_desc['format_version'] = v
	f = open("pool-desc.txt", "w")
	f.write(pformat(pool_desc)+"\n")
	f.close()
	
#===============================================================================
def upgrade_1to2():
	print("Upgrading pool from version 1 to 2 ...")
		
	for node_dir in glob("nodes/*"):
		node_name = path.basename(node_dir)
		print "working on: "+node_name
		
		# correcting node-desc.txt filename
		desc_fn_old = node_dir+"/node-desc.txt"
		desc_fn_new = node_dir+"/"+node_name+"_desc.txt"
		if(not path.exists(desc_fn_new)):
			print("Renaming: %s -> %s"%(desc_fn_old, desc_fn_new))
			os.rename(desc_fn_old, desc_fn_new)
		
		
		# correcting trajectory - filename
		trr_fn_new = node_dir+"/"+node_name+".trr"
		trr_fn_old = node_dir+"/traj.trr"
		trr_whole_fn = node_dir+"/"+node_name+"_whole.trr"
		if(not path.exists(trr_fn_new)):
			if(path.exists(trr_fn_old)): # normal case
				print("Renaming: %s -> %s"%(trr_fn_old, trr_fn_new))
				os.rename(trr_fn_old, trr_fn_new)
				if(path.exists(trr_whole_fn)):
					print("Removing: "+trr_whole_fn)
					os.remove(trr_whole_fn)
			
			elif(path.exists(trr_whole_fn)): #case root-node (presampling)
				print("Creating symlink: %s -> %s"%(trr_fn_new, trr_whole_fn))
				os.symlink(node_name+"_whole.trr", trr_fn_new)
				
			else: #case: not yet sampled node 
				print("This node seems to have not trajectory, yet")
		
		
		# correcting pdb filename
		pdb_fn_new = node_dir+"/"+node_name+"_conf.pdb"
		if(not path.exists(pdb_fn_new)):
			node_desc = open(node_dir+"/"+node_name+"_desc.txt").read()
			m = re.search("'pdb_fn':\s+'([^']+)'", node_desc)
			if(m):
				pdb_fn_old = m.group(1)
				print("Creating symlink: %s -> %s"%(pdb_fn_new, pdb_fn_old))
				os.symlink(os.path.relpath(pdb_fn_old, node_dir), pdb_fn_new)
		
		
		# renameing more files
		for i in ("observables.txt", "convergence.log", "reweighting.log"):
			fn_old = node_dir+"/" + i
			fn_new = node_dir+"/" + node_name +"_"+ i
			if(path.exists(fn_old)):
				print("Renaming: %s -> %s"%(fn_old, fn_new))
				os.rename(fn_old, fn_new)
		
		
#===============================================================================
if(__name__ == "__main__"):
	main()


#EOF
