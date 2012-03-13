#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the first step of ZIBgridfree.}

	This tool will, based on a presampling trajectory, process your input in order to generate an (yet empty) pool of ZIBgridfree sampling nodes.
	In the directory where zgf_create_pool is run, two new folders will be created, nodes/ and analysis/, along with a file called pool-desc.txt that contains the current state of your node pool. The folder nodes/ will contain a single folder node0000, which represents the root node. The root node corresponds to the presampling. All following nodes will originate from the root node.

	B{The next step is L{zgf_create_nodes}.}

How it works
============
	At the command line, type::
		$ zgf_create_nodes [options]

Requirements
============
	- molecule in pdb-format
	- presampling trajectory in trr format
	- U{mdp file<https://wiki.kobv.de/confluence/display/AGCMD/Example+mdp-file+for+Gromacs+with+ZIBgridfree>} for grompp
	- Gromacs topology for the molecule, and all included files
	- index file including group 'MOI' (molecule of interest)
	- U{internal coordinates <http://www.zib.de/cmd-debian/ZIBMolPy/apidocs/ZIBMolPy.internals-module.html>} definition

	MOI will probably be everything except the solvent, or at least every molecule that is involved in your internal coordinates. You have to make sure that it is specified in the index file. Furthermore, MOI has to be among the energy groups ('energygrps') in the U{mdp file<https://wiki.kobv.de/confluence/display/AGCMD/Example+mdp-file+for+Gromacs+with+ZIBgridfree>}.

	The mdp-file has to require the following lines::
		; Dihedral restraints
		dihre               =  yes
		dihre_fc            =  1
		; Distance restraints
		disre               =  simple
		disre_fc            =  1

	If the above lines are not present, they will be added and a fixed version of your mdp file will be written. Furthermore, the value for 'nstxout' has to be equal to the value of 'nstenergy'.

	An example mdp-file can be found U{here<https://wiki.kobv.de/confluence/display/AGCMD/Example+mdp-file+for+Gromacs+with+ZIBgridfree>}.


Gelman-Rubin parameters
=======================
  - B{GR threshold} defines a threshold for the Gelman-Rubin convergence check. The closer the value to 1.0, the more rigorous the convergence of the sampling is evaluated.
	
  - B{GR chains} defines the number of chains for the Gelman-Rubin convergence check. More chains mean more rigorous evaluation of the convergence, as the variance in each chain (intra-chain variance) is compared to the overall variance of the sampling (inter-chain variance).

"""

from ZIBMolPy.utils import check_call
from ZIBMolPy.pool import Pool
from ZIBMolPy import gromacs
from ZIBMolPy.node import Node
from ZIBMolPy.ui import userinput, Option, OptionsList
from ZIBMolPy.io.trr import TrrFile
from ZIBMolPy.internals import Converter, LinearCoordinate
import os
from os import path
from pprint import pformat
from math import sqrt
import sys
import re

options_desc = OptionsList([
		Option("c", "common-filename", "str", "Sets new, common default filenames for ALL options"),
		Option("s", "molecule", "file", extension="pdb", default="molecule.pdb"),
		Option("f", "presampling", "file", extension="trr", default="presampling.trr"),
		Option("g", "grompp", "file", extension="mdp", default="run.mdp"),
		Option("p", "topology", "file", extension="top", default="topol.top"),
		Option("n", "index", "file", extension="ndx", default="index.ndx"),
		
		# ZIBgridfree related options
		Option("I", "internals", "file", extension="int", default="internals.int"),
		Option("T", "temperature", "int", "temperature in Kelvin", default=300, min_value=0),
		Option("G", "gr-threshold", "float", "Gelman-Rubin threshold", default=1.1),
		Option("C", "gr-chains", "int", "Gelman-Rubin chains", default=5, min_value=1),
		Option("L", "balance-linears", "bool", "balance linear weights", default=False), #TODO optional for now, later we just do it without asking :P
	])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc


def is_applicable():
	pool = Pool()
	return( len(pool)==0 )


#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]

	if(options.common_filename):
		options.molecule = options.common_filename+".pdb"
		options.presampling = options.common_filename+".trr"
		options.internals = options.common_filename+".int"
		options.grompp = options.common_filename+".mdp"
		options.topology = options.common_filename+".top"
		options.index = options.common_filename+".ndx"

	print("Options:\n%s\n"%pformat(eval(str(options))))

	assert(path.exists(options.molecule))
	assert(path.exists(options.presampling))
	assert(path.exists(options.internals))
	assert(path.exists(options.grompp))
	assert(path.exists(options.topology))
		
	#TODO: what if there is no index-file? (make_ndx)
	assert(path.exists(options.index))
	assert('MOI' in gromacs.read_index_file(options.index)), "group MOI should be defined in index file"
 
	# checks e.g. if the mdp-file looks good
	mdp_options = gromacs.read_mdp_file(options.grompp)
	
	# options we cannot fix
	for ref_t in re.findall('[0-9]+', mdp_options["ref_t"]):
		assert(int(ref_t) == options.temperature), "temperature in mdp file does not match ZIBgridfree temperature"
		#TODO drop options.temperature and get temperature directly from mdp file... ask again if temperature is above 310K
		
	# options we can fix
	mdp_options_dirty = False #if set, a new mdp-file will be written
	required_mdp_options = {"dihre":"yes", "dihre_fc":"1", "disre":"simple", "disre_fc":"1"}
	for (k,v) in required_mdp_options.items():
		if(mdp_options.has_key(k)):
			assert(mdp_options[k] == v) # check, if we would overwrite something
		else:
			mdp_options[k] = v
			mdp_options_dirty = True
	
	if(mdp_options.has_key("energygrps")):
		assert('MOI' in [str(egrp) for egrp in re.findall('[\S]+', mdp_options["energygrps"])]), "group MOI should be among energygrps in mdp file"
	else:
		mdp_options["energygrps"] = "MOI"
		mdp_options_dirty = True
	
	a, b = mdp_options.has_key("nstxout"), mdp_options.has_key("nstenergy")
	if(a and not b):
		mdp_options["nstenergy"] = mdp_options["nstxout"]
		mdp_options_dirty = True
	elif(b and not a):
		mdp_options["nstxout"] = mdp_options["nstenergy"]
		mdp_options_dirty = True
	elif(b and a):
		assert(mdp_options["nstxout"] == mdp_options["nstenergy"]), "nstxout should equal nstenergy"
		
	if(int(mdp_options["nsteps"]) > 1e6):
		msg = "Number of MD-steps?"
		mdp_options["nsteps"] = str( userinput(msg, "int", default=int(mdp_options["nsteps"])) )
	
	# create a fixed mdp-file
	if(mdp_options_dirty):
		print("Creating copy of mdp-file and adding missing options.")
		out_fn = options.grompp.rsplit(".", 1)[0] + "_fixed.mdp"
		f = open(out_fn, "w") # append
		f.write("; Generated by zgf_create_pool\n")
		for i in mdp_options.items():
			f.write("%s = %s\n"%i)
		f.write("; EOF\n")
		f.close()
		options.grompp = out_fn
		
	
	# check if subsampling is reasonable
	if(os.path.getsize(options.presampling) > 100e6): # 100MB
		print("Presampling trajectory is large")
		trr = TrrFile(options.presampling)
		dt = trr.first_frame.next().t - trr.first_frame.t
		trr.close()
		print("Presampling timestep is %.2f ps"%dt)
		if(dt < 10): # picoseconds
			#TODO: maybe calculate subsampling factor individually, or ask? 
			msg = "Subsample presampling trajectory by a tenth?"
			if(userinput(msg, "bool")):
				out_fn = options.presampling.rsplit(".", 1)[0] + "_tenth.trr"
				cmd = ["trjconv", "-f", options.presampling, "-o", out_fn, "-skip", "10"]
				check_call(cmd)
				options.presampling = out_fn
	
			
	# balance linears
	if(options.balance_linears):
		print("Balance Linears")
		old_converter = Converter(options.internals)
		print("Loading presampling....")
		frames = old_converter.read_trajectory(options.presampling)
		new_coord_list = []
		for c in old_converter:
			if(not isinstance(c, LinearCoordinate)):
				new_coord_list.append(c)
				continue # we do not work on other Coordinate-Types
			#TODO: is this a good way to determine new_weight and new_offset??? 
			new_weight = c.weight / sqrt(2*frames.var().getcoord(c))
			new_offset = c.offset + frames.mean().getcoord(c)
			new_coord = LinearCoordinate(*c.atoms, label=c.label, weight=new_weight, offset=new_offset)
			new_coord_list.append(new_coord)
		new_converter = Converter(coord_list=new_coord_list)
	
		assert(old_converter.filename.endswith(".int"))
		options.internals = old_converter.filename[:-4] + "_balanced.int"
		print("Writing balanced Converter to: "+options.internals)
		f = open(options.internals, "w")
		f.write(new_converter.serialize())
		f.close()
		assert(len(Converter(options.internals)) == len(new_coord_list)) #try parsing
	
	# Finally: Create root-node and pool
	pool = Pool()
	if(len(pool) != 0):
		print("ERROR: A pool already exists here.")
		sys.exit(1)
	
	node0 = Node()
	node0.state = "refined"
	node0.save() # also creates the node directory ... needed for symlink
	os.symlink(os.path.relpath(options.presampling, node0.dir), node0.trr_fn)
	os.symlink(os.path.relpath(options.molecule, node0.dir), node0.pdb_fn)
	
	pool.int_fn = options.internals
	pool.mdp_fn = options.grompp
	pool.top_fn = options.topology
	pool.ndx_fn = options.index
	pool.temperature = options.temperature
	pool.gr_threshold = options.gr_threshold
	pool.gr_chains = options.gr_chains
	pool.alpha = None
	pool.root_name = node0.name
	pool.save()
		
	if(not path.exists("analysis")):
		os.mkdir("analysis")
	
	

#===============================================================================
	
	# if(options.balance_linears):
		# pool.reload_nodes()
		# span = []
		# for c in pool.converter.linears:
			# samples = pool.root.trajectory.getcoord(c.index)
			# span.append(max(samples)-min(samples))
# 
		# print span
		# weights = max(span)/span
		# print weights
		# #TODO nehmen wir zum ausbalancieren das attribut 'weight', oder führen wir ein neues attribut (nur für linears) ein?
		# #TODO zum testen verwende ich zunächst das reguläre weight-attribut als speicherort
		# #TODO 1. gefixtes int-file mit ausbalancierten linear-weights speichern
		# for (i, c) in enumerate(pool.converter.linears):
			# print c
			# print id(c)			
			# c.set_weight(weights[i])
		# for c in pool.converter:
			# print c
			# print id(c)
			# print c.str_filestyle()
			# print c.__dict__
		# #TODO 2. das gefixte int-file zum int-file des pools machen



	
# #==========================================================================
# def check_parameters(options):
	# """ checks e.g. if the mdp-file looks good """
	# mdp_file = gromacs.read_mdp_file(options.grompp)
	# 
	# assert(mdp_file["dihre"] == "yes")
	# assert(mdp_file["dihre_fc"] == "1")
	# assert(mdp_file["disre"] == "simple")
	# assert(mdp_file["disre_fc"] == "1")
	# assert(mdp_file["nstxout"] == mdp_file["nstenergy"])
	# for ref_t in re.findall('[0-9]+', mdp_file["ref_t"]):
		# assert( int(ref_t) == options.temperature )
	# assert(mdp_file["energygrps"])
	# assert('MOI' in [str(egrp) for egrp in re.findall('[\S]+', mdp_file["energygrps"])])
	# assert('MOI' in gromacs.read_index_file(options.index))
 

#==========================================================================
if(__name__=="__main__"):
	main()

#EOF

