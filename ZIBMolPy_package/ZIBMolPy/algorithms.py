# -*- coding: utf-8 -*-

import numpy as np
import sys

#===============================================================================
def kmeans(frames, k, threshold=1e-4, max_iterations=50, fixed_clusters=None):
	""" 
	Centroids for new cluster centers are calculated by mean_weighted.
	U{K-Means <http://en.wikipedia.org/wiki/K-means_clustering>}
	
	@param frames: Sampling points to clusters
	@type frames:  L{InternalArray}
	@param k: Number of clusters
	@type k: positiv integer
	@param fixed_clusters: additional cluster-centers, which can have members but are never moved.
	This is used in L{zgf_refine} to create additional nodes. 
	@type fixed_clusters: list of L{InternalArray}. 
	"""
	assert(frames.has_frameweights)
	if(fixed_clusters==None):
		fixed_clusters = []
	# pick initial means randomly
	start_frames = np.arange(len(frames))
	# using numpy-random because python-random differes beetween 32 and 64bit 
	np.random.shuffle(start_frames)
	start_frames = start_frames[:k]
	means = [ frames.getframe(i) for i in start_frames ]
	means += fixed_clusters
	for j in range(max_iterations):

		# distances of all frames to all nodes
		diffs = np.row_stack( (frames-m).norm2() for m in means )         
		# list specifying to which node each frame belongs
		members = np.argmin(diffs, axis=0)
		new_means = []
		for i in range(k):
			# from the list of all frames belonging to i-th node...
			member_frames_idx = np.atleast_1d(np.squeeze(np.argwhere(members == i)))
			# ...calculate the new centroid of i-th node
			new_means.append( frames.getframes(member_frames_idx).mean_weighted() )
		progress = np.mean( [(a-b).norm2() for (a,b) in zip(means, new_means)] )
		means = new_means + fixed_clusters
		print("k-means iteration %2d - Progress: %g"%(j, progress))
		if(progress < threshold):
			print "k-means has converged - quitting"
			break
	
	return(means[:k])
	

#===============================================================================
def gelman_rubin(frames, n_chains, threshold, log=sys.stdout):
	# split into chains of equal or near-equal(!) length
	assert(frames.has_frameweights)
	assert(frames.n_frames >= n_chains)
	chains = frames.array_split(n_chains)
	
	# catch runaway sampling
	for c in chains:		
		if( np.max(c.frameweights) == 0):
			log.write("### Convergence summary: Gelman-Rubin not possible.\n")
			log.write("WARNING: This usually means the sampling has left the support of its basis function!\n")
			log.write("### Convergence not achieved\n")
			return(False)

	#TODO: evtl. mögliche Vereinfachung: B_total_var = W_chain_var*n_frames 
	# calculate weighted inter-chain variance B, without factor n
	var_per_chain = [c.var_weighted().array for c in chains]
	sum_chain_var = np.sum(var_per_chain, axis=0)[0]
	W_chain_var = sum_chain_var / n_chains
		
	mean_total = frames.mean_weighted()
	square_diffs = [(c.mean_weighted() - mean_total).square().array for c in chains]
	sum_square_diffs = np.sum(square_diffs, axis=0)[0]
	B_total_var = sum_square_diffs / (n_chains-1) # TODO why -1?
	
	print "W_chain_vars", W_chain_var
	print "B_total_var", B_total_var
	
	# calculate variance estimate
	chain_len = float(len(chains[1]))
	V_hat = (1-(1/chain_len)) * W_chain_var + B_total_var
	sqrt_R = np.sqrt(V_hat/W_chain_var)

	log.write("### Convergence summary: Gelman-Rubin, threshold %s \n" % threshold)
	for (i, c) in enumerate(frames.converter):
		log.write("  %s \t: GR-shrink factor: %f\n" % (c, sqrt_R[i]))

	bad_guys = np.argwhere(sqrt_R >= threshold)
	if(len(bad_guys) == 0):
		log.write("### Convergence achieved\n")
	else:
		log.write("### Convergence not achieved due to:\n")
		for b in bad_guys:
			log.write("  %s \t: GR-shrink factor: %f\n" % (frames.converter[int(b)], sqrt_R[b]))

	return( len(bad_guys)==0 )


#===============================================================================
def cluster_by_isa(eigenvectors, n_clusters):
	#TODO: check this somehow, probably more args nessecary	
	# eigenvectors have to be sorted in descending order in regard to their eigenvalues
	if n_clusters > len(eigenvectors):
		n_clusters = len(eigenvectors)

    # the actual ISA algorithm
	c = eigenvectors[:, range(n_clusters)]
	ortho_sys = np.copy(c)
	max_dist = 0.0
	ind = np.zeros(n_clusters, dtype=np.int32)

	# first two representatives with maximum distance
	for (i, row) in enumerate(c):        
		if np.linalg.norm(row, 2) > max_dist:
			max_dist = np.linalg.norm(row, 2)
			ind[0] = i

	ortho_sys -= c[ind[0], None]
	
	# further representatives via Gram-Schmidt orthogonalization
	for k in range(1, n_clusters):
		max_dist = 0.0
		temp = np.copy(ortho_sys[ind[k-1]])
		

		for (i, row) in enumerate(ortho_sys):
			row -= np.dot( np.dot(temp, np.transpose(row)), temp )
			distt = np.linalg.norm(row, 2)
			if distt > max_dist:
				max_dist = distt
				ind[k] = i

		ortho_sys /= np.linalg.norm( ortho_sys[ind[k]], 2 )

	# linear transformation of eigenvectors
	rot_mat = np.linalg.inv(c[ind])
	
	chi = np.dot(c, rot_mat)

	# determining the indicator
	indic = np.min(chi)
	# Defuzzifizierung der Zugehoerigkeitsfunktionen
	#[minVal cF]=max(transpose(Chi)); #TODO minval? Marcus-check
	#minVal = np.max(np.transpose(chi))
	c_f = np.amax(np.transpose(chi))

	return (c_f, indic, chi, rot_mat)


#===============================================================================
def symmetrize(matrix, weights, correct_weights=False, error=1E-02):
	weights_new = weights
 
	if correct_weights:
		diff = 1		
		while diff >= error:
  			# left eigenvector of matrix yields weights_new
			weights_new = np.dot(np.transpose(matrix), weights)
			# iterate until we are below the error
			diff = np.linalg.norm(weights - weights_new, 2)
			weights = weights_new

	diff = 1
	while diff >= error:
		# scaling row sum of matrix to the respective weight yields matrix_new
		matrix_new = np.dot( np.diag( (1/np.sum(matrix, axis=1))*weights ), matrix )
		# make matrix_new symmetric
		matrix_new = 0.5*( matrix_new + np.transpose(matrix_new) )
		# iterate until we are below the error
		diff = np.linalg.norm(matrix - matrix_new, 2)
		matrix = matrix_new
		
	# make matrix_new stochastic
	matrix_new = np.dot( np.diag( (1/np.sum(matrix_new, axis=1)) ), matrix_new )
	
	return(matrix_new, weights_new)


#===============================================================================
def orthogonalize(eigenvalues, eigenvectors, weights):
	perron = 0
	# count degeneracies
	for eigval in eigenvalues:
		if eigval > 0.9999:
			perron += 1
		else:
			break

	if perron > 1:
		# look for most constant eigenvector
		max_scal = 0.0
	
		for i in range(perron):
			scal = np.dot( np.transpose(eigenvectors[:,i]), weights )
			if np.abs(scal) > max_scal:
				max_scal = np.abs(scal)
				max_i = i

		# swap non-constant eigenvector
		eigenvectors[:,max_i] = eigenvectors[:,0]
		eigenvectors[:,0] = np.ones(eigenvectors.shape[1])

		# weight-orthogonalize all other eigenvectors
		for i in range(1, perron):
			for j in range(i):
				scal = np.dot( np.dot( np.transpose(eigenvectors[:,j]), np.diag(weights) ), eigenvectors[:,i] ) 
				eigenvectors[:,i] -= scal * eigenvectors[:,j]

	# normalize
	for eigvec in np.transpose(eigenvectors):
		weighted_norm = np.dot( np.dot( np.transpose(eigvec), np.diag(weights) ), eigvec )
		eigvec /= np.sqrt(weighted_norm)

	eigenvectors[:,0] = np.ones(eigenvectors.shape[1])
	return eigenvectors


#===============================================================================
def opt_soft(eigvectors, rot_matrix, n_clusters):

	# only consider first n_clusters eigenvectors
	eigvectors = eigvectors[:,:n_clusters]
	
	# crop first row and first column from rot_matrix
	rot_crop_matrix = rot_matrix[1:,1:]
	
	(x, y) = rot_crop_matrix.shape
	
	# reshape rot_crop_matrix into linear vector
	rot_crop_vec = np.reshape(rot_crop_matrix, x*y)

	# target function for optimization
	def susanna_func(rot_crop_vec, eigvectors):
		# reshape into matrix
		rot_crop_matrix = np.reshape(rot_crop_vec, (x, y))
		# fill matrix
		rot_matrix = fill_matrix(rot_crop_matrix, eigvectors)

		result = 0
		for i in range(0, n_clusters):
			for j in range(1, n_clusters):
				result += np.power(rot_matrix[j,i], 2) / rot_matrix[0,i]
		return(-result)


	from scipy.optimize import fmin
	rot_crop_vec_opt = fmin( susanna_func, rot_crop_vec, args=(eigvectors,) )
	
	rot_crop_matrix = np.reshape(rot_crop_vec_opt, (x, y))
	rot_matrix = fill_matrix(rot_crop_matrix, eigvectors)

	return(rot_matrix)


#===============================================================================
def fill_matrix(rot_crop_matrix, eigvectors):

	(x, y) = rot_crop_matrix.shape

	row_sums = np.sum(rot_crop_matrix, axis=1)	
	row_sums = np.reshape(row_sums, (x,1))

	# add -row_sums as leftmost column to rot_crop_matrix 
	rot_crop_matrix = np.concatenate((-row_sums, rot_crop_matrix), axis=1 )

	tmp = -np.dot(eigvectors[:,1:], rot_crop_matrix)

	tmp_col_max = np.max(tmp, axis=0)
	tmp_col_max = np.reshape(tmp_col_max, (1,y+1))

	tmp_col_max_sum = np.sum(tmp_col_max)

	# add col_max as top row to rot_crop_matrix and normalize
	rot_matrix = np.concatenate((tmp_col_max, rot_crop_matrix), axis=0 )
	rot_matrix /= tmp_col_max_sum

	return rot_matrix


#===============================================================================
#EOF
