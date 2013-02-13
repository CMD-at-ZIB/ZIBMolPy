#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============

This optional tool will put unsolvated node configurations (e.g. obtained by high-temperature presampling in vacuum) into equally sized solvent boxes.

All solvent boxes will be filled with the same number of solvent molecules. The node topologies will be updated accordingly. For known solvent models, the necessary force field include statements will be added to the node topologies. If the specified box size is too small to fit in the specified linear coordinates (if any), the box size will be increased automatically.

B{If required, ions can be added by using L{zgf_genion}. Otherwise, the next step is L{zgf_mdrun}, or L{zgf_submit_job_HLRN}, if you are working on HLRN.}

How it works
============
	At the command line, type::
		$ zgf_solvate_nodes

"""

from ZIBMolPy.pool import Pool
from ZIBMolPy.internals import LinearCoordinate
from ZIBMolPy.ui import userinput, OptionsList, Option

import zgf_grompp

import sys
import re
import os
from subprocess import Popen, PIPE
import numpy as np
import shutil
from tempfile import mktemp


#===============================================================================
options_desc = OptionsList([
	Option("b", "bt", "choice", "Box type", choices=("dodecahedron", "octahedron", "triclinic", "cubic")),
	Option("x", "box-x", "float", "Box vector length (x)", default=3.0, min_value=0.0),
	Option("y", "box-y", "float", "Box vector length (y)", default=3.0, min_value=0.0),
	Option("z", "box-z", "float", "Box vector length (z)", default=3.0, min_value=0.0),
	Option("s", "solv-model", "choice", "Solvent model", choices=("tip3p", "tip4p", "tip4pew", "tip5p", "spc", "spce", "acetonitrile")),
	Option("g", "grompp", "file", extension="mdp", default="em.mdp"),
])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc

def is_applicable():
	pool = Pool()
	return(len(pool.where("state == 'grompp-able'")) > 0)

	
#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	
	pool = Pool()
	needy_nodes = pool.where("state == 'grompp-able'")
	assert(len(needy_nodes) == len(needy_nodes.multilock())) # make sure we lock ALL nodes

	if(options.solv_model == "tip3p"):
		solv_box = "spc216.gro"
		solv_fn = "tip3p.itp"
	elif(options.solv_model == "tip4p"):
		solv_box = "tip4p.gro"
		solv_fn = "tip4p.itp"
	elif(options.solv_model == "tip4pew"):
		solv_box = "tip4p.gro"
		solv_fn = "tip4pew.itp"
	elif(options.solv_model == "tip5"):
		solv_box = "tip5p.gro"
		solv_fn = "tip5p.itp"
	elif(options.solv_model == "spc"):
		solv_box = "spc216.gro"
		solv_fn = "spc.itp"
	elif(options.solv_model == "spce"):
		solv_box = "spc216.gro"
		solv_fn = "spce.itp"
	elif(options.solv_model == "acetonitrile"): # TODO one might change this one to "custom" and let user enter name of template box
		solv_box = "acetonitrile.pdb"
		msg = "Topology update for acetonitrile is not supported. Proceed?"
		if not(userinput(msg, "bool")):
			for n in needy_nodes:
				n.unlock()
			return("Quit by user.")
	
	# determine maximum length of linears, if any
	max_linear = query_linear_length(pool)

	# make box and fill with solvent
	genbox(pool, max_linear, options.bt, (options.box_x, options.box_y, options.box_z), solv_box)

	# update topology files (add solvent model and ions includes)
	if not(options.solv_model == "acetonitrile"):
		update_tops(pool, solv_fn)

	for n in needy_nodes:
		n.state = "em-grompp-able"
		zgf_grompp.call_grompp(n, mdp_file=options.grompp, final_state="em-mdrun-able") # re-grompp to get a tpr for energy minimization
		n.unlock()


#===============================================================================
def query_linear_length(pool):
	max_length = 0.0
	for n in pool.where("state == 'grompp-able'"):
		for c in pool.converter:
			if isinstance(c, LinearCoordinate):
				lin_length = c.scaled2real( n.internals.getcoord(c) )
				if(lin_length > max_length):
					max_length = lin_length
	return(max_length)


#===============================================================================
def genbox(pool, max_linear, boxtype, dims, solv_box, slack=1.0):
	
	# it has to hold that Gromacs box size >= 2*maximum distance restraint length
	new_dims = ()
	healthy_dim = np.round(max_linear, 3)*2+slack
	for dim in dims:
		if(dim < healthy_dim):
			new_dims = new_dims+(healthy_dim,)
		else:
			new_dims = new_dims+(dim,)
	
	if not(dims == new_dims):
		print "Box dimensions changed in order to make room for distance restraints:"
		print "(%.3f,%.3f,%.3f)"%new_dims

	n_solmols = []
	for n in pool.where("state == 'grompp-able'"):

		cmd = ["editconf", "-f", n.pdb_fn, "-o", n.pdb_fn, "-bt", boxtype, "-box"] + [str(dim) for dim in new_dims] 
		print("Calling: %s"%" ".join(cmd))
		p = Popen(cmd)
		retcode = p.wait()
		assert(retcode == 0) # editconf should never fail
		
		genbox_fn = mktemp(suffix=".pdb", dir=n.dir)

		# 1st genbox: finding out how many solvent molecules we can fit in
		cmd = ["genbox", "-cp", n.pdb_fn, "-o", genbox_fn, "-cs", solv_box] 
		print("Calling: %s"%" ".join(cmd))
		p = Popen(cmd, stdout=PIPE, stderr=PIPE)
		stderr = p.communicate()[1]
		assert(p.returncode == 0) # genbox should never fail
		foo = re.search("\nAdded \d+ molecules\n", stderr, re.DOTALL).group(0)
		n_solmols.append( int( re.findall("\d+", foo)[0] ) )

		os.remove(genbox_fn)

	max_solmols = min(n_solmols)

	print "Maximum number of SOL molecules per box is %d."%max_solmols
	
	for n in pool.where("state == 'grompp-able'"):

		# 2nd genbox: filling each box with an equal number of solvent molecules
		cmd = ["genbox", "-cp", n.pdb_fn, "-o", n.pdb_fn, "-cs", solv_box, "-maxsol", str(max_solmols), "-p", n.top_fn]
		print("Calling: %s"%" ".join(cmd))
		p = Popen(cmd)
		retcode = p.wait()
		assert(p.returncode == 0) # genbox should never fail
		

#===============================================================================
def update_tops(pool, solv_fn):

	rawdata = open(pool.top_fn).read()

	all_incs =  re.findall('#include\s+"([^"]*)"(?=\s)', rawdata)
	ff_inc = [inc for inc in all_incs if 'forcefield.itp' in inc ]
	assert(len(ff_inc) == 1)
	
	# find out name of force field
	ff_dir = ff_inc[0].rsplit("/", 1)[0]
	
	solv_fn = ff_dir+"/"+solv_fn
	ions_fn = ff_dir+"/ions.itp"

	inc_solv = False
	inc_ions = False
	if not ( solv_fn in all_incs ):
		inc_solv = True
		print "Will include %s into topologies ..."%solv_fn
	if not ( ions_fn in all_incs ):
		inc_ions = True
		print "Will include %s into topologies ..."%ions_fn

	# update topologies
	if(inc_solv or inc_ions):
		import fileinput

		toplist = [pool.top_fn] + [n.top_fn for n in pool.where("state == 'grompp-able'")]
		
		for top_fn in toplist:
			process = False
			for line in fileinput.input(top_fn, inplace=1):
				if line.startswith('#include "'+ff_inc[0]+'"'):
					process = True
				else:
					if process:
						if(inc_solv):
							print '#include "'+solv_fn+'"'
						if(inc_ions):
							print '#include "'+ions_fn+'"'
						process = False
				sys.stdout.write(line)


#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF

