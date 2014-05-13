#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ZIBMolPy.pool import Pool
from ZIBMolPy.utils import fn2dep, dep2fn
from ZIBMolPy.ui import OptionsList

from os import path
import sys
import os

options_desc = OptionsList()

def is_applicable():
	return(True)

#===============================================================================
def main():
	print("Cleaning up.")
	
	#check locks
	pool = Pool()
	for n in pool:
		sys.stdout.write("Node %s is %s and "%(n.name, n.state))
		if(not n.is_locked ):
			print("not locked.")
		elif( n.is_lock_valid ):
			print("is locked and valid.")
		else:
			print("its lock is stale - removing it.")
			os.remove(n.lock_fn) 			
	
	#check zgf-dep files
	files = []
	for root, _, names in os.walk( os.getcwd()):
		for n in names:
			if(not n.endswith(".zgf-dep")):
				continue
			dep = path.join(root,n)
			fn = dep2fn(dep)
			if(not path.exists(fn)):
				print("Removing lonely dep-file: "+dep)
				os.remove(dep)
				continue
			files.append(fn) #in extra loop - otherwise check_files and remove(dep) collide
	
	for fn in files: 
		check_file(fn)


#===============================================================================
def check_file(fn1):
	#print "checking: "+fn1
	if(not path.exists(fn1) or not path.exists(fn2dep(fn1))):
		return #nothing to check
		
		
	t1 = path.getmtime(fn1)
			
	
	for l in open(fn2dep(fn1)).readlines():
		fn2 = path.normpath(path.join(path.dirname(fn1), l.strip()))
		check_file(fn2)
		if(not path.exists(fn2)):
			print ("Removing %s because source-file %s is gone."%(fn1, fn2))
			os.remove(fn1)
			os.remove(fn2dep(fn1))
			return
		
		t2 = path.getmtime(fn2)
		if(t1 < t2):
			print("Removing outdated file %s because %s is younger."%(fn1, fn2))
			os.remove(fn1)
			os.remove(fn2dep(fn1))
			return
			
#===============================================================================
#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
