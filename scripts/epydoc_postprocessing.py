#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
from subprocess import Popen
from optparse import OptionParser
from os import path
import shutil
from glob import glob



#===============================================================================
def main():
#	usage = 'Usage: %prog [options] <action>\n<action> can be "install" or "uninstall"'
	new_code = r"""	
	<script type="text/x-mathjax-config">
    MathJax.Hub.Config({
      tex2jax: {
        inlineMath: [['$','$'], ['\\(','\\)']],
        displayMath: [['$$', '$$'], ["\\[", "\\]"]]
      }
    });
    </script>
    <script type="text/javascript" src="http://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-AMS-MML_HTMLorMML"></script>
	</head>
	"""
	
	html_files = glob("apidocs/*.html")
	assert(len(html_files) > 100) #there should be alot
	
	for fn in html_files:
		f = open(fn, "r")
		content = f.read()
		f.close()
		if("MathJax" in content): continue
		new_content = content.replace(r"</head>", new_code)
		f = open(fn, "w")
		f.write(new_content)
		f.close()
	
	print("Successfully injected MathJax in %i html files."%len(html_files))
	

#===============================================================================	
	
	
if(__name__ == "__main__"):
	main()
	
#EOF