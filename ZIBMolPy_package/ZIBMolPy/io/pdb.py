# -*- coding: utf-8 -*-



r""" Reads coordinates from a PDB file.
	 For Details about the PDB-fileformat see:
	 U{http://www.wwpdb.org/documentation/format32/sect9.html}"""
		
	
import numpy as np
from math import cos, sin, sqrt, radians

#===============================================================================
class PdbFile(object):
	 
	def __init__(self, filename):
		assert(filename.endswith(".pdb"))
		self.filename = filename
	
	def read_box(self):
		"""
		Finds and parses the CRYST1 record from the head of the pdb-file.
		
		The record is search for within the first 1000 bytes of the file.
		The found box definition is converted to the gromacs notation by using a formula from
		U{this post <http://lists.gromacs.org/pipermail/gmx-users/2008-May/033944.html>} on the gromacs mailinglist.
		If no CRYST1 record is found, three zero-vectors are returned (just like gromacs does).
		
		@see: U{definition of pdb-format <http://deposit.rcsb.org/adit/docs/pdb_atom_format.html#CRYST1>}
		"""
		
		f = open(self.filename)
		head = f.read(1000)
		f.close()
		cryst1_lines = [l for l in head.splitlines() if l.upper().startswith("CRYST1")]
		if(len(cryst1_lines) == 0): 
			return(np.zeros(9).reshape(3,3))
		
		assert(len(cryst1_lines) == 1)
		cryst1_line = cryst1_lines[0]
		
		#pylint: disable=W0612		
		a			= float(cryst1_line[ 6:15])
		b			= float(cryst1_line[15:24])
		c			= float(cryst1_line[24:33])
		alpha		= float(cryst1_line[33:40])
		beta		= float(cryst1_line[40:47])
		gamma		= float(cryst1_line[47:54])
		space_group = cryst1_line[55:66]
		z_value		= cryst1_line[66:70]
				
		# from http://lists.gromacs.org/pipermail/gmx-users/2008-May/033944.html
		cosgam = cos(radians(gamma))
		singam = sin(radians(gamma))
		cosbet = cos(radians(beta))
		cosalp = cos(radians(alpha))
		v = sqrt(1.0 - cosalp**2 - cosbet**2 - cosgam**2 + 2.0*cosalp*cosbet*cosgam)*a*b*c
		xx = a
		xy = 0.0
		xz = 0.0
		yx = b*cosgam
		yy = b*singam
		yz = 0.0
		zx = c*cosbet
		zy = (c/singam)*(cosalp-cosbet*cosgam)
		zz = v/(a*b*singam)
		box = np.array([[xx, xy, xz],[yx, yy, yz],[zx, zy, zz]])
		
		# Angstroem (pdb) to nm (Gromacs and ZIBgridfree)
		return(0.1*box)
	
		
	#---------------------------------------------------------------------------
	def read_coordinates(self):
		r"@return: Cartesian coordinate in B{nanometers} as ndarray of shape (#atoms, 3)" 

		# we also need to read the first column, which is a string
		# in order to find ATOM and HETATM entries.
		# Lets create a record dtype. 
		dt = np.dtype([('name', np.str_, 6), ('x', np.float64), ('y', np.float64), ('z', np.float64)])
		widths = (6, 25, 8, 8, 8 ) #pdb uses fix-width columns
		a = np.genfromtxt(self.filename, dtype=dt, delimiter=widths, usecols=(0,2,3,4))
		is_atom = np.logical_or(a['name']=='ATOM  ', a['name']=='HETATM') 
		b = np.argwhere(is_atom)
		c = a[b][['x','y','z']].view(np.float64)
		assert(np.all(np.isfinite(c))) #decent check, whether s.th. went wrong.
		# Angstroem (pdb) to nm (Gromacs and ZIBgridfree)
		return(0.1*c)

#===============================================================================
#EOF