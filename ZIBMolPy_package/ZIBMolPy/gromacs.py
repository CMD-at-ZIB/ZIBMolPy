# -*- coding: utf-8 -*-

""" Convenience methods for closely gromacs related tasks. """ 


import re

#===============================================================================
def read_index_file(index_file):
	""" reads index file and returns dictionary with key = group name and val = array of ints """
	
	groups = {}
	pat = re.compile(r"^\[\s+(\S+)\s+\]")

	f = open(index_file, 'r')
	for line in f:
		temp = re.search(pat, line.lower()) # lower-case group names
		
		if temp:		
			hit = temp
			groups[hit.group(1)] = ""
		else:
			groups[hit.group(1)] += line

	for i in groups.keys():
		temp = groups[i].split()
		for j in range(len(temp)):
			temp[j] = int(temp[j])
		groups[i] = temp
				
	f.close()
	return(groups)


#===============================================================================
def read_mdp_file(mdp_filename):
	txt = open(mdp_filename).read()
	txt = re.sub(";.*\n", "\n", txt.lower()) # throw away comments and lower-case content
	mdp_dict = dict(re.findall("^\s*(\S+)\s*=\s*(\S.*)$", txt, re.MULTILINE))
	return(mdp_dict)


#===============================================================================
#EOF	
