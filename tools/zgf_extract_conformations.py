#!/usr/bin/python
# -*- coding: utf-8 -*-

from ZIBMolPy.utils import register_file_dependency
from ZIBMolPy.ui import Option, OptionsList
from ZIBMolPy.io.trr import TrrFile
from ZIBMolPy.node import Node
from ZIBMolPy.pool import Pool
import zgf_cleanup

from subprocess import Popen, PIPE
from tempfile import mktemp
from os import path
import numpy as np
import sys
import os


options_desc = OptionsList([
	Option("c", "node-threshold", "float", "threshold for node conformation membership, based on chi value", default=0.5),
	Option("f", "frame-threshold", "float", "threshold for frame conformation membership, based on frame weight", default=0.5),
	Option("s", "write-sol", "bool", "write output trajectories with SOL", default=False),
])
	
def is_applicable():
	pool = Pool()
	return( path.exists(pool.chi_mat_fn) )


#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]

	zgf_cleanup.main()
	
	pool = Pool()
	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']
	node_names = npz_file['node_names']
	n_clusters = npz_file['n_clusters']
	active_nodes = [Node(nn) for nn in node_names]
	
	# create and open dest_files, intialize counters for statistics
	dest_filenames = [ pool.analysis_dir+"cluster%d.trr"%(c+1) for c in range(n_clusters) ]
	dest_files = [ open(fn, "wb") for fn in dest_filenames ]
	dest_frame_counters = np.zeros(n_clusters)
	
	
	# For each active node...
	for (i, n) in enumerate(active_nodes):
		# ... find the clusters to which it belongs (might be more than one)...
		belonging_clusters = np.argwhere(chi_matrix[i] > options.node_threshold)
		
		# ... and find all typical frames of this node.
		#TODO not an optimal solution... discuss
		# per default, we take every frame with above average weight
		frame_threshold = options.frame_threshold*2*np.mean(n.frameweights)
		typical_frame_nums = np.argwhere(n.frameweights > frame_threshold)
		
		# Go through the node's trajectory ...
		trr_in = TrrFile(n.trr_fn)
		curr_frame = trr_in.first_frame
		for i in typical_frame_nums:
			# ...stop at each typical frame...
			while(i != curr_frame.number):
				curr_frame = curr_frame.next()
			assert(curr_frame.number == i)
			#... and copy it into the dest_file of each belonging cluster.
			for c in belonging_clusters:
				dest_files[c].write(curr_frame.raw_data)
				dest_frame_counters[c] += 1
		trr_in.close() # close source file


	# close dest_files
	for f in dest_files:
		f.close()
	del(dest_files)
	
	# desolvate cluster-trajectories 'in-place'
	if(not options.write_sol):
		for dest_fn in dest_filenames:
			tmp_fn = mktemp(suffix='.trr', dir=pool.analysis_dir)
			os.rename(dest_fn, tmp_fn) # works as both files are in same dir
			cmd = ["trjconv", "-f", tmp_fn, "-o", dest_fn, "-n", pool.ndx_fn]
			p = Popen(cmd, stdin=PIPE)
			p.communicate(input="MOI\n")
			assert(p.wait() == 0)
			os.remove(tmp_fn)
			
	# register dependencies
	for fn in dest_filenames:
		register_file_dependency(fn, pool.chi_mat_fn)
	
	# check number of written frames
	sys.stdout.write("Checking lenghts of written trajectories... ")
	for i in range(n_clusters):
		f = TrrFile(dest_filenames[i])
		assert(f.count_frames() == dest_frame_counters[i])
		f.close()
	print("done.")
	
	#output statistics
	print "\n### Extraction summary ###\nnode threshold: %1.1f, frame threshold: %1.1f"%(options.node_threshold, options.frame_threshold)
	print "Cluster trajectories were written to %s:"%pool.analysis_dir
	for (c, f) in enumerate(dest_frame_counters):
		print "cluster%d.trr [%d frames] from node(s):"%(c+1, f)
		print list(np.argwhere(chi_matrix[:,c] > options.node_threshold).flat)
		
		
#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
