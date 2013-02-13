# -*- coding: utf-8 -*-


from os import path
import os

import numpy as np
import itertools
import traceback
import socket
import subprocess
import time
from ZIBMolPy import utils
from ZIBMolPy.phi import get_phi

#needed to eval node0042_desc.txt!!!
from ZIBMolPy.internals import InternalArray


#===============================================================================
# this is what gets written to node.lock_fn during a lock
def my_lock_signature():
	return( "%i %s"%(os.getpid(), socket.getfqdn()) )
    


#===============================================================================
class Store(dict):
	def __getattr__(self, name):
		return(self[name])
	
	def __setattr__(self, name, value):
		self[name] = value
		

#===============================================================================
class Node(object):
	#pylint: disable=W0404
	
	#Singleton-Pattern
	_instances = dict()

	def __new__(cls, name=None):
		""" Instanciates a node from a file, and (name=None) creates a new node
		
			Caution: Filenames are always given relative to the root-dir
			When no name is given, a new node is created. """
		
		if(name!=None and cls._instances.has_key(name)):
			return(cls._instances[name])
			
		if(name==None):  # a new node, lets find a name
			for i in itertools.count(0):
				name = "node%.4d"%i
				if(cls._instances.has_key(name)): continue# new nodes might not been saved, yet
				if(path.exists("./nodes/"+name)): continue
				break
					
		
		self = object.__new__(cls)
		cls._instances[name] = self

		#actuall init-code
		from ZIBMolPy.pool import Pool #avoids circular imports
		self._pool = Pool() #Pool is a singleton
		self._name = name
		self._tmp = Store() #for thing that need to be stored temporarly
		self._obs = Store()
		self.parent = None

		if(path.exists(self.dir)):
			self.reload()
		
		#self.pool.append(self) #register with pool
		return(self)
	
	#---------------------------------------------------------------------------
	@property
	def obs(self):
		return(self._obs)
	
	@property
	def tmp(self):
		return(self._tmp)
		
	@property
	def pool(self):
		return(self._pool)
		
	
	#---------------------------------------------------------------------------
	@property
	def name(self):
		return(self._name)
	
	#---------------------------------------------------------------------------
	@property
	def dir(self):
		return("nodes/"+self.name)
	
	@property
	def filename(self):
		return(self.dir+"/"+self.name+"_desc.txt")
	
	#---------------------------------------------------------------------------
	def reload(self):
		#pylint: disable=W0612
		
		#avoiding race-condition and respecting time-resoultion of 1s 
		t = time.time() - 1
		try:
			from numpy import array, float32, float64
			from ZIBMolPy.restraint import DihedralRestraint, DistanceRestraint
			from ZIBMolPy.internals import Converter
			f = open(self.filename)
			text = f.read()
			raw_persistent = eval(text)
			self.__dict__.update(raw_persistent)					
			if(path.exists(self.observables_fn)):
				raw_obs = eval(open(self.observables_fn).read())
				self.obs.update(raw_obs)
			
			self._mtime = t
		except:			
			traceback.print_exc()
			raise(Exception("Could not parse: "+self.filename))
			
	#---------------------------------------------------------------------------			
	def save(self):
		""" Save node to it's files (node0042_desc.txt and observables.txt) """
		#observables are save to a different file - so zgf_cleanup can remove them when updated
		if(not path.exists(self.dir)):
			os.makedirs(self.dir)
		else:
			assert(self.owns_lock)
			
		#save persistent node data
		persistent = dict([ (k,v) for k,v in self.__dict__.items() if k[0]!='_' ])
		split_temp = (self.filename).rsplit(".")
		name_temp = split_temp[0] + "temp" + split_temp[1]
		f = open(name_temp, "w")
		#f = open(self.filename, "w")
		f.write(utils.pformat(persistent)+"\n")
		f.close()
		os.rename(name_temp,self.filename)
		
		# save observables, if there are any
		if(len(self.obs) > 0):
			f = open(self.observables_fn, "w")
			f.write(utils.pformat(self.obs)+"\n")
			f.close()
		
		self._mtime = path.getmtime(self.filename)
	
	#---------------------------------------------------------------------------
	def __str__(self):
		return("<Node %s>"%self.name)
	
	def __eq__(self, other): #used e.g. in NodeList.append
		return( isinstance(other, type(self)) and other.name == self.name )
		
	def	__hash__(self):
		return(hash(self.name))
		
	def __repr__(self):
		return("Node(name='%s')"%self.name)

	#---------------------------------------------------------------------------
	@property
	def mtime(self):
		return(self._mtime)
	
	#---------------------------------------------------------------------------
	@property
	def observables_fn(self):
		return(self.dir+"/"+self.name+"_observables.txt")
	
	@property
	def lock_fn(self):
		return(self.dir+"/lock")

	@property
	def is_locked(self):
		""" Returns true when the node is lock (by whoever) """
		return(path.exists(self.lock_fn))
	
	@property
	def owns_lock(self):
		""" Returns true when I have got the lock """
		return(path.exists(self.lock_fn) and open(self.lock_fn).read() == my_lock_signature())
	
	@property
	def is_lock_valid(self):
		""" Tests if the process which holds the lock still exists """	
		lock_signature = open(self.lock_fn).read()
		(pid, host) = lock_signature.split()
			
		if(host !=  socket.getfqdn()):
			cmd = ["ssh", "-o", "UserKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=no", host, "test", "-x", "/proc/"+pid]
			return( subprocess.call(cmd) == 0 )
		
		return(path.exists("/proc/"+pid)) # linux-way to check if a pid exists :-)


	def lock(self, guardtime=1):
		if(path.exists(self.lock_fn)):
			return(False)
		f = open(self.lock_fn, "w")
		f.write(my_lock_signature())
		f.close()
		if(guardtime > 0):
			print("Waiting for Node-lock...")
			time.sleep(guardtime)
		return(self.owns_lock)
	
	def unlock(self):
		assert(self.owns_lock)
		os.remove(self.lock_fn)
	
	
	#---------------------------------------------------------------------------
	@property
	def children(self):
		return(self.pool.where("parent!=None and parent.name=='%s'"%self.name))
	
	@property
	def tpr_fn(self):
		return(self.dir+"/run.tpr")
	
	@property
	def trr_fn(self):
		return(self.dir+"/"+self.name+".trr")
	
	@property
	def mdp_fn(self):
		return(self.dir+"/"+self.name+".mdp")
		
	@property
	def pdb_fn(self):
		return(self.dir+"/"+self.name+"_conf.pdb")
	
	@property
	def top_fn(self):
		return(self.dir+"/"+self.name+".top")

	@property
	def convergence_log_fn(self):
		return(self.dir+"/"+self.name+"_convergence.log")

	@property
	def reweighting_log_fn(self):
		return(self.dir+"/"+self.name+"_reweighting.log")

	@property
	def mdrun_log_fn(self):
		return(self.dir+"/md.log")

	@property
	def has_convergence_log(self):
		return path.exists(self.convergence_log_fn)

	@property
	def has_reweighting_log(self):
		return path.exists(self.reweighting_log_fn)

	@property
	def has_mdrun_log(self):
		return path.exists(self.mdrun_log_fn)

	@property
	def has_trajectory(self):
		return path.exists(self.trr_fn)

	@property
	def has_restraints(self):
		return(hasattr(self, "restraints") and len(self.restraints)>0)

	@property
	def has_internals(self):
		return(hasattr(self, "internals"))
	
	@property
	def trajectory(self):
		try:
			return(self.read_trajectory())
		except AttributeError:
			traceback.print_exc()
			raise(Exception("Could not load trajectory"))
		
	
	def read_trajectory(self):
		if(not path.exists(self.trr_fn)):
			raise(Exception("%s not found."%self.trr_fn))
		
		if(self.__dict__.has_key("_trajectory_cache") and self.__dict__["_trajectory_cache_time"] >= path.getmtime(self.trr_fn)):
			#print "Using trajectory cache."
			return(self._trajectory_cache)
		
		# using print for newline, so that converter warnings are more readable
		#sys.stdout.write("Loading trr-file: %s... "%self.trr_fn)
		#sys.stdout.flush()
		print("Loading trr-file: %s... "%self.trr_fn)
		frames_int = self.pool.converter.read_trajectory(self.trr_fn)
		print("done.")
								
		if(self.has_internals and self.has_restraints):
			phi_values = get_phi(frames_int, self)
			penalty_potential = np.zeros(frames_int.n_frames)
			for (r, c) in zip(self.restraints, self.pool.converter):
				penalty_potential += r.energy(frames_int[:,c])				

			beta = self.pool.thermo_beta
			frameweights = phi_values / np.exp(-beta * penalty_potential)
		
		else:
			phi_values = np.zeros(frames_int.n_frames)
			penalty_potential = np.zeros(frames_int.n_frames)
			frameweights = np.ones(frames_int.n_frames)
		
		trajectory = InternalArray(frames_int.converter, frames_int.array, frameweights)
		self.__dict__["_phi_values_cache"] = phi_values
		self.__dict__["_penalty_potential_cache"] = penalty_potential
		self.__dict__["_trajectory_cache"] = trajectory
		self.__dict__["_trajectory_cache_time"] = path.getmtime(self.trr_fn)
		return(self._trajectory_cache)
	
	@property
	def penalty_potential(self):
		self.read_trajectory()
		return(self._penalty_potential_cache)
	
	@property
	def phi_values(self):
		self.read_trajectory()
		return(self._phi_values_cache)
	
	@property
	def frameweights(self):
		return(self.trajectory.frameweights)
		
	
	#---------------------------------------------------------------------------	
	# some conjugate state information
	@property
	def isa_partition(self):
		"""Indicates that this node belongs to the partioning of the internal coordinate space."""
		return(
			(self.has_restraints and self.state != 'refined') 
			or self.state=='creating-a-partition' ) # used by zgf_create_node.calc_theta()

	@property
	def isa_transition(self):
		"""Indicates that this node is a transition node."""
		return not(self.has_restraints or self == self.pool.root) 
	
	@property
	def is_sampled(self):
		"""Indicates that this node is finished with sampling""" 
		return self.state in ("converged", "not-converged", "refined", "ready")
	
#===============================================================================
#EOF
