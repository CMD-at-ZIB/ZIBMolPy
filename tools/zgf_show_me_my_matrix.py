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
	#npz_file = np.load(pool.analysis_dir+"p_pdb.npz")
	#P = npz_file['matrix']
	#C = npz_file['count']
	npz_new_file = np.load(pool.qc_mat_fn)
	QC= npz_new_file['matrix']

	print "---- --- Q_C Matrix Begin --- ----"
	print QC
	print "---- --- Q_C Matrix End --- ----"



	npz_file=np.load(pool.analysis_dir+"p_pdb.npz")
	P = npz_file['matrix']
	print P
	X = np.around(P,decimals=4)
	print X

	H= np.zeros(shape=(9,9))
	#H_C = np.zeros(shape=(9,9))
	#switch Matrix
	for i in range(0,9):
		for j in range(0,9):
			i=i+1
			if(i==1):
				k=3
			if(i==2):
				k=5
			if(i==3):
				k=2
			if(i==4):
				k=8
			if(i==5):
				k=9
			if(i==6):
				k=7
			if(i==7):
				k=1
			if(i==8):
				k=6
			if(i==9):
				k=4
			k=k-1
			i=i-1

			j=j+1
			if(j==1):
				l=3
			if(j==2):
				l=5
			if(j==3):
				l=2
			if(j==4):
				l=8
			if(j==5):
				l=9
			if(j==6):
				l=7
			if(j==7):
				l=1
			if(j==8):
				l=6
			if(j==9):
				l=4
			j=j-1
			l=l-1
			H[i,j]=X[k,l]
			#H_C[i,j]=C[k,l]

	print H
	#print "Counting"
	#print H_C
#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

