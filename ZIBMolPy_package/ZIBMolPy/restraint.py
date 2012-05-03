# -*- coding: utf-8 -*-

import numpy as np
from numpy import pi

# Using the params as a list is more convenient for the fit method in zgf_setup_nodes
#===============================================================================
class Restraint(object):
	def __init__(self, atoms, params):
		assert(np.all(np.isfinite(params)))
		self.atoms = atoms
		self.params = params
		
	def energy(self, x):
		return( self.calc_energy(self.params, x) )

	#DEBUG_BEGINN
	def energy_rescaled(self, x, c):
		return( self.calc_energy_rescaled(self.params, x, c) )
	#DEBUG_ENDE
		
	def __repr__(self):
		param_str = ",".join([str(x) for x in (self.atoms,)+self.params])
		return(self.__class__.__name__+"("+param_str+")")

	@staticmethod
	def calc_energy(params, x):
		raise(NotImplementedError)
	
#===============================================================================
class DihedralRestraint(Restraint):
	def __init__(self, atoms, phi0, dphi, k):
		params = (phi0, dphi, k)
		Restraint.__init__(self, atoms, params)
		
	@staticmethod	
	def calc_energy(params, phi):
		(phi0, dphi, k) = params
		diffs = phi0 - phi
		m = np.mod(diffs + np.pi , 2*np.pi)
		dp = abs( m - np.pi ) 
		c = dp > dphi
		v = 0.5*k*np.square(dp - dphi)
		return(v*c)

	@staticmethod	
	def calc_energy_alternative(params, all_phi):
		""" slower but directly translated from gromacs-code """ 
		(phi0, dphi, kfac) = np.array(params, np.float32) 
				
		vtot = np.zeros(all_phi.size)
		for i, phi in enumerate(all_phi):
			#from gromacs-4.5.3/src/gmxlib/dihres.c line 112
			dp = phi-phi0  
			if (abs(dp) > dphi):
				# dp cannot be outside (-2*pi,2*pi)
				if (dp >= pi):
					dp -= 2*pi
				elif(dp < -pi):
					dp += 2*pi
					
				if (dp > dphi):
					ddp = dp-dphi
				elif(dp < -dphi):
					ddp = dp+dphi
				else:
					ddp = 0
	
				if (ddp != 0.0):
					vtot[i] = 0.5*kfac*ddp*ddp
					#ddphi = kfac*ddp;
		return(vtot)
	
	#DEBUG_BEGINN TODO dummy, to be removed after Ole-check
	def calc_energy_rescaled(self, params, phi, c):
		return( self.calc_energy(params, phi) )
	#DEBUG_ENDE

#===============================================================================
class DistanceRestraint(Restraint):
	def __init__(self, atoms, r0, r1, r2, k):
		params = (r0, r1, r2, k)
		Restraint.__init__(self, atoms, params)
		
	@staticmethod
	def calc_energy(params, r):
		(r0, r1, r2, k) = params
		v1 = 0.5*k*np.square(r - r0)
		v2 = 0.5*k*np.square(r - r1)
		v3 = 0.5*k*(r2-r1)*(2*r-r2-r1)
		c1 = (r < r0)
		c2 = np.logical_and(r1<=r, r<r2)
		c3 = (r2 <= r)
		return( v1*c1 + v2*c2 + v3*c3 )

	#DEBUG_BEGINN
	@staticmethod
	def calc_energy_rescaled(params, r, c):
		
		(r0, r1, r2, k) = params
	
		# rescaling parameters
		r0 = c.plot_scale(r0)
		r1 = c.plot_scale(r1)
		r2 = c.plot_scale(r2)
		k  = k/pow(c.weight,2)
		
		# rescaling timeseries
		r = c.plot_scale(r)	
	
		v1 = 0.5*k*np.square(r - r0)
		v2 = 0.5*k*np.square(r - r1)
		v3 = 0.5*k*(r2-r1)*(2*r-r2-r1)
		c1 = (r < r0)
		c2 = np.logical_and(r1<=r, r<r2)
		c3 = (r2 <= r)

		return( v1*c1 + v2*c2 + v3*c3 )
	#DEBUG_ENDE

#===============================================================================
#EOF	
