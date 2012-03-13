#! /usr/bin/env python
# -*- coding: utf-8 -*-

from scipy.io import savemat
import sys
import numpy as np

#===============================================================================
def main():
	if(len(sys.argv) != 3):
		print("Takes a npz-file from NumPy and converts it into a mat-file for Matlab.")
		print("Usage: npz2mat.py <npz-input-file> <mat-output-file>")
		sys.exit(1)
	
	npz_fn = sys.argv[1]
	mat_fn = sys.argv[2]
	
	print("Opening: %s"%npz_fn)
	data = np.load(npz_fn)
	
	mat_dict = dict()
	for i in data.files:
		print("Found matrix: "+str(i))
		mat_dict[i] = data[i] 
	
	print("Writing: %s"%mat_fn)	
	savemat(mat_fn, mat_dict)
	
	
	
	
#===============================================================================
if(__name__=="__main__"):
	main()
	
#EOF
