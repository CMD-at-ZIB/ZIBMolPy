#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
What it does
============
	B{This is the fifth step of ZIBgridfree.}

	This tool performs the task of L{zgf_mdrun} on HLRN. In addition to the inherited L{zgf_mdrun} options, you can pick several options for the HLRN job script, such as job queue, time limit, and e-mail notification. It is also possible to allocate a larger number of nodes and subdivide these into separate L{zgf_mdrun} processes. Alternatively, you can call this tool several times on the same node pool to submit multiple smaller jobs. For more information, please refer to the L{zgf_mdrun} documentation. 

	
	B{The next step is L{zgf_refine}, if you want to refine or extend nodes where convergence has not been achieved. Otherwise, you can proceed with L{zgf_reweight}.}

How it works
============
	At the command line, type::
		$ zgf_submit_job_HLRN [options]

"""

import subprocess
import re
import sys
import tempfile
import math
import os
import zgf_mdrun
from ZIBMolPy.pool import Pool
from ZIBMolPy.ui import Option, OptionsList


def load_queues():
	try:
		p = subprocess.Popen(['qstat','-q'], stdout=subprocess.PIPE)
		stdout = p.communicate()[0]
		assert(p.returncode == 0)
		foo = re.match(".*\nQueue\s[^\n]*\n[- ]*(\n.*)", stdout, re.DOTALL).group(1)
		return( re.findall("\n(\w+)\s", foo) )
	except:
		return([])


options_desc = OptionsList([
	Option("Q", "queue", "choice", "queue for scheduling", choices=["auto",]+sorted(load_queues())),
	Option("N", "nodes", "int", "number of computing cluster nodes", default=2, min_value=1),
	Option("P", "ppn", "int", "number of processors per node", default=8, min_value=1),
	Option("W", "walltime", "float", "job-walltime in hours", default=1.0, min_value=0.1),
	Option("M", "email", "str", "email-address for notifications"),
	Option("D", "dryrun", "bool", "Only generates job-file, but does not submit it", default=False),
	Option("S", "subdivide", "int", "number of parallel zgf_mdrun processes started within the job", min_value=1, default=1),
	Option("A", "account", "str", "account to be debited"),
])

sys.modules[__name__].__doc__ += options_desc.epytext() # for epydoc


# reuse some options from zgf_mdrun
FORWARDED_ZGF_MDRUN_OPTIONS = ("seq", "npme", "reprod", "pd", "convtest", "auto-refines", "multistart")
for x in FORWARDED_ZGF_MDRUN_OPTIONS:
	options_desc.append(zgf_mdrun.options_desc[x]) 

	
def is_applicable():
	pool = Pool()
	return(len(pool.where("state in ('em-mdrun-able', 'mdrun-able')")) > 0)


#===============================================================================
def main():
	options = options_desc.parse_args(sys.argv)[0]
	assert(options.nodes % options.subdivide == 0)	
	
	joblines = ["#!/bin/bash"]
	joblines += ["#PBS -N zgf_job", "#PBS -j oe",]
	if(options.email): 
		joblines += ["#PBS -m ea -M "+options.email]
	if(options.account): 
		joblines += ["#PBS -A "+options.account]
	wt_hours = math.floor(options.walltime)
	wt_minutes = (options.walltime - wt_hours) * 60 
	joblines += ["#PBS -l walltime=%0.2d:%0.2d:00"%(wt_hours, wt_minutes)]
	if(options.queue != "auto"):
		joblines += ["#PBS -q "+options.queue]
	joblines += ["#PBS -l nodes=%d:ppn=%d"%(options.nodes, options.ppn)]
	
	joblines += ["source ${MODULESHOME}/init/sh"]
	#for m in ("gromacs/gromacs-4.5.4-single", "zibmolpy"):
	for m in os.environ['LOADEDMODULES'].split(":"):
		joblines += ["module load "+m]
	
	# on some machines the local module has to be loaded 
	joblines += ['if ! python -c "import numpy" &>/dev/null; then']
	joblines += ['   module load local']
	joblines += ['fi']
	
	
	joblines += ["set -x"]
	joblines += ["hostname --fqdn"]
	joblines += ["export"]
	joblines += ["date"]
	joblines += ["cd $PBS_O_WORKDIR"]
	
	zgfmdrun_call = "zgf_mdrun --np=%d"%(options.nodes*options.ppn / options.subdivide)
	# forward options to zgf_mdrun
	for o in zgf_mdrun.options_desc:
		if(o.long_name in FORWARDED_ZGF_MDRUN_OPTIONS):
			zgfmdrun_call += " " + " ".join(o.forward_value(options))
			# TODO better: "-option=value" , meaning wrap each item in quotes 
			# ...the shell should remove them.
	
	for i in range(options.subdivide):
		joblines += [zgfmdrun_call + " &> zgf_mdrun.${PBS_JOBID}.%d.log &"%i]
	
	joblines += ["wait"]
	joblines += ["date"]
	
	content = "\n".join(joblines)
	content += "\n#EOF\n"
	
	print "Generated Jobfile:\n"+content
	sys.stdout.flush()
	
	fn = tempfile.mkstemp(prefix='tmp', suffix='.sh')[1]
	f = open(fn, "w")
	f.write(content)
	f.close()
	
	if(not options.dryrun):
		subprocess.check_call(["msub",fn])
	os.remove(fn)
	
#==========================================================================
if(__name__=="__main__"):
	main()
		
#EOF
