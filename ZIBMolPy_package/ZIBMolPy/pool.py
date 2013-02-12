# -*- coding: utf-8 -*-

from ZIBMolPy.internals import InternalArray, Converter
import numpy as np
from os import path
from glob import glob
import traceback
from ZIBMolPy.node import Node
from ZIBMolPy import utils
import time
from ZIBMolPy.constants import BOLTZMANN, AVOGADRO

# needed to eval pool-desc.txt
import datetime #pylint: disable=W0611

#===============================================================================
class NodeList(list):
	def __init__(self, nodes=None):
		list.__init__(self)
		if(nodes != None):
			self.extend(nodes)
	
	#---------------------------------------------------------------------------
	@property
	def internals(self):
		arrays = [n.internals for n in self if hasattr(n, "internals")]
		if(len(arrays) == 0):
			return(None)
		return( InternalArray.stack_frames(arrays) )
	
	
	#---------------------------------------------------------------------------
	def where(self, query):
		""" very cool, smart query tool - runs a python-statement on every node """
		class Resolver(dict):
			def __init__(self, node):
				dict.__init__(self)
				self.node = node
			
			def __getitem__(self, key):
				if(key == "hasattr"): 
					return( lambda x: hasattr(self.node, x) )
				return(getattr(self.node, key))
		
		matches = [ n for n in self if eval(query, Resolver(n)) ] 
		return( NodeList(matches) )
	
	#---------------------------------------------------------------------------
	def coord_range(self, coord, num=360, lin_slack=True):
		"""
		Calculates the min and max values occurring for coordinate coord.
		
		It first queries L{InternalCoordinate.plot_range<ZIBMolPy.internals.InternalCoordinate.plot_range>}.
		If plot_range returns None,	it will look at the trajectories of all nodes instead.
		"""
		# ask the coordinate		
		if(coord.plot_range != None):
			(lower, upper) = coord.plot_range
			return( np.linspace(lower, upper, num=num) )

		# considering presampling-trajectory and position of all nodes
		values = self[0].pool.root.trajectory.getcoord(coord)
		(lower, upper) = (min(values), max(values))
		
		ints = self.internals # is None if no nodes besides root exist, yet
		if(ints != None):
			values = ints.getcoord(coord)
			(lower2, upper2) = (min(values), max(values))
			(lower, upper) = (min(lower, lower2), max(upper, upper2))
		slack = 0
		if lin_slack:
			slack = 0.1*(upper - lower)
		return( np.linspace(lower-slack, upper+slack, num=num) )

	#---------------------------------------------------------------------------
	def get_force_constant(self):
		return(self.alpha / self.thermo_beta) # in kJ/(mol rad^2)

	#---------------------------------------------------------------------------
	def multilock(self):
		nodes_lockable = self.where("not is_locked")
		for n in nodes_lockable:
			n.lock(guardtime=0)
			
		if(len(nodes_lockable) > 0):
			print("Waiting for Node-Multilock...")
			time.sleep(1)
			
		return(self.where("owns_lock"))

	#---------------------------------------------------------------------------
	def unlock(self):
		for n in self:
			n.unlock()

	#---------------------------------------------------------------------------
	def append(self, n):
		if(n not in self):
			list.append(self, n)

			
#===============================================================================
class Pool(NodeList):
	FORMAT_VERSION = 2
	
	# Singleton-Pattern
	_instance = None
	
	def __new__(cls):
		if(cls._instance != None):
			return(cls._instance)
			
		self = NodeList.__new__(cls)
		cls._instance = self
			
		# actual init-code
		NodeList.__init__(self)
		self._mtime = -1 # very old
		self._mtime_nodes = -1 # very old
		self.history = []
		self.format_version = self.FORMAT_VERSION
		
		if(path.exists(self.filename)):
			self.reload()
			self.reload_nodes()
		return(self)
		
	
	#---------------------------------------------------------------------------
	def __init__(self):
		#because of singleton, we must not(!) call the super constructor
		#pylint: disable=W0231
		pass 
	
	#---------------------------------------------------------------------------
	def reload(self):
		try:
			raw_persistent = eval(open(self.filename).read())
			self.__dict__.update(raw_persistent)
			self._mtime = path.getmtime(self.filename)
		except:
			traceback.print_exc()
			raise(Exception("Could not parse: "+self.filename))
			
		if(self.format_version > Pool.FORMAT_VERSION):
			raise(Exception("Pool was created with newer version of ZIBMolPy - run zgf_upgrade."))
			
	#---------------------------------------------------------------------------
	def reload_nodes(self):
		if(not path.exists("./nodes/")):
			return
			
		self._mtime_nodes = path.getmtime("./nodes")
		
		new_nodes = []
		for node_dir in sorted(glob("./nodes/*")):
			node_name = path.basename(node_dir)
			if(not path.exists(node_dir+"/"+node_name+"_desc.txt")):
				continue #ignoring not readily created nodes
			found_node = None 
			for n in self:
				if(n.name == node_name):
					found_node = n
			
			if(found_node == None):
				found_node = Node(node_name)
			new_nodes.append(found_node)
		
		self[:] = new_nodes

	
	#---------------------------------------------------------------------------
	def save(self):
		persistent = dict([ (k,v) for k,v in self.__dict__.items() if k[0]!='_' ])
		f = open(self.filename, "w")
		f.write(utils.pformat(persistent)+"\n")
		f.close()
		self._mtime = path.getmtime(self.filename)
	
	
	#---------------------------------------------------------------------------
	def __repr__(self):
		return( "<Pool len=%d>"% (len(self)) )
		
	def __str__(self):
		return(self.__repr__())

	#---------------------------------------------------------------------------
	@property
	def filename(self):
		return("pool-desc.txt")
	

	@property
	def mtime(self):
		return(self._mtime)
	
	@property
	def mtime_nodes(self):
		return(self._mtime_nodes)
	
	#---------------------------------------------------------------------------
	@property
	def converter(self): #TODO maybe cache instance
		if(hasattr(self, "int_fn")):
			return(Converter(self.int_fn))
		return(None)

	#---------------------------------------------------------------------------
	@property
	def root(self):
		for n in self:
			if(n.name == self.root_name):
				return(n)
		return(None)

	#---------------------------------------------------------------------------
	@property 
	def analysis_dir(self):
		return("./analysis/")
		
	@property 
	def s_mat_fn(self):	
		return(self.analysis_dir+"s_mat.npz")
		
	@property
	def s_corr_mat_fn(self): 
		return(self.analysis_dir+"s_corr_mat.npz")
			
	@property
	def chi_mat_fn(self): 
		return(self.analysis_dir+"chi_mat.npz")
		
	@property
	def qc_mat_fn(self): 
		return(self.analysis_dir+"qc_mat.npz")

	@property
	def pc_mat_fn(self): 
		return(self.analysis_dir+"pc_mat.npz")

	@property
	def p_mat_fn(self): 
		return(self.analysis_dir+"p_mat.npz")

	@property
	def thermo_beta(self):
		return 1/(self.temperature*BOLTZMANN*AVOGADRO)

#===============================================================================	
#EOF
