#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the third step of ZIBgridfree.}

	After a set of initial nodes has been created by zgf_create_nodes, this tool will, for each node, setup all the files that are necessary for Gromacs to run the sampling. This includes writing the initial geometry to each node directory, and creating a per-node topology file that contains the restraint setup that is used to fit the node's phi function.

	B{The next step is L{zgf_grompp}.}

How it works
============
	At the command line, type::
		$ zgf_setup_nodes

"""

from ZIBMolPy.restraint import DihedralRestraint, DistanceRestraint
from ZIBMolPy.pool import Pool
import ZIBMolPy.topology as topology
from ZIBMolPy.ui import OptionsList
from ZIBMolPy.io.trr import TrrFile

import sys
import os
from tempfile import mktemp
from subprocess import Popen, PIPE
from math import degrees
import numpy as np
import shutil

options_desc = OptionsList()

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc


def is_applicable():
	pool = Pool()
	return(len(pool.where("state == 'created'")) > 0)

	
#===============================================================================
def main():
	
	pool = Pool()
	needy_nodes = pool.where("state == 'created'")
	assert(len(needy_nodes) == len(needy_nodes.multilock())) # make sure we lock ALL nodes
	
	extract_frames(pool)
	generate_topology(pool)
	
	for n in needy_nodes:
		n.state = "grompp-able"
		n.save()
		n.unlock()
	
#===============================================================================
def extract_frames(pool):
	needy_nodes = pool.where("state == 'created'")
	
	# we want to scan through a parent-trr only once - saves time
	parents = set([n.parent for n in needy_nodes])
	for p in parents:
		childs = [n for n in needy_nodes if n.parent == p]
		childs.sort(key=lambda x: x.parent_frame_num)
		trr_in = TrrFile(p.trr_fn)
		
		frame = trr_in.first_frame
		for n in childs:
			for dummy in range(n.parent_frame_num - frame.number):
				frame = frame.next()
			assert(frame.number == n.parent_frame_num)
			trr_tmp_fn = mktemp(suffix='.trr')
			trr_tmp = open(trr_tmp_fn, "wb")
			trr_tmp.write(frame.raw_data)
			trr_tmp.close()
			cmd = ["trjconv", "-f", trr_tmp_fn, "-o", n.pdb_fn, "-s", n.parent.pdb_fn] 
			p = Popen(cmd, stdin=PIPE)
			p.communicate(input="System\n")
			assert(p.wait() == 0)
			os.remove(trr_tmp_fn)
		trr_in.close()
	
	
	#Check if the right frames where extracted
	# In principle PDB coordinates should have a precision of 1e-4 nm
	# beause they are given in Angström with three decimal places.
	
	for n in needy_nodes:
		a = pool.converter.read_pdb(n.pdb_fn)
		d = np.max(np.abs(n.internals.array - a.array))
		print n.name+": pdb vs internals deviation: %.2e"%np.max(np.abs(n.internals.array - a.array))
		assert(1e-2 > d)
		
#===============================================================================
def generate_topology(pool):
	for n in pool.where("state == 'created'"):
		
		if(not n.has_restraints):
			shutil.copyfile(pool.top_fn, n.top_fn)
			continue
		
		# load unmodified topology
		top = topology.Topology(pool.top_fn)
		
		#k = node.alpha / get_beta(node.temperature) # in kJ/(mol rad^2)
		
		# Gromacs topologies consist of molecules, where each molecule belongs to a moleculetype.
		# Atoms, bonds, dihedrals belong to a moleculetype.
		# Atomnumbers are counted in each moleculetype seperately, starting with 1 (internals start with 0)
		#disres_idx = 0
		
		assert(len(pool.converter) == len(n.restraints))
		
		for (c, r) in zip(pool.converter, n.restraints):
			assert(c.atoms == r.atoms) # information is stored redundantly :-(
			
			# find Molecule of Interest
			moi = [top.atomnum2molnum(a+1) for a in r.atoms]
			if(not len(set(moi)) == 1):
				raise(Exception("Found restraint that spans more than one molecule. Merge moleculetypes in topology."))
			
			rel_atoms = [top.abs2rel_atomnum(a+1) for a in r.atoms]
			moltype_of_interest = top.molnum2moltype(moi[0])
			if isinstance(r, DihedralRestraint):
				(phi0, dphi, k) = r.params
				t = tuple( rel_atoms + [degrees(phi0), degrees(dphi), k] )
				newline = "%d  %d  %d  %d  1  1  %.10f  %.10f  %.10f  2; ZIBgridfree\n" % t
				moltype_of_interest.add2section("dihedral_restraints", newline)
			
			elif isinstance(r, DistanceRestraint):
				(r0, r1, r2, k) = r.params
				
				r0 = r0/c.weight + c.offset #TODO:really??? 
				r1 = r1/c.weight + c.offset #TODO:really???
				r2 = r2/c.weight + c.offset #TODO:really???
				k  = k/pow(c.weight,2)    #TODO:really???
				
				#t = tuple( rel_atoms + [disres_idx] + [r0, r1, r2, k] )
				#newline = "%d  %d  1  %d  1  %.10f  %.10f  %.10f  %.10f; ZIBgridfree\n" % t
				#moltype_of_interest.add2section("distance_restraints", newline)
				# Using bond type 10 instead of "true" distance restraints because
				# - it will keep the molecule together when resolving PBC
				# - distance restraints do not write energies to edr when DD is on
				t = tuple( rel_atoms + [r0, r1, r2, k] )
				newline = "%d  %d  10  %.10f  %.10f  %.10f  %.10f; ZIBgridfree\n" % t
				moltype_of_interest.add2section("bonds", newline)
				#disres_idx += 1
				
			else:
				raise(Exception("Unkown Restraint-Type"))
			
		print("Writing: %s"%n.top_fn)
		top.write(n.top_fn)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
