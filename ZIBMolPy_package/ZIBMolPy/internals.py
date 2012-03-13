# -*- coding: utf-8 -*-

"""
Classes for working with internal coordinates.

The int File Format
===================
	An internals file (int-file) contains the definition of the internal coordinates used in the simulation.
	So far, dihedral angles (dihedrals) and distances (linears) are supported.

	The first line of an int-file contains the list of relevant dihedrals defined by the four atoms involved, e. g.::
		(0-1-2-4),(1-2-3-4), ...

	The second line of an int-file contains the list of relevant linears defined by the two atoms involved, e. g.::
		(0-4),(20-46), ...
		
Atom Indices
============
Please note:

	1. Atom indices in int-files start with zero.
	
	2. Atom indices in int-files refer to the absolut atom indices as can be found in the coordinate file of the complete system, and not on a per-molecule topology basis.
	

Labels
======
	Each internal coordinate comes with a standard label stating its type and index. Optional custom labels can be specified within the int-file as::
		(0-1-2-4){'label':'cat'},(1-2-3-4), ...

	which will overwrite the standard label "dih_000" with "cat".

Weights and Offsets
===================
	Angle coordinates can take on only values between -2S{pi} and +2S{pi}.
	But distance coordinates can in principle take on any positiv value.
	This can lead to problems where distance coordinates are overly dominate.
	
	Therefore, distance coordinates also offer a weight and an offset paramter::
		(0-4){'weight':2.0, 'offset':1.5},(20-46){'label':'puppy', 'weight':2.0, 'offset':-0.4}
	
	See also L{LinearCoordinate}.


Custom Coordinate
=================
One can create his own subclasses of L{InternalCoordinate}.

They can be addressed in the int-file by providing a 'type' argument e.g.::
	(3-1-4){'type':'Funny', 'foobar':'cat'},...

This will call the following constructor::
	FunnyCoordinate(3, 1, 4, foobar='cat')
	
Besides writting a subclass one also has make some adjustments to the code 
in L{zgf_create_nodes}, which determines the associated gromacs-restraints.

"""

import numpy as np
import re
import math
from ZIBMolPy.io.pdb import PdbFile
from ZIBMolPy.io.trr import TrrFile
from ZIBMolPy.utils import all #pylint: disable=W0622
from warnings import warn

#===============================================================================
class InternalArray(object):
	def __init__(self, converter, array, frameweights=None):
		""" dim[0] = frames    dim[1] = coordinate """
		assert(array.ndim == 2)
		assert(array.shape[1] == len(converter))
		assert(np.all(np.isfinite(array))) #here is a good place to catch those
				
		if(frameweights != None):
			assert(frameweights.ndim == 1)
			assert(frameweights.shape[0] == array.shape[0])
			assert(np.all(np.isfinite(frameweights)))
		
		self._array = array
		self._converter = converter
		self._frameweights = frameweights
	
	
	#---------------------------------------------------------------------------
	@property
	def frameweights(self):
		""" read-only access """
		return(self._frameweights)
	
	@property
	def array(self):
		""" read-only access """
		return(self._array)
	
	@property
	def converter(self):
		""" read-only access """
		return(self._converter)
	
	
	#---------------------------------------------------------------------------
	@staticmethod	
	def _resolve_key(key):
		""" used by __getitem__ and __setitem__ """
		if(isinstance(key, tuple)):
			if(isinstance(key[1], InternalCoordinate)):
				key = list(key)
				key[1] = key[1].index 
		return(key)
	
	def __setitem__(self, key, value):
		key = self._resolve_key(key)
		self.array[key] = value
	
	def __getitem__(self, key):
		key = self._resolve_key(key)
		return(self.array[key])

	#---------------------------------------------------------------------------
	def __str__(self):
		return("InternalArray: "+str(self.array.shape))

	def __repr__(self):
		return("InternalArray("+repr(self.converter)+", "+repr(self.array)+")")
	
	def frames(self):
		""" @return: an iterator for all frames """
		class FramesIterator(object):
			def __init__(self, intarray):
				self.intarray = intarray
				self.current_frame_idx = -1
			def __iter__(self):
				return self
			def	next(self):
				self.current_frame_idx += 1
				if( self.current_frame_idx >= len(self.intarray) ):
					raise StopIteration
				#print self.current_frame_idx
				return( self.intarray.getframe(self.current_frame_idx) )
		return(FramesIterator(self))


	@property
	def n_frames(self):
		""" the number of frames """
		return(self.array.shape[0])
	
	def __len__(self):
		""" @return: the number of frames"""
		return(self.array.shape[0])
	
	@property
	def has_frameweights(self):
		return(self.frameweights != None)
		
	def mean_weighted(self):
		assert(self.has_frameweights)
		# http://en.wikipedia.org/wiki/Mean_of_circular_quantities
		parts = [c.mean(self.array[:,i], self.frameweights) for i, c in enumerate(self.converter)]
		new_array = np.column_stack(parts)
		return(InternalArray(self.converter, new_array))
		
	def mean(self):
		# http://en.wikipedia.org/wiki/Mean_of_circular_quantities
		parts = [c.mean(self.array[:,i]) for i, c in enumerate(self.converter)]
		new_array = np.column_stack(parts)
		return(InternalArray(self.converter, new_array))
	
	def var_weighted(self):
		""" var over all frames, per internal """
		assert(self.has_frameweights)
		diff =  self - self.mean()
		new_array = np.average(np.square(diff.array), axis=0, weights=self.frameweights)
		return(InternalArray(self.converter, new_array[None,:]))	
	
	def var(self):
		diff =  self - self.mean()
		new_array = np.average(np.square(diff.array), axis=0)
		return(InternalArray(self.converter, new_array[None,:]))	
	
	def merged_var(self):
		""" var over all frames, all internals merged
			@return: a number """
		diff =  self - self.mean()
		return(np.average(diff.norm2(), axis=0))	
	
	def merged_var_weighted(self):
		""" var over all frames, all internals merged
			@return: a number """ 
		assert(self.has_frameweights)
		diff =  self - self.mean()
		return(np.average(diff.norm2(), axis=0, weights=self.frameweights))

	def norm(self):
		return(np.sqrt(self.norm2()))

	def norm2(self):
		""" This mixes dihedral and linear values!!!
			@return: a normal Numpy-Array""" 
		return( np.sum(np.square(self.array), axis=1) )

	def square(self):
		return(InternalArray(self.converter, np.square(self.array), self.frameweights))

	def __sub__(self, other):
		assert(isinstance(other, InternalArray))
		assert(self.converter == other.converter)
		parts = [c.sub(self.array[:,i], other.array[:,i]) for i, c in enumerate(self.converter)]
		new_array = np.column_stack(parts)
		return(InternalArray(self.converter, new_array))

	def __div__(self, other):
		assert(isinstance(other, InternalArray))
		assert(self.converter == other.converter)
		return(InternalArray(self.converter, self.array/other.array))
	
	def getframe(self, frame_idx):
		assert(isinstance(frame_idx, int))
		return( self.getframes((frame_idx,)) )

	def getframes(self, frame_indices):
		""" Expects a list of frame-indices. Returns an new InternalArray containing only those frames."""
		assert(all([isinstance(i, int) for i in frame_indices]))
		if(self.has_frameweights):
			return(InternalArray(self.converter, self.array[frame_indices, :], self.frameweights[frame_indices,:]))
		return(InternalArray(self.converter, self.array[frame_indices, :]))

	def array_split(self, n_segments):
		""" Attempts to split self into n_segments InternalArrays of equal size """
		assert(isinstance(n_segments, int))
		parts_a = np.array_split(self.array, n_segments, axis=0)
		if(self.has_frameweights):
			parts_w = np.array_split(self.frameweights, n_segments, axis=0)
			return([ InternalArray(self.converter, a, w) for (a,w) in zip(parts_a, parts_w) ])
		return([ InternalArray(self.converter, a) for a in parts_a ])

	# accepts coordinate-objects or an integer (=coordinate-index)
	def getcoord(self, coordinate):
		""" Expects a coordinate-index or a coordinate-object.
		Returns all values that belong to coordinate"""
		if(isinstance(coordinate, InternalCoordinate)):
			coordinate = self.converter.index(coordinate)
		assert(isinstance(coordinate, int))
		value = self.array[:, coordinate]
		if(value.size == 1):
			value = value[0] #TODO: a double-edged sword
		return(value)
		
	def copy(self):
		""" Returns an indepent copy """
		if(self.has_frameweights):
			return( InternalArray(self.converter, np.copy(self.array), np.copy(self.frameweights) ) )
		return( InternalArray(self.converter, np.copy(self.array)) )

	@classmethod
	def stack_frames(cls, arrays):
		arrays = list(arrays) #could be a generator
		assert(all(isinstance(a, InternalArray) for a in arrays))
		c = arrays[0].converter
		has_fw = arrays[0].has_frameweights
		assert(all(c == a.converter for a in arrays))
		assert(all(has_fw == a.has_frameweights for a in arrays))
		new_array = np.row_stack([a.array for a in arrays])
		if(has_fw):
			new_frameweights = np.concatenate([a.frameweights for a in arrays])
			return(InternalArray(c, new_array, new_frameweights))
		return(InternalArray(c, new_array))
		
	
	#---------------------------------------------------------------------------
	#TODO: remove deprecated methods
	
	@property
	def n_dihedrals(self):
		"""
		the number of dihedral internals
		@deprecated:
		"""
		warn("deprecated", DeprecationWarning)
		return(self.converter.n_dihedrals)
	
	@property	
	def n_linears(self):
		"""
		the number of linear internals
		@deprecated:
		"""
		warn("deprecated", DeprecationWarning)
		return(self.converter.n_linears)

	@property	
	def has_dihedrals(self):
		"""
		True if dihedral internals exist, else False
		@deprecated:
		"""
		warn("deprecated", DeprecationWarning)
		return(self.n_dihedrals > 0)
		
	@property
	def has_linears(self):
		"""
		True if linear internals exist, else False
		@deprecated:
		"""
		warn("deprecated", DeprecationWarning)
		return(self.n_linears > 0)
	
	
	@property
	def dihedral_array(self):
		""" @deprecated: """
		warn("deprecated", DeprecationWarning)
		return(self.array[:, :self.n_dihedrals])

	@property
	def linear_array(self):
		""" @deprecated: """
		warn("deprecated", DeprecationWarning)
		return(self.array[:, self.n_dihedrals:])
			
		
#===============================================================================
class PbcResolver(object):
	""" 
	Resolves periodic boundary conditions by explicitly calculating all 27 
	possible images and applying the minimum image convention.
	Actually, there are only 26 images plus the original. 
	In general the box-geometry can change with every frame of a trajectory - e.g. when a 
	U{barostat <http://www.gromacs.org/Documentation/Terminology/Barostats>} is used.
	Therefore the 27 shift-vectors, which translate the coordinates to the images,
	are calculated for each frame seperately. These shift-vectors are only 
	calculated once by the constructor and then used 
	by e.g. L{rvec_sub}.
	
	Please note, that the more fancy (non cubic) box-types have less than 26 neighboring boxes.
	Currently, we do not take advantage of this - so there is room for improvments.
	
	@see: U{Gromacs manual 4.5.4 Chapter 3<http://www.gromacs.org/@api/deki/files/152/=manual-4.5.4.pdf#page=29>}
	@see: Bekker, Dijkstra, Renardus, Berendsen:
	U{An Efficient, Box Shape Independent Non-Bonded Force
	and Virial Algorithm for Molecular Dynamics
	<http://dx.doi.org/10.1080/08927029508022012>}
	"""
		
	def __init__(self, frame_boxes):
		""" 
		@param frame_boxes: box-vectors for each frame of a trajectory
		@type  frame_boxes: numpy.ndarray of shape(n_frames, 3, 3), where the last axis denotes x,y,z.
		"""
		assert(frame_boxes.ndim == 3)
		assert(frame_boxes.shape[1] == 3)
		assert(frame_boxes.shape[2] == 3)
		
		# enforce the gromacs-convention for box-vectors 
		assert(np.all(frame_boxes[:,0,1] == 0.0))
		assert(np.all(frame_boxes[:,0,2] == 0.0))
		assert(np.all(frame_boxes[:,1,2] == 0.0))
		
		# calc all possible shifts for each frame
		self._has_box = True
		if(np.all(frame_boxes==0)):
			#print("found no box-vectors")
			self._has_box = False
			return
			
		#TODO: could be optimised for non-rectancular boxtypes, as they have less neightbors
		# there are 27 possible images (in the most general case)
		k = np.array([(i,j,k) for i in (-1,0,1) for j in (-1,0,1) for k in (-1,0,1)])
		self._shifts = np.sum(k[:,None,:,None]*frame_boxes[None,:,:,:], axis=2)
		
		
	#---------------------------------------------------------------------------
	def rvec_sub(self, xi, xj):
		"""
		Calculates the vector difference between.
		@type xi: numpy.ndarray of shape (n_frames, 3)
		@type xj: numpy.ndarray of shape (n_frames, 3) 
		@return: the vector differences
		@rtype: numpy.ndarray of shape (n_frames, 3)
		"""
		assert(xi.ndim     == xj.ndim == 2)
		assert(xi.shape[0] == xj.shape[0])
		assert(xi.shape[1] == xj.shape[1] == 3)
		
		dx = xi - xj
		if(not self._has_box):
			return(dx)
		
		assert(xi.shape[0] == self._shifts.shape[1])
			
		a = dx[None,:,:] + self._shifts
		b = np.sum(np.square(a), axis=2)
		c = np.argmin(b, axis=0)
		
		dx_pbc = np.choose(c[:,None], a)
		return(dx_pbc)

#===============================================================================
class Converter(tuple):
	""" @note: Converter-Objects are read-only. """
	
	def __new__(cls, int_fn=None, coord_list=None):
		r""" Creates a new Converter either by loading it from file or by creating
		it from a given list of L{InternalCoordinate} objects.
		
		Note: exactly one of int_fn or coord_list has to be provided.
		
		@param int_fn: filename of an internal file
		@param coord_list: list of L{InternalCoordinate} objects.
		"""
		
		assert( (int_fn==None) ^ (coord_list==None) ) # "^" == XOR
				
		if(int_fn!=None): # load from file
			assert(int_fn.endswith(".int"))
			f = open(int_fn)
			raw = f.read()
			f.close()
			found_linear = False #needed to detect error and throw Exception - see below
			#NOTE: this does not detect badly formated entries
			
			coord_list = []
			for m in re.findall("(\([-0-9]*\))({([^}]*)})?",raw):
				args = eval(m[0].replace("-",","))
				kwargs = eval("{"+m[2]+"}")
				if(kwargs.has_key("type")):
					coordclass = globals()[kwargs["type"]+"Coordinate"]
					del(kwargs["type"])
					coord_list.append(coordclass(*args, **kwargs))
				elif(len(args) == 2):
					coord_list.append(LinearCoordinate(*args, **kwargs))
					found_linear = True
				elif(len(args) == 4):
					coord_list.append(DihedralCoordinate(*args, **kwargs))
					if(found_linear):
						raise(Exception("Found Dihedral after Linear Coordinate."))
				else:
					raise(Exception("Found strange internal coordinate: %s"%m[0]))
		
		for i in coord_list:
			assert(isinstance(i, InternalCoordinate))
		
		self = tuple.__new__(cls, coord_list)
		self.filename = int_fn
		
		for c in self:
			c._converter = self
		
		return(self)
	
	#----------------------------------------------------------------------------
	def __repr__(self):
		if(self.filename !=None):
			return("Converter(int_fn='%s')"%self.filename)
		else:
			list_str = ", ".join([repr(c) for c in self])
			return("Converter(coord_list=[%s])"%list_str)
	
	#----------------------------------------------------------------------------
	@property
	def dihedrals(self):
		""" @deprecated:  """
		warn("deprecated", DeprecationWarning)
		return([c for c in self if isinstance(c, DihedralCoordinate)])
	
	@property
	def linears(self):
		""" @deprecated:  """
		warn("deprecated", DeprecationWarning)
		return([c for c in self if isinstance(c, LinearCoordinate)])
	
	@property
	def n_dihedrals(self):
		""" @deprecated:  """
		warn("deprecated", DeprecationWarning)
		return(len(self.dihedrals))
	
	@property
	def n_linears(self):
		""" @deprecated: """
		warn("deprecated", DeprecationWarning)
		return(len(self.linears))
		
	#----------------------------------------------------------------------------
	def read_pdb(self, pdb_fn):
		""" Reads a pdb-file, resolves periodic boundary conditions
		with L{PbcResolver} and calculates internal coordinates.
		"""
		pdb = PdbFile(pdb_fn)
		frame_ext = pdb.read_coordinates()
		pbc = PbcResolver(pdb.read_box()[None,...])
		
		def dx_provider(atom1, atom2):
			ai = frame_ext[None,atom1,:]
			aj = frame_ext[None,atom2,:]
			return(pbc.rvec_sub(ai, aj))
			
		array = np.column_stack([ c.from_externals(dx_provider) for c in self ])
		return( InternalArray(self, array) )
		
	
	#----------------------------------------------------------------------------
	def read_trajectory(self, fn):
		"""
		Reads a trr-trajectory, resolves periodic boundary conditions
		with L{PbcResolver} and calculates internal coordinates.
				
		@param fn: filename of a gromacs trr trajectory.
		@return: L{InternalArray}
		"""
		required_atoms = set(sum([c.atoms for c in self], () ))	
		atoms_start = min(required_atoms)
		atoms_end   = max(required_atoms) + 1
		f_trr = TrrFile(fn)
		(frames_x, frames_box) = f_trr.read_frames(atoms_start, atoms_end, read_boxes=True)
		f_trr.close()
		pbc = PbcResolver(frames_box)
		
		def dx_provider(atom1, atom2):
			ai = frames_x[:,atom1-atoms_start,:]
			aj = frames_x[:,atom2-atoms_start,:]
			return(pbc.rvec_sub(ai, aj))
		
		array = np.column_stack([ c.from_externals(dx_provider) for c in self ])
		return( InternalArray(self, array) )
		
	#---------------------------------------------------------------------------
	# implementation for python 2.4
	def index(self, item):
		for (i,x) in enumerate(self):
			if(x==item):
				return(i)
		raise(ValueError("tuple.index(x): x not in list"))

	#---------------------------------------------------------------------------
	def serialize(self):
		"""
		Serialize this convert into a string of the L{int-file format <ZIBMolPy.internals>}.
		This is used by L{zgf_create_pool} when choosing the right weights and offsets
		for L{LinearCoordinate}s.
		"""
		
		return(",".join([c.serialize() for c in self]))		
		
			
#===============================================================================
class InternalCoordinate(object):
	def __init__(self, atoms, label):
		self._atoms = atoms
		self._label = label
		self._converter = None # set by the Converter.__init__
	
	def __repr__(self):
		out = self.__class__.__name__ + "("+", ".join([str(a) for a in self.atoms])
		if(self._label != None):
			out += ', label="%s"'%self.label
		return(out+")")
	
	def serialize(self):
		out = "("+ "-".join([str(a) for a in self.atoms]) + ")"
		if(self._label!=None):
			out += "{'label':'%s'}"%self._label
		return(out)
		
	def __str__(self):
		out = "{%s}"%self.label
		out += "("+"-".join([str(a) for a in self.atoms])+")"
		return(out)
	
	def __eq__(self, other):
		if(type(self) != type(other)):
			return False
		if(len(self.atoms) != len(other.atoms)):
			return False
		for (a,b) in zip(self.atoms, other.atoms):
			if(a != b):
				return False
		return(True)
		
	@property
	def index(self):
		return(self._converter.index(self))

	@property
	def atoms(self): 
		""" read-only property """
		return(self._atoms)

	@property
	def label(self):
		""" read-only property """
		if(self._label!=None):
			return(self._label)
		return("coord_%03d"%self.index)

	@property
	def plot_min_range(self):
		""" used by L{ZIBMolPy.pool.Pool.coord_range} """
		return(0.0, 0.0)

	@property
	def plot_max_range(self):
		""" used by L{ZIBMolPy.pool.Pool.coord_range} """
		return(None)

	
#===============================================================================
class DihedralCoordinate(InternalCoordinate):
	""" U{http://en.wikipedia.org/wiki/Dihedral_angle} """
	def __init__(self, atom0, atom1, atom2, atom3, label=None):
		atoms = (atom0, atom1, atom2, atom3)
		InternalCoordinate.__init__(self, atoms, label)
	
	#---------------------------------------------------------------------------
	def from_externals(self, dx_provider):
		#from gromacs-4.5.3/include/vec.h
		def cprod(a, b):
			return( [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]] )
			
		def iprod(a, b):
			return( a[0]*b[0]+a[1]*b[1]+a[2]*b[2] )

		def norm(a):
			return( np.sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]) )

		def gmx_angle(a, b):
			w = cprod(a,b)
			wlen  = norm(w)
			s = iprod(a,b)
			return( np.arctan2(wlen,s) )
		
		# transpose puts xyz onto the first axis - easier for broadcasting
		r_ij = dx_provider(self._atoms[0], self._atoms[1]).transpose()
		r_kj = dx_provider(self._atoms[2], self._atoms[1]).transpose()
		r_kl = dx_provider(self._atoms[2], self._atoms[3]).transpose()
		
		#from gromacs-4.5.3/src/gmxlib/bondfree.c line 991
		m = cprod(r_ij, r_kj)
		n = cprod(r_kj, r_kl)
		phi = gmx_angle(m,n)
		ipr = iprod(r_ij,n)
		sign= np.sign(ipr)
		phi = sign*phi
		return( np.array(phi) )
  
	#---------------------------------------------------------------------------
	@staticmethod
	def sub(a, b):
		""" equivialent to Gromacs 4.07 gmxlib/dihres.c """
		diffs = a - b
		m = np.mod(diffs + np.pi, 2*np.pi)
		return(m - np.pi)
			
	@staticmethod
	def mean(a, frameweights=None):
		""" U{http://en.wikipedia.org/wiki/Mean_of_circular_quantities} """
		dih_complex = np.exp(a*1j)
		dih_mean_complex = np.average(dih_complex, axis=0, weights=frameweights)
		dih_mean = np.angle(dih_mean_complex)
		return(dih_mean)

	@property
	def label(self):
		""" read-only property """
		if(self._label!=None):
			return(self._label)
		return("dih_%03d"%self.index)
	
	@property
	def plot_label(self):
		return("Degrees")
	
	@property
	def plot_min_range(self):
		""" used by L{ZIBMolPy.pool.Pool.coord_range} """
		return(-1*math.pi, math.pi)

	@property
	def plot_max_range(self):
		""" used by L{ZIBMolPy.pool.Pool.coord_range} """
		return(self.plot_min_range)

	def plot_scale(self, data):
		return(np.degrees(data))
		
	def plot_scaleinv(self, data):
		return(np.radians(data))
		
		
#===============================================================================
class LinearCoordinate(InternalCoordinate):
	def __init__(self, atom0, atom1, weight=1.0, offset=0.0, label=None):
		atoms = (atom0, atom1)
		InternalCoordinate.__init__(self, atoms , label)
		self._weight = weight
		self._offset = offset
	
	def __repr__(self):
		out = self.__class__.__name__ + "("+", ".join([str(a) for a in self.atoms])
		if(self._label != None):
			out += ', label="%s"'%self.label
		if(self.weight != 1.0):
			out += ', weight=%f'%self.weight
		if(self.offset != 0.0):
			out += ', offset=%f'%self.offset
		return(out+")")
	
	def serialize(self):
		out = "("+ "-".join([str(a) for a in self.atoms]) + ")"
		out_props = []
		if(self._label != None):
			out_props.append("'label':'%s'"%self._label)
		if(self.weight != 1.0):
			out_props.append("'weight':%f"%self.weight)
		if(self.offset != 0.0):
			out_props.append("'offset':%f"%self.offset)
		if(len(out_props) > 0):
			out += "{"+ ", ".join(out_props) +"}"		
		return(out)
		
	#---------------------------------------------------------------------------
	def from_externals(self, dx_provider):
		# transpose puts xyz onto the first axis - easier for broadcasting
		b = dx_provider(self._atoms[0], self._atoms[1]).transpose()
		b_norm = np.sqrt(b[0]*b[0]+b[1]*b[1]+b[2]*b[2])
		return(self._weight*(b_norm - self._offset))
	
	#---------------------------------------------------------------------------
	@staticmethod
	def sub(a, b):
		return(a - b)
	
	@staticmethod
	def mean(a, frameweights=None):
		lin_mean = np.average(a, axis=0, weights=frameweights)
		return(lin_mean)

	@property
	def label(self):
		""" read-only property """
		if(self._label!=None):
			return(self._label)
		return("lin_%03d"%self.index)

	def plot_scale(self, data):
		return(data/self._weight + self._offset)
		
	def plot_scaleinv(self, data):
		return(self._weight*(data-self._offset))
	
	@property
	def plot_label(self):
		return("nm")

	@property
	def weight(self):
		""" read-only property """
		return(self._weight)
		
	@property
	def offset(self):
		""" read-only property """
		return(self._offset)
	

#===============================================================================
#EOF
