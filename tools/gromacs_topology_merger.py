#! /usr/bin/env python
# -*- coding: utf-8 -*-


import tempfile
import subprocess
from subprocess import check_call
import os
from os import path
import sys
import shutil
from ZIBMolPy.ui import userchoice, userinput, Option, OptionsList
from ZIBMolPy.io.topology import Topology, preprocess

options_desc = OptionsList([
		Option("p", "input_topology", "file", extension="top", default="topol.top"),
		Option("o", "output_topology", "file", extension="top", default="merged_topol.top"),
	])
	
	
#===============================================================================
def main():
	(options, args) = options_desc.parse_args(sys.argv)
	assert(path.exists(options.input_topology))
	print("Preprocessing (only local includes): %s ..."%options.input_topology)
	rawdata = preprocess(options.input_topology, includedirs=[]) #only local includes
	
	print("\nParsing...")
	top = Topology(rawdata)
	print("The topology contains:")
	
	for m in top.molecules:
		print("  %d molecule(s) of the moleculetype '%s'"%(m.mols, m.name))
		
	#find candidates for molecules to merge 
	candidates = []
	for i in range(len(top.molecules)-1):
		#check this and the next molecule
		is_candidate = True
		for m in top.molecules[i:i+2]:
			is_candidate &= (m.mols==1)
			uses = [n for n in top.molecules if n.name == m.name]
			is_candidate &= (len(uses)==1)
		if(is_candidate):
			candidates.append(i)
	
	#pick a candidate
	if(len(candidates) == 0):
		print("Topology contains no mergable moleculetypes - abort.")
		sys.exit(1)
		
	elif(len(candidates) == 1):
		mt_index1 = candidates[0]
		print("Topology contains only one mergable pair of moleculetypes.")
		
	else:
		msg = "Only two consecutively molecultypes with mol=1 can be merged.\n"
		msg += "Choose index of first moleculetype.\n"
		for i in candidates:
			msg += "%d: %s\n"%(i, top.molecules[i].name)
		mt_index1 = userinput(msg, "int", condition="x in "+repr(candidates))
	
	#print choosen moleculetypes
	mt_name1 = top.molecules[mt_index1].name
	mt_name2 = top.molecules[mt_index1+1].name
	print("Merging moleculetype '%s' with '%s'."%(mt_name1, mt_name2))
	merge_moleculetypes(top, mt_name1, mt_name2)

	print("")
	print("The merged topology contains:")
	for m in top.molecules:
		print("  %d molecule(s) of the moleculetype '%s'"%(m.mols, m.name))
	
	
	top_out_fn =  options.output_topology
	print("Writting merged topology to "+top_out_fn)
	f = open(top_out_fn, "w")
	f.write(top.write())
	f.close()
	print("DONE")

#===============================================================================
def merge_moleculetypes(top, mt_name1, mt_name2):
	#assert that moleculetypes are used exactely once and consecutively 
	found_m1 = [m for m in top.molecules if m.name == mt_name1]
	found_m2 = [m for m in top.molecules if m.name == mt_name2]
	assert(len(found_m1) == 1) # mt used only once?
	assert(len(found_m2) == 1) # mt used only once?
	m1, m2 = found_m1[0], found_m2[0] 
	assert(top.molecules.index(m1)+1 == top.molecules.index(m2))
	
	# find moleculetype objects
	found_mt1 = [mt for mt in top.moleculetypes if mt.name == mt_name1]
	found_mt2 = [mt for mt in top.moleculetypes if mt.name == mt_name2]
	assert(len(found_mt1) == 1) #is mt-name unique?
	assert(len(found_mt2) == 1) #is mt-name unique?
	mt1, mt2 = found_mt1[0], found_mt2[0]
	
	assert(mt1.nrexcl == mt2.nrexcl)
	# gromacs-manual:
	# nrexc=3 stands for excluding non-bonded interactions between
	# atoms that are no further than 3 bonds away.

	#offsets for continuous numbering
	#offset = len(mt1.atoms) # offset for the atom-numbers
	offset_id   = max([a.id for a in mt1.atoms])    +1 -min([a.id for a in mt2.atoms])
	offset_cgnr = max([a.cg_nr for a in mt1.atoms]) +1 -min([a.cg_nr for a in mt2.atoms])
	offset_resnr= max([a.res_nr for a in mt1.atoms]) +1 -min([a.res_nr for a in mt2.atoms])
		
	
	for a in mt2.atoms:
		a.id += offset_id
		a.cg_nr += offset_cgnr
		a.res_nr += offset_resnr
		mt1.atoms.append(a)
	
	for b in mt2.bonds:
		b.ai += offset_id
		b.aj += offset_id
		mt1.bonds.append(b)
	
	for p in mt2.pairs:
		p.ai += offset_id
		p.aj += offset_id
		mt1.pairs.append(p)
	
	for a in mt2.angles:
		a.ai += offset_id
		a.aj += offset_id
		a.ak += offset_id
		mt1.angles.append(a)
	
	for d in mt2.dihedrals:
		d.ai += offset_id
		d.aj += offset_id
		d.ak += offset_id
		d.al += offset_id
		mt1.dihedrals.append(d)
	
	for pr in mt2.position_restraints:
		pr.ai += offset_id
		mt1.position_restraints.append(pr)
	
	
	mt1.name += "_"+mt2.name
	m1.name = mt1.name
	top.molecules.remove(m2)
	top.moleculetypes.remove(mt2)
	

#===============================================================================
if(__name__=="__main__"): 
	main()
#EOF
