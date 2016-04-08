#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from subprocess import Popen
from optparse import OptionParser
from os import path
import shutil
from glob import glob


LOG_FILENAME = "installed_files.log"

#===============================================================================
def main():
	usage = 'Usage: %prog [options] <action>\n<action> can be "install" or "uninstall"'
	parser = OptionParser(usage=usage)
	parser.add_option("-p", "--prefix", help="base-directory for the installation", default="/")
	(options, args) = parser.parse_args()
	if(len(args) != 1):
		parser.error("wrong number of arguments.")
	
	if(args[0] == "install"):
		do_install(options.prefix)
	
	elif(args[0] == "uninstall"):
		do_uninstall()
		
	else:
		parser.error("unkown action: "+args[0])
	


	
#===============================================================================
def do_install(prefix="/"):
	if(prefix[-1] != "/"):
		prefix += "/"
	
		
	log = open(LOG_FILENAME, "a")

	def mkdir(dirname):
		log.write(dirname+"\n")
		if(not path.exists(dirname)):
			print("Creating dir: "+dirname)
			os.mkdir(dirname) #not using os.makedirs, to get seperate log-entries
	
	def copyfile(fn_src, fn_dest):
		log.write(fn_dest+"\n")
		print("Copying %s -> %s"%(fn_src, fn_dest))
		shutil.copy(fn_src, fn_dest)
		
	# create destination dirs
	dir_bin = prefix + "bin/" 
	dir_share = prefix + "usr/share/zibmolpy/"
	mkdir(prefix + "bin")
	mkdir(prefix + "usr")
	mkdir(prefix + "usr/share")
	mkdir(prefix + "usr/share/zibmolpy")
		
	# copy test-cases
	for root, dirs, files in os.walk('tests'):
		mkdir(dir_share+root)
		for fn in files:
			if fn.endswith('.pyc'): continue
			if fn.startswith('.'): continue
			copyfile(root+"/"+fn, dir_share+root+"/"+fn)
      
	
	# install the library modules
	cmd = ["./setup.py","install"]
	if(prefix != "/"):
		cmd += ["--prefix="+prefix]
	p = Popen(cmd, cwd="ZIBMolPy_package")
	p.wait()
	assert(p.returncode == 0)
	
	# copy tools and create symlinks
	for fn in glob("./tools/*.py"):
		fn_dest = dir_bin+path.basename(fn)
		copyfile(fn, fn_dest)
		
		link_src = path.basename(fn)
		link_name = fn_dest[:-3]
		log.write(link_name+"\n")
		if(not path.exists(link_name)):
			print("Createing Link %s -> %s"%(link_name, link_src))
			os.symlink(link_src, link_name)
			
	
	log.close()
	print("Install done.")
	
#===============================================================================
def do_uninstall():
	try:
		#removing library
		import ZIBMolPy
		lib_dir = path.dirname(ZIBMolPy.__file__)
		del(ZIBMolPy)
		print("Removing directory-tree: "+lib_dir)
		shutil.rmtree(lib_dir)
		
		#removing egg-files
		for fn in glob(lib_dir+"*.egg-info"):
			print("Removeing file: "+fn)
			os.remove(fn)	
	except:
		print("Could not uninstall library.")
		pass
	
	
	#removing tools and test-cases
	if(not path.exists(LOG_FILENAME)):
		print("Required file %s not found."%LOG_FILENAME)
		sys.exit(1)
	
	log = open(LOG_FILENAME, "r")
	for fn in reversed(log.readlines()):
		fn = fn.strip()
		if(not path.exists(fn)):
			pass
		elif(not path.isdir(fn)):
			print("Removeing file: "+fn)
			os.remove(fn)	
		elif(len(os.listdir(fn)) == 0):
			print("Removeing directory: "+fn)
			os.rmdir(fn)
		else:
			print("Leaving not empty directory: "+fn)
				
			
	log.close()
	os.remove(LOG_FILENAME)
	print("Uninstall done.")

#===============================================================================	
	
	
if(__name__ == "__main__"):
	main()
	
#EOF