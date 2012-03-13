# -*- coding: utf-8 -*-

import os
from os import path
from subprocess import Popen
import numpy as np
import pprint

#===============================================================================
def check_call_silent(*popenargs, **kwargs):
	""" redirect stdout and stderr to /dev/null """
	fnull = open(os.devnull, 'w')
	kwargs["stdout"] = fnull
	kwargs["stderr"] = fnull
	check_call(*popenargs, **kwargs)
	fnull.close()
	

#===============================================================================
def check_call(*popenargs, **kwargs):
	""" Selfmade version of subprocess.check_call for python 2.4 """
	p = Popen(*popenargs, **kwargs)
	retcode = p.wait()
	if(retcode !=0):
		raise( Exception("Return-code %d with program %s"%(retcode, popenargs[0])) )



#===============================================================================
def get_phi_contrib(x, curr_node, coord):
	all_nodes = curr_node.pool.where("state!='refined'")
	other_nums = [ get_phi_num_contrib(x, curr_node, n, coord) for n in all_nodes ]
	denom = np.sum(other_nums, axis=0)
	num = get_phi_num_contrib(x, curr_node, curr_node, coord)
	return( num / denom )
	
def get_phi_num_contrib(x, ref_node, curr_node, coord):
	#TODO: implement InternalArray.__setslice__ and use norm2() instead
	""" Takes all values from ref_node.internals except for coordinate coord. \
		There it uses the values x. """ 	
	# #calc normal diff
	# diffs = (ref_node.internals - curr_node.internals).array
	# #ignore results for coordinate coord
	# print diffs.shape
	# diffs[coord.index] = 0 #this will be counted in diff2
	# diff1 = np.sum(np.square(diffs))
	# 
	
	diffs = ref_node.internals - curr_node.internals
	diffs[:, coord] = 0  #this will be counted in diff2
	diff1 = diffs.norm2()
	
	#calc result for coodinate coord
	diff2 = np.square(coord.sub(x, curr_node.internals.getcoord(coord)))
	#add those two and take advantage of broadcasting
	diff12 = diff1 + diff2 #using broadcasting
	return( np.exp( -curr_node.pool.alpha * diff12 ) )


#===============================================================================
def get_phi_contrib_potential(x, curr_node, coord):
	#return( -1/get_beta(curr_node.pool.temperature)*np.log( get_phi_contrib(x, curr_node, coord) ) )
	return( -1/curr_node.pool.thermo_beta*np.log( get_phi_contrib(x, curr_node, coord) ) )





			

#===============================================================================
def get_phi(frames, curr_node):
	""" Considers only active nodes (state!='refined') """ 	
	return( get_phi_num(frames, curr_node) / get_phi_denom( frames, curr_node.pool.where("state!='refined'") ) )
	

def get_phi_num(frames, curr_node):	
	return( np.exp(-curr_node.pool.alpha*( (frames - curr_node.internals).norm2() ) ) )


def get_phi_denom(frames, nodes):
	return( np.sum( get_phi_num(frames, node) for node in nodes) )


#===============================================================================
def get_phi_potential(frames, curr_node):
	#return( -1/get_beta(curr_node.pool.temperature)*np.log( get_phi(frames, curr_node) ) )
	return( -1*curr_node.pool.thermo_beta*np.log( get_phi(frames, curr_node) ) )


#===============================================================================
def all(*args):
	""" Selfmade version of buildin all for python 2.4 """
	#pylint: disable=W0622
	
	for x in args:
		if(not x): return False
	return(True)


#===============================================================================
def any(*args):
	""" Selfmade version of buildin any for python 2.4 """
	#pylint: disable=W0622
	for x in args:
		if(x): return True
	return(False)

#===============================================================================
def fn2dep(fn):
	return path.join(path.dirname(fn),"."+path.basename(fn)+".zgf-dep")
		
def dep2fn(dep):
	assert(dep.endswith(".zgf-dep"))
	assert(path.basename(dep).startswith("."))
	return path.join(path.dirname(dep), path.basename(dep)[1:-8])
	
#===============================================================================
def register_file_dependency(addict, drug):
	entries = set()
	dep_fn = fn2dep(addict)
	if(path.exists(dep_fn)):
		f = open(dep_fn, "r")
		entries = set(f.readlines())
		f.close()
	entries.add(relpath(drug, path.dirname(addict))+"\n")
	f = open(dep_fn, "w")
	f.write("".join(entries))
	f.close()

#===============================================================================
def pformat(data):
	""" A pretty formater, that outputs numpy-arrays completely """
	np.set_printoptions(threshold=float('nan')) #hack to ensure complete arrays from pformat
	txt = pprint.pformat(data)
	np.set_printoptions(threshold=1000) #reset to default value
	return(txt)

#===============================================================================
# This is os.path.relpath implementation for python 2.4
#http://code.activestate.com/recipes/302594-another-relative-filepath-script/
def relpath(target, base=os.curdir):
	"""
	Return a relative path to the target from either the current dir or an optional base dir.
	Base can be a directory specified either as absolute or relative to current dir.
	"""
	
	# if not os.path.exists(target):
		# raise OSError, 'Target does not exist: '+target
		# 
	# if not os.path.isdir(base):
		# raise OSError, 'Base is not a directory or does not exist: '+base
	 
	base_list = (os.path.abspath(base)).split(os.sep)
	target_list = (os.path.abspath(target)).split(os.sep)
	
	# On the windows platform the target may be on a completely different drive from the base.
	if os.name in ['nt','dos','os2'] and base_list[0] != target_list[0]:
		raise OSError, 'Target is on a different drive to base. Target: '+target_list[0].upper()+', base: '+base_list[0].upper()
		
	# Starting from the filepath root, work out how much of the filepath is
	# shared by base and target.
	i = None
	for i in range(min(len(base_list), len(target_list))):
		if base_list[i] != target_list[i]: break
	else:
		# If we broke out of the loop, i is pointing to the first differing path elements.
		# If we didn't break out of the loop, i is pointing to identical path elements.
		# Increment i so that in all cases it points to the first differing path elements.
		i+=1
		
	rel_list = [os.pardir] * (len(base_list)-i) + target_list[i:]
	return os.path.join(*rel_list)
#===============================================================================
#EOF
