#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ZIBMolPy.utils import check_call

from xml.dom import minidom
import tempfile
import sys
import os
import re

#===============================================================================
def main():
	if(len(sys.argv) != 2):
		print("zgf_test <test-desc.xml>")
		exit(1)
	
	desc_fn = sys.argv[1]
	dom = minidom.parse(desc_fn)
	for n in dom.firstChild.childNodes:
		if(n.nodeType != 1):
			continue
		ndata = n.firstChild.data.strip()
		try:
			if(n.nodeName == "run"):
				current_cmd = ndata
				output = check_output(current_cmd)
			elif(n.nodeName == "match-stdout"):
				i = match(ndata, output)
				output = output[i:]
			else:
				raise(Exception("Unkown tag in xml-file: "+n.nodeName))
		
		except Exception, err:
			#traceback.print_exc()
			print "\n"+str(err)
			print("FOUND ERRORS IN: %s\n\n"%current_cmd)
			sys.exit(1)
			
	print("\n\n        TEST FINISHED WITHOUT ERRORS :-)")

#===============================================================================
def match(pattern_txt, output):
	""" converts the pattern_txt into a regular expression, which allows fuzzy-matching of floats """
	
	#http://stackoverflow.com/questions/638565/parsing-scientific-notation-sensibly
	float_re = r"([+\-]?(?:0|[1-9]\d*)(?:\.\d*)?(?:[eE][+\-]?\d+)?)\s*"
			
	ref_values = [float(x) for x in re.findall(float_re, pattern_txt)]
	pattern_re = re.sub(r"([\[\]()])", r"\\\1", pattern_txt) #escape special chars
	pattern_re =  re.sub(float_re, float_re, pattern_re) #turn floats into float_re
		
	m = re.search(pattern_re, output)
	if(not m):
		print("\nERROR: Could not find:\n%s\n"%pattern_re)
		raise(Exception("Pattern not found"))

	for r, v in zip(ref_values, m.groups()):
		max_delta = 0.01*max(abs(r), 0.01) #maybe r==0
		delta = abs(r - float(v))
		if(delta > max_delta):
			print("\nERROR: delta=%f is too high (>%f)."%(delta, max_delta))
			print("Expecting %f from:\n%s\n"%(r,pattern_txt))
			print("Found %s from:\n%s\n"%(v, m.group(0)))
			raise(Exception("Numbers do not match."))
				
	return(m.end()) #return end-index of matched substring
	
#===============================================================================
def check_output(cmd):
	print("\n" + '#'*(len(cmd)+13) + "\n# Running: " + cmd + " #\n" + '#'*(len(cmd)+13) +"\n")
	tmp_fn = tempfile.mktemp()
	# The pipe to tee hides the exit-status of cmd, but its save in $PIPESTATUS
	cmd += " | tee "+tmp_fn+" ; exit $PIPESTATUS"
	
	# Debian's default shell is Dash, which does not support $PIPESTATUS
	check_call(cmd, shell=True, executable="/bin/bash")
	output = open(tmp_fn).read()
	os.remove(tmp_fn)
	return(output)

#===============================================================================
if(__name__ == "__main__"):
	main()

#EOF
