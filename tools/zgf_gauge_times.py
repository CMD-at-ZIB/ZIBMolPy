#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ZIBMolPy.pool import Pool


def is_applicable():
	return(True)
	
	
#===============================================================================
def main():
	pool = Pool()
	for n in pool.where("isa_partition"):
		for cn in n.children.where("is_sampled"):
			print cn.trajectory
		
#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
