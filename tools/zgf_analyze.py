#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the final step of ZIBgridfree.}

	This tool will

		1. Calculate the initial S matrix (S{Phi} overlap matrix) and K matrix (S{Phi} transition matrix)
		2. Symmetrize S and K using the direct node weights obtained by L{zgf_reweight}
		3. Come up with a second, corrected version of node weights
		4. Calculate eigenvalues and eigenvectors of the symmetrized S matrix
		5. Sort the eigenvectors in descending order according to the value of the corresponding eigenvalue
		6. Orthogonalize the eigenvectors and deal with degeneracies
		7. Perform PCCA+ on the orthogonalized eigenvectors, yielding S{chi} (chi) matrix and cluster weights
		8. Calculate the eigenvectors S{xi} (xi) of the Q_c matrix (the Markov state model)
		9. Calculate Q_c from S{xi} and PCCA+ output

	You may continue your analysis by looking at the clustering with L{zgf_browser}. If you like the clustering, you can extract the frames belonging to the metastable conformations by using L{zgf_extract_conformations} for visualization of cluster representatives. If you don't like the clustering, you can rerun L{zgf_analyze} and try a different number of clusters.

How it works
============
	At the command line, type::
		$ zgf_analyze [options]

PCCA+
=====
	You will have to specify a number of clusters for PCCA+. An initial guess for this number will be made based on the largest gap between the calculated eigenvalues. Ideally there is only real eigenvalue one, followed by a number of eigenvalues very close to one (together forming the Perron cluster, which gives the number of metastable conformations), followed by a significant gap to mark the end of the Perron cluster. Eigenvectors belonging to eigenvalues that are not in the Perron cluster are irrelevant for PCCA+. The quality of the clustering result can be evaluated by taking a look at the (stochastic) S{chi} matrix, which for each node gives the membership to the metastable conformations identified during PCCA+. All matrices can also be exported for use in Matlab. The matrices are stored in the analysis/ directory.

K matrix and lag time
=====================
	At the moment, the K matrix and its lag time are not used.

Symmetrization error threshold
==============================
	This parameter helps to adjust the weighting of overlap regions between S{Phi} functions.

"""

from os import path
import sys
from ZIBMolPy.utils import get_phi_num, get_phi_denom, register_file_dependency
from ZIBMolPy.pool import Pool
from ZIBMolPy.algorithms import cluster_by_isa, orthogonalize, symmetrize
from ZIBMolPy.ui import userinput, Option, OptionsList
from scipy.io import savemat
import numpy as np

import zgf_cleanup

options_desc = OptionsList([
	Option("e", "error", "choice", "error threshold for symmetrize", choices=("1E-02", "1E-03", "1E-04", "1E-05", "1E-06", "1E-07", "1E-08", "1E-09", "1E-10")),
	Option("m", "export-matlab", "bool", "export matrices as mat-files", default=False),
	Option("c", "auto-cluster", "bool", "choose number of clusters automatically", default=False),
	Option("l", "lag-time", "int", "lag time for K matrix", default=1, min_value=0),
	Option("o", "overwrite-mat", "bool", "overwrite existing matrices", default=False),
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return( len(pool.where("'weight_direct' in obs")) > 0 and len(pool.where("isa_partition and 'weight_direct' not in obs")) == 0 )

#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]

	zgf_cleanup.main()
	
	pool = Pool()
	active_nodes = pool.where("isa_partition")
	
	assert(len(active_nodes) == len(active_nodes.multilock())) # make sure we lock ALL nodes

	if active_nodes.where("'weight_direct' not in obs"):
		sys.exit("Matrix calculation not possible: Not all of the nodes have been reweighted.")
	
	print "\n### Getting S matrix ..."
	s_matrix = cache_matrix(pool.s_mat_fn, active_nodes, overwrite=options.overwrite_mat)
	register_file_dependency(pool.s_mat_fn, pool.filename)

	print "\n### Getting K matrix ..."
	k_matrix = cache_matrix(pool.k_mat_fn, active_nodes, shift=options.lag_time, overwrite=options.overwrite_mat)
	register_file_dependency(pool.k_mat_fn, pool.filename)	

	node_weights = np.array([node.obs.weight_direct for node in active_nodes])
	
	print "\n### Symmetrizing S matrix ..."
	(corr_s_matrix, corr_node_weights) = symmetrize(s_matrix, node_weights, correct_weights=True, error=float(options.error))
	print "\n### Symmetrizing K matrix ..."
	(corr_k_matrix, corr_node_weights) = symmetrize(k_matrix, corr_node_weights)

	# store intermediate results
	register_file_dependency(pool.s_corr_mat_fn, pool.s_mat_fn)
	register_file_dependency(pool.k_corr_mat_fn, pool.k_mat_fn)
	np.savez(pool.s_corr_mat_fn, matrix=corr_s_matrix, node_names=[n.name for n in active_nodes])
	np.savez(pool.k_corr_mat_fn, matrix=corr_k_matrix, node_names=[n.name for n in active_nodes])
	
	if options.export_matlab:
		savemat(pool.analysis_dir+"node_weights.mat", {"node_weights":node_weights, "node_weights_corrected":corr_node_weights})
		savemat(pool.analysis_dir+"s_mats.mat", {"s_matrix":s_matrix, "s_matrix_corrected":corr_s_matrix})
		savemat(pool.analysis_dir+"k_mats.mat", {"k_matrix":k_matrix, "k_matrix_corrected":corr_k_matrix})
	
	for (n, cw) in zip(active_nodes, corr_node_weights):
		n.obs.weight_corrected = cw
		
	print "\n### Node weights after symmetrization of S matrix:"
	for n in active_nodes:
		print "%s: initial weight: %f, corrected weight: %f, weight change: %f" % (n.name, n.obs.weight_direct, n.obs.weight_corrected, abs(n.obs.weight_direct - n.obs.weight_corrected))
		n.save()

	active_nodes.unlock()

	# calculate and sort eigenvalues in descending order
	(eigvalues, eigvectors) = np.linalg.eig(corr_s_matrix)
	argsorted_eigvalues = np.argsort(-eigvalues)
	eigvalues = eigvalues[argsorted_eigvalues]
	eigvectors = eigvectors[:, argsorted_eigvalues]
	
	gaps = np.abs(eigvalues[1:]-eigvalues[:-1])
	gaps = np.append(gaps, 0.0)
	wgaps = gaps*eigvalues

	print "\n### Sorted eigenvalues of symmetrized S matrix:"
	for (idx, ev, gap, wgap) in zip(range(1, len(eigvalues)+1), eigvalues, gaps, wgaps):
		print "EV%04d: %f, gap to next: %f, EV-weighted gap to next: %f" % (idx, ev, gap, wgap)
	n_clusters = np.argmax(gaps)+1
	print "\n### Maximum gap %f after top %d eigenvalues." % (np.max(gaps), n_clusters)
	print "### Maximum EV-weighted gap %f after top %d eigenvalues." % (np.max(wgaps), np.argmax(wgaps)+1)
	sys.stdout.flush()
	if not options.auto_cluster:
		n_clusters = userinput("Please enter the number of clusters for PCCA+", "int", "x>0")

	print "eigenvectors"
	print eigvectors[:, :n_clusters]

	if options.export_matlab:
		savemat(pool.analysis_dir+"evs.mat", {"evs":eigvectors})
	
	# orthogonalize and normalize eigenvectors 
	eigvectors = orthogonalize(eigvalues, eigvectors, corr_node_weights)

	# perform PCCA+
	# First two return-values "c_f" and "indicator" are not needed
	(chi_matrix, rot_matrix) = cluster_by_isa(eigvectors, n_clusters)[2:]
	
	#TODO at the moment, K-matrix is not used
	#xi = [] # calculate eigenvalues of Q_c, xi
	#for eigvec in np.transpose(eigvectors)[: n_clusters]:
	#	num = np.dot( np.dot( np.transpose(eigvec), corr_k_matrix ), eigvec )
	#	denom = np.dot( np.dot( np.transpose(eigvec), corr_s_matrix ), eigvec )
	#	xi.append(num/denom-1)

	#print np.diag(xi) #TODO what does this tell us? Marcus-check

	qc_matrix = np.dot( np.dot( np.linalg.inv(rot_matrix), np.diag(eigvalues[range(n_clusters)]) ), rot_matrix ) - np.eye(n_clusters)

	cluster_weights = rot_matrix[0]

	print "Q_c matrix:"
	print qc_matrix
	print "Q_c matrix row sums:"
	print np.sum(qc_matrix, axis=1)
	print "cluster weights (calculated twice for checking):"
	print cluster_weights
	print np.dot(corr_node_weights, chi_matrix)
	print "chi matrix column sums:"
	print np.sum(chi_matrix, axis=0)
	print "chi matrix row sums:"
	print np.sum(chi_matrix, axis=1)

	# store final results
	np.savez(pool.chi_mat_fn, matrix=chi_matrix, n_clusters=n_clusters, node_names=[n.name for n in active_nodes])
	np.savez(pool.qc_mat_fn,  matrix=qc_matrix,  n_clusters=n_clusters, node_names=[n.name for n in active_nodes], weights=cluster_weights)

	if options.export_matlab:
		
		savemat(pool.analysis_dir+"chi_mat.mat", {"chi_matrix":chi_matrix})
		savemat(pool.analysis_dir+"qc_mat.mat", {"qc_matrix":qc_matrix, "weights":cluster_weights})

	register_file_dependency(pool.chi_mat_fn, pool.s_corr_mat_fn)
	register_file_dependency(pool.qc_mat_fn, pool.s_corr_mat_fn)
	for fn in (pool.s_mat_fn, pool.s_corr_mat_fn, pool.k_mat_fn, pool.k_corr_mat_fn):
		register_file_dependency(pool.chi_mat_fn, fn)
		register_file_dependency(pool.qc_mat_fn, fn)
		
	zgf_cleanup.main()


#===============================================================================
# "cache" specialized for "calc_matrix" in order to save a proper npz
def cache_matrix(filename, nodes, shift=0, overwrite=False):
	if(path.exists(filename) and not overwrite):
		return(np.load(filename)["matrix"])
	mat = calc_matrix(nodes, shift)
	for n in nodes:
		register_file_dependency(filename, n.trr_fn)
	np.savez(filename, matrix=mat, node_names=[n.name for n in nodes])
	return(mat)


#===============================================================================
def calc_matrix(nodes, shift=0):
	mat = np.zeros( (len(nodes), len(nodes)) )
	for (i, ni) in enumerate(nodes):
		print("Working on: %s"%ni)
		phi_denom = get_phi_denom(ni.trajectory, nodes)
		frame_weights = ni.frameweights
		if shift > 0:
			frame_weights = frame_weights[:-shift]
		for (j, nj) in enumerate(nodes):
			mat[i, j] = np.average(get_phi_num(ni.trajectory, nj)[shift:] / phi_denom[shift:], weights=frame_weights)
	
	return(mat)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
