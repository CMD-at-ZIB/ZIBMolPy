#!/usr/bin/python
# -*- coding: utf-8 -*-


from ZIBMolPy.ui import Option, OptionsList
from ZIBMolPy.pool import Pool
import zgf_cleanup

import numpy as np
from scipy.io import savemat
from pprint import pformat
import sys


options_desc = OptionsList([
	Option("K", "numnodes", "int", "number of nodes to create", default=10, min_value=2),
	Option("m", "export-matlab", "bool", "export matrices as mat-files", default=False)
])

def is_applicable():
	pool = Pool()
	return( len(pool.where("'weight_direct' in obs")) > 0 and len(pool.where("state != 'refined' and 'weight_direct' not in obs")) == 0 )

	
#===============================================================================
#Equidistand nodes and free energy computation
def main():
	options = options_desc.parse_args(sys.argv)[0]
	zgf_cleanup.main()
	
	print("Options:\n%s\n"%pformat(eval(str(options))))
	
	pool = Pool()
	parent = pool.root
	active_nodes = pool.where("state != 'refined'")
	
	assert(len(active_nodes) == len(active_nodes.multilock())) # make sure we lock ALL nodes

	if active_nodes.where("'weight_direct' not in obs"):
		sys.exit("Q-Matrix calculation not possible: Not all of the nodes have been reweighted.")

	node_weights = np.array([node.obs.weight_direct for node in active_nodes])
	
	print "### Generate bins: equidist ###" 
	result = q_equidist(parent, options.numnodes)
	chosen_idx=result['chosen_idx']
	frames_chosen=result['frames_chosen']
	theta=result['theta']
	chosen_idx.sort() # makes preview-trajectory easier to understand
	dimension=len(chosen_idx)

	print "chosen_idx"
	print chosen_idx

	print "### Generate bin weights ###"
	bin_weights=np.zeros(dimension)
	for (i,n) in enumerate(active_nodes):
		w_denom = np.sum(n.frameweights) 
		for t in range(len(n.trajectory)):
			diffs = (frames_chosen - n.trajectory.getframe(t)).norm()
			j = np.argmin(diffs)
			bin_weights[j] = bin_weights[j] + node_weights[i] * n.frameweights[t] / w_denom
			
	
	print "bin_weights"
	print bin_weights
	
	print "### Generate q_all (entries only for neighboring bins) ###" 
	q_all = np.empty((dimension, dimension), dtype=np.float)
	for i in range(dimension):
		sum_row = 0.0
		diffs = (frames_chosen - frames_chosen.getframe(i)).norm()
		print "diffs"
		print diffs
		for j in range(dimension):
			if (diffs[j] < 2.0 * theta) and (bin_weights[i] > 0.0):
				q_all[i,j] = np.sqrt(bin_weights[j]) / np.sqrt(bin_weights[i])
				sum_row = sum_row + q_all[i , j]
			else:
				q_all[i,j] = 0
		q_all[i, i] = q_all[i, i]- sum_row  
			
	print "Q_All"
	print q_all
	
	if options.export_matlab:
		savemat(pool.analysis_dir+"q_all.mat", {"q_all":q_all})
		
	active_nodes.unlock()
	zgf_cleanup.main()



#==========================================================================
def q_equidist(parent, numnodes):

	frames_int = parent.trajectory
	initial_node = 0
	# sorted distances (increasing order) from initial node to all frames
	diffs = (frames_int - frames_int.getframe(initial_node)).norm()
	sorted_diffs_idx = np.argsort( diffs )
	
	def identify_nodes(frames_int, initial_node, theta, sorted_diffs, sorted_diffs_idx):		
		chosen_idx = []

		while True:
			node = sorted_diffs_idx[0]
			chosen_idx.append(node)

			dist2initial = (frames_int.getframe(initial_node) - frames_int.getframe(node)).norm()
			dump = np.where((sorted_diffs - dist2initial) < theta)[0]

			# crop diffs and indices
			sorted_diffs = sorted_diffs[len(dump):]
			sorted_diffs_idx = sorted_diffs_idx[len(dump):]	
		
			if len(sorted_diffs) == 0:
				break

		return chosen_idx

	# binary search: tune theta so that 'numnodes' nodes are chosen
	theta_low = 0.0
	theta_high = np.max(diffs)
	theta = theta_high/2.0 # initial guess

	while True:
		chosen_idx = identify_nodes(frames_int, initial_node, theta, diffs[sorted_diffs_idx][:], sorted_diffs_idx[:])
		print "theta: %f, theta_high: %f, theta_low: %f, current numnodes: %d"%(theta, theta_high, theta_low, len(chosen_idx))

		if len(chosen_idx) < numnodes:
			theta_high = theta
		else:
			theta_low = theta
		if (len(chosen_idx) == numnodes) or (theta_high - theta_low < 2E-6):
			break

		theta = (theta_low + theta_high)/2.0

	frames_chosen = frames_int.getframes(chosen_idx)

	print "\nDiscretization overview:"
	print "- Variance per int of presampling trajectory:"
	print frames_int.var().array
	print "- Variance per int of chosen nodes:"
	print frames_chosen.var().array
	print "- Relative variance per int of chosen nodes:"
	print (frames_chosen.var() / frames_int.var()).array
	
	return {'chosen_idx':chosen_idx, 'frames_chosen':frames_chosen, 'theta':theta_high}
	


#==========================================================================
if(__name__=="__main__"):
	main()

#EOF

