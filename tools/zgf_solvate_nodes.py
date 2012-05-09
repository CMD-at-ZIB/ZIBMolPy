#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
What it does
============

bla

How it works
============
	At the command line, type::
		$ zgf_solvate_nodes bla

"""


from ZIBMolPy.pool import Pool
from ZIBMolPy.internals import LinearCoordinate
from ZIBMolPy.ui import OptionsList, Option

import sys
import re
from subprocess import Popen, PIPE
import numpy as np
import shutil


#===============================================================================
options_desc = OptionsList([
	Option("b", "bt", "choice", "Box type", choices=("dodecahedron", "octahedron", "triclinic", "cubic")),
	Option("x", "box-x", "float", "Box vector length (x)", default=3.0, min_value=0.0),
	Option("y", "box-y", "float", "Box vector length (y)", default=3.0, min_value=0.0),
	Option("z", "box-z", "float", "Box vector length (z)", default=3.0, min_value=0.0),
	Option("s", "solv-model", "choice", "Solvent model", choices=("tip3p", "tip4p", "tip4pew", "tip5p", "spc", "spce")),
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
	
	# determine maximum length of linears, if any
	max_linear = query_linear_length(pool)

	# make box and fill with solvent
	genbox(pool, max_linear, options.bt, (options.box_x, options.box_y, options.box_z), solv_box)

	# update topology files
	update_tops(pool, solv_fn)

	# grompp?? ... maybe not, because this duplicates code... make zgf_grompp smarter
	#TODO ion support ... maybe use extra tool

	for n in needy_nodes:
		n.state = "m-grompp-able"
		n.save()
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
def genbox(pool, max_linear, boxtype, dims, solv_box, slack=0.1):
	
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

		editconf_pdb_fn = n.pdb_fn.rsplit(".", 1)[0] + "_editconf.pdb" #TODO if this works out, we can just overwrite n.pdb_fn

		cmd = ["editconf", "-f", n.pdb_fn, "-o", editconf_pdb_fn, "-bt", boxtype, "-box"] + [str(dim) for dim in new_dims] 
		print("Calling: %s"%" ".join(cmd))
		p = Popen(cmd)
		retcode = p.wait()
		assert(retcode == 0) # editconf should never fail

		genbox_pdb_fn = n.pdb_fn.rsplit(".", 1)[0] + "_genbox.pdb" #TODO couldn't I save the guy in /dev/null?

		cmd = ["genbox", "-cp", editconf_pdb_fn, "-o", genbox_pdb_fn, "-cs", solv_box] 
		print("Calling: %s"%" ".join(cmd))
		p = Popen(cmd, stdout=PIPE, stderr=PIPE)
		stderr = p.communicate()[1]
		assert(p.returncode == 0) # genbox should never fail
		foo = re.search("\nAdded \d+ molecules\n", stderr, re.DOTALL).group(0)
		n_solmols.append( int( re.findall("\d+", foo)[0] ) )

	max_solmols = min(n_solmols)

	print "Maximum number of SOL molecules per box is %d."%max_solmols
	
	for n in pool.where("state == 'grompp-able'"):

		editconf_pdb_fn = n.pdb_fn.rsplit(".", 1)[0] + "_editconf.pdb"

		cmd = ["genbox", "-cp", editconf_pdb_fn, "-o", n.pdb_fn, "-cs", solv_box, "-maxsol", str(max_solmols), "-p", n.top_fn]
		print("Calling: %s"%" ".join(cmd))
		p = Popen(cmd)
		retcode = p.wait()
		assert(p.returncode == 0)
		

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
