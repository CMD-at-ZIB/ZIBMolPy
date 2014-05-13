#!/usr/bin/env python
# -*- coding: utf-8 -*-


import xdrlib
import numpy as np
from os import path

#http://code.google.com/p/mdanalysis/source/browse/trunk/src/xdrfile/xdrfile_trr.c
# gromacs/src/gmxlib/trnio.c

# using big-endian due to XDR-standard
#http://tools.ietf.org/html/rfc1014
#http://en.wikipedia.org/wiki/External_Data_Representation
		
DIM = 3
GROMACS_MAGIC = 1993
VERSION = "GMX_trn_file"
DTYPE_FLOAT = np.dtype(">f4")
DTYPE_DOUBLE = np.dtype(">f8")


#===============================================================================
class TrrFile(object):
	def __init__(self, filename):
		assert(filename.endswith(".trr"))
		self.filename = filename
		self.filesize = path.getsize(filename)
		self.fh = open(self.filename, "rb")
		self.first_frame = TrrFrame(self) 	
	
	#---------------------------------------------------------------------------
	def close(self):
		self.fh.close()
		
	#---------------------------------------------------------------------------
	def count_frames(self):
		frame = self.first_frame
		while(frame.has_next()):
			frame = frame.next()
		return(frame.number+1)
	
	#---------------------------------------------------------------------------
	def goto_frame(self, n):
		frame = self.first_frame
		for dummy in range(n):
			frame = frame.next()
		return(frame)
	
	#---------------------------------------------------------------------------
	def read_frames(self, atoms_start=0, atoms_end=None, read_boxes=False):
		"""
		@param read_boxes: introduced to keep backward-compatibility
		"""
		frames_x = []
		frames_box = []
		frame = self.first_frame
		while(True):
			frames_x.append(   frame.read_positions(atoms_start, atoms_end) )
			if(read_boxes):
				frames_box.append( frame.read_box() )
			if(not frame.has_next()): break
			frame = frame.next()
		
		if(read_boxes):
			return(np.array(frames_x), np.array(frames_box))
		else:
			return(np.array(frames_x))
	
		
#===============================================================================
class TrrFrame(object):
	""" Frame-numbers are zero-based """
	def __init__(self, trr_file, number=0):
		self.f = trr_file
		self.number = number
		self.start = self.f.fh.tell()
			
		u = xdrlib.Unpacker(self.f.fh.read(100))
		assert(u.unpack_int() == GROMACS_MAGIC) 
		assert(u.unpack_int() == len(VERSION)+1)
		assert(u.unpack_string() == VERSION)
		
		# .._size variables are always in byte
		
		self.ir_size	= u.unpack_int() #inputrec
		self.e_size		= u.unpack_int() #energies
		self.box_size	= u.unpack_int()
		self.vir_size	= u.unpack_int() #don't knows reads DIM vectors into pv
		self.pres_size	= u.unpack_int() #don't knows reads DIM vectors into pv
		self.top_size	= u.unpack_int() #topology
		self.sym_size	= u.unpack_int() #symbol
		self.x_size		= u.unpack_int() #positions
		self.v_size		= u.unpack_int() #velocities
		self.f_size		= u.unpack_int() #forces
		self.natoms		= u.unpack_int()
		self.step 		= u.unpack_int()
		self.nre		= u.unpack_int()
		
		if(self.ir_size != 0): raise(NotImplementedError)
		if(self.e_size != 0): raise(NotImplementedError)
		if(self.vir_size != 0): raise(NotImplementedError)
		if(self.pres_size != 0): raise(NotImplementedError)
		if(self.f_size != 0): raise(NotImplementedError)
		
		self.bDouble = (self._nFloatSize() == DTYPE_DOUBLE.itemsize)
		if(self.bDouble):
			self.dtype = DTYPE_DOUBLE
			self.t = u.unpack_double()
			self.Lambda = u.unpack_double()
		else:
			self.dtype = DTYPE_FLOAT
			self.t = u.unpack_float()
			self.Lambda = u.unpack_float()
		
		#just caching some results...
		#TODO: check if they are all needed/used
		#self.body_part_sizes = (self.box_size, self.vir_size, self.pres_size, self.x_size, self.v_size, self.f_size)
		self.header_size = u.get_position()
		self.body_part_sizes = (self.box_size, self.x_size, self.v_size, self.f_size)
		self.body_part_indices = np.cumsum(self.body_part_sizes)[:-1] / self.dtype.itemsize
		self.body_size = sum(self.body_part_sizes)
		self.body_length = self.body_size / self.dtype.itemsize
		self.frame_size = self.header_size + self.body_size
		self.end = self.start + self.frame_size
		
	#---------------------------------------------------------------------------
	def _nFloatSize(self):
		nflsize = 0
		if(self.box_size):
			nflsize = self.box_size/(DIM*DIM)
		elif(self.x_size):
			nflsize = self.x_size/(self.natoms*DIM)
		elif(self.v_size):
			nflsize = self.v_size/(self.natoms*DIM)
		elif(self.f_size):
			nflsize = self.f_size/(self.natoms*DIM)
		else: 
			raise(Exception("unable to guess float-size"))
	  
		if(nflsize not in (DTYPE_FLOAT.itemsize, DTYPE_DOUBLE.itemsize)):
			raise(Exception("found strange float-size"))
		
		return(nflsize)
	
	#---------------------------------------------------------------------------
	def next(self):
		self.f.fh.seek(self.end)
		return(TrrFrame(self.f, self.number+1))
	
	#---------------------------------------------------------------------------	
	def has_next(self):
		return(self.f.filesize > self.end)

	#---------------------------------------------------------------------------
	def read_box(self):
		assert(self.box_size == DIM*DIM*self.dtype.itemsize) # frame has box
		self.f.fh.seek(self.start + self.header_size)
		box = np.fromfile(self.f.fh, self.dtype, count=self.box_size/self.dtype.itemsize)
		return( box.reshape(DIM, DIM) )
		
	#---------------------------------------------------------------------------
	def read_positions(self, atoms_start=0, atoms_end=None):
		""" reads efficiently only a range of atoms - seeks past all others (e.g. water) """
		assert(self.x_size == DIM*self.natoms*self.dtype.itemsize) # frame has positions
		if(atoms_end==None):
			atoms_end = self.natoms
		atoms_range = atoms_end - atoms_start
		assert(0 <= atoms_range and atoms_range <= self.natoms)
		self.f.fh.seek(self.start + self.header_size + self.box_size + atoms_start*DIM*self.dtype.itemsize)
		x = np.fromfile(self.f.fh, self.dtype, count=atoms_range*DIM)
		return( x.reshape(atoms_range, DIM) )
	
	#---------------------------------------------------------------------------
	@property
	def raw_data(self):
		""" Returns the raw binary data of this frame. """
		self.f.fh.seek(self.start)
		return(self.f.fh.read(self.frame_size))
		
#===============================================================================
#EOF
