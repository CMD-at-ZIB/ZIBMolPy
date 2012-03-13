#! /usr/bin/env python
# -*- coding: utf-8 -*-


from ZIBMolPy.io.trr import TrrFile
from scipy.io import savemat
import sys

def main():
	if(len(sys.argv) != 3):
		print("Takes a trr-trajectory and converts it into a mat-file for matlab.")
		print("Usage: trr2mat.py <trr-input-file> <mat-output-file>")
		sys.exit(1)
	
	trr_fn = sys.argv[1]
	mat_fn = sys.argv[2]
	
	print("Opening: %s"%trr_fn)
	
	f = TrrFile(trr_fn)
	data = f.read_frames()
	f.close()
	print("Loaded trr-file with shape: "+str(data.shape))
	
	print("Writing: %s"%mat_fn)	
	savemat(mat_fn, {"trr":data})

	
	
	
	
if(__name__=="__main__"):
	main()
	
#EOF
