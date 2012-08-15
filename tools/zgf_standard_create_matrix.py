#!/usr/bin/python
# -*- coding: utf-8 -*-


from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import Option, OptionsList

import sys
import numpy as np

from ZIBMolPy.gromacs import read_mdp_file


upper_threshold_default=0.6
lower_threshold_default=0.4

options_desc = OptionsList([	
	Option("n", "timestep", "int", "Timestep tau", default=1, min_value=1)
	])

#===============================================================================
def main():

	options = options_desc.parse_args(sys.argv)[0]

	pool = Pool()
	npz_file = np.load(pool.chi_mat_fn)
	chi_matrix = npz_file['matrix']
	n_clusters = npz_file['n_clusters']

	mdp = read_mdp_file(pool.mdp_fn)
	nsteps = float(mdp['nsteps'])
	nstxout = float(mdp['nstxout'])
	dt= float(mdp['dt'])

	active_nodes = pool.where("isa_partition")

	#initiliase Schuette Matrix P
	P = np.zeros(shape=(len(active_nodes),len(active_nodes)))

	timestep = options.timestep

	index_i=0
	for node_i in active_nodes:

		ready_nodes = pool.where("state == 'ready' and parent!=None and parent.name=='%s'"%node_i.name)

		for ready_node in ready_nodes:			

			extension_length = len(ready_nodes[0].trajectory)/(ready_nodes[0].extensions_counter+1)
			extension_amount = ready_nodes[0].extensions_counter+1
			
			index_j=0
			for node_j in active_nodes:
				for extension_counter in range(0,extension_amount):
					frame_num 	   = extension_counter*extension_length + timestep
					phi_value	   = get_phi(ready_node.trajectory.getframe(frame_num),node_j)
					P[index_i,index_j] = P[index_i,index_j]+phi_value
				index_j=index_j+1
		index_i=index_i+1
				
	#normalise P
	for i in range(0,len(active_nodes)):
		factor = sum(P[i,:])
		P[i,:] = (1/factor) * P[i,:]
	
	print P



	

	

		
#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF


