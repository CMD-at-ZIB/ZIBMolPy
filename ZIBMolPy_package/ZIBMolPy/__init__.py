""" 
Graphical user interface:
=========================
	- L{zgf_browser} : Framework GUI for all essential ZIBgridfree tools

ZIBgridfree essential pipeline:
===============================
	1. L{zgf_create_pool}
	2. L{zgf_create_nodes}
	3. L{zgf_setup_nodes}
	4. L{zgf_grompp}
	5. L{zgf_mdrun} or L{zgf_submit_job_HLRN}
	6. L{zgf_refine}
	7. L{zgf_reweight}
	8. L{zgf_analyze}

Convenience:
============
	- L{zgf_extract_conformations}
	- L{zgf_cleanup}
	- L{zgf_remove_nodes}
	- L{zgf_solvate_nodes}
	- L{zgf_genion}
	- L{zgf_recover_failed}

Testing:
========
	- L{zgf_test}


@group base: internals, pool, node, restraint, phi
@group helpers: algorithms, constants, gromacs, ui, utils, topology, io
@group browser: plots
"""
#EOF
