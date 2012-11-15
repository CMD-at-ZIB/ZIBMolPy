#!/usr/bin/python
# -*- coding: utf-8 -*-

from ZIBMolPy.pool import Pool
from ZIBMolPy.node import Node
from ZIBMolPy.phi  import get_phi
from ZIBMolPy.ui import Option, OptionsList

import zgf_setup_nodes
import zgf_grompp

import sys
import numpy as np

#===============================================================================
def main():

	pool = Pool()
	npz_new_file = np.load(pool.qc_mat_fn)

	npz_file=np.load(pool.analysis_dir+"p_pdb.npz")
	P = npz_file['matrix']
	print P
	X = np.around(P,decimals=4)
	print X

#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

