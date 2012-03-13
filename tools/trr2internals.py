#! /usr/bin/env python
# -*- coding: utf-8 -*-


from ZIBMolPy.internals import Converter, DihedralCoordinate, LinearCoordinate
import numpy as np
import sys
import math
from scipy.io import savemat
from optparse import OptionParser


#===============================================================================
def main():

	usage_txt = "\nTakes trr-trajectory and internals-definition and outputs timeseries as npz- or mat-file.\nOutput-filetype is decided based on given filename-extension.\n\n   %prog [options] <trr-input-file> <int-file> <output-file>"
	parser = OptionParser(usage=usage_txt, version="%prog 0.1")
	parser.add_option("-d", "--degrees", action="store_true", default=False, help="save dihedrals in [deg]")

	(options, args) = parser.parse_args()

	if(len(args) != 3):
		parser.error("incorrect number of arguments")

	if(options.degrees):
		print("\nDihedral angles will be saved in [deg].\n")
	else:
		print("\nDihedral angles will be saved in [rad].\n")

	trr_fn = args[0]
	internals_fn = args[1]
	out_fn = args[2]

	converter = Converter(internals_fn)
	all_frames_int = converter.read_trajectory(trr_fn)
	print("loaded trr-file with %d frames" % len(all_frames_int))

	if(options.degrees):
		all_frames_int.dihedral_array = np.degrees(all_frames_int.dihedral_array)

	dih_labels = [c.label for c in converter.dihedrals]
	lin_labels = [c.label for c in converter.linears]

	if(out_fn.endswith(".npz")):
		print("Writing NumPy file: "+out_fn)
		if (all_frames_int.has_dihedrals and all_frames_int.has_linears):
			np.savez(out_fn, linears=all_frames_int.linear_array, linear_labels=lin_labels, dihedrals=all_frames_int.dihedral_array, dihedral_labels=dih_labels)
		elif(all_frames_int.has_dihedrals):
			np.savez(out_fn, dihedrals=all_frames_int.dihedral_array, dihedral_labels=dih_labels)
		else:
			np.savez(out_fn, linears=all_frames_int.linear_array, linear_labels=lin_labels)	
	elif(out_fn.endswith(".mat")):
		print("Writing Matlab file: "+out_fn)
		if (all_frames_int.has_dihedrals and all_frames_int.has_linears):
			savemat(out_fn, {'linears':all_frames_int.linear_array, 'dihedrals':all_frames_int.dihedral_array})
		elif(all_frames_int.has_dihedrals):
			savemat(out_fn, {'dihedrals':all_frames_int.dihedral_array})
		else:
			savemat(out_fn, {'linears':all_frames_int.linear_array})
	else:
		raise(Exception("Unkown output filetype: "+out_fn))
		

#===============================================================================
if __name__ == '__main__':
	main()

#EOF
