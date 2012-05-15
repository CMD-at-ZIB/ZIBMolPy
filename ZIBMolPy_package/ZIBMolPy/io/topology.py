# -*- coding: utf-8 -*-

import re
import os
import sys
from os import path
import traceback
#TODO:
# support #else
# support #define
# support constrainttypes

GMXLIB = ["/usr/local/gromacs/share/gromacs/top/","/usr/share/gromacs/top/"]
if("GMXLIB" in os.environ):
	GMXLIB = os.environ["GMXLIB"].split(":")

#===============================================================================
class LineEntry(object):
	_fieldtypes = ()
	_fieldnames = ()
	
	def __init__(self, lineno, line, ifdef_stack):
		self.lineno = lineno
		self.ifdef_stack = ifdef_stack
				
		if(not hasattr(self, "_min_values")):
			self._min_values = len(self._fieldnames) 
		
		values = line.split()
		assert(len(values) >= self._min_values)
		for t, k in zip(self._fieldtypes, self._fieldnames):
			self.__dict__[k] = None
			if(len(values)>0):
				self.__dict__[k] = t(values.pop(0))
		self._rest = values
		
	
	def asline(self):
		values = [ self.__dict__[k] for k in self._fieldnames ]
		parts = [ str(v) for v in values if v!=None ]
		parts += self._rest
		return("  ".join(parts))
		
#===============================================================================
# Copied from gromacs-4.5.3/src/kernel/toppush.c , row 214
#
# Comments on optional fields in the atomtypes section:
# 
# The force field format is getting a bit old. For OPLS-AA we needed
# to add a special bonded atomtype, and for Gerrit Groenhofs QM/MM stuff
# we also needed the atomic numbers.
# To avoid making all old or user-generated force fields unusable we
# have introduced both these quantities as optional columns, and do some
# acrobatics to check whether they are present or not.
# This will all look much nicer when we switch to XML... sigh.
# 
# Field 0 (mandatory) is the nonbonded type name. (string)
# Field 1 (optional)  is the bonded type (string)
# Field 2 (optional)  is the atomic number (int)
# Field 3 (mandatory) is the mass (numerical)
# Field 4 (mandatory) is the charge (numerical)
# Field 5 (mandatory) is the particle type (single character)
# This is followed by a number of nonbonded parameters.
# 
# The safest way to identify the format is the particle type field.
# 
# So, here is what we do:
# 
# A. Read in the first six fields as strings
# B. If field 3 (starting from 0) is a single char, we have neither
#    bonded_type or atomic numbers.
# C. If field 5 is a single char we have both.
# D. If field 4 is a single char we check field 1. If this begins with
#    an alphabetical character we have bonded types, otherwise atomic numbers.
#    atomtypes have more columns but e.g. the diala_quick has a strange 3rd column

class Atomtype(LineEntry):
	def __init__(self, lineno, line, ifdef_stack):
		self.bondtype = None
		self.at_number = None
		
		values = line.split()
		if(len(values[3])==1 and values[3].isalpha()):
			self._fieldtypes = (str, float, float, str)
			self._fieldnames = ("name", "mass", "charge", "ptype")
			
		elif(len(values[5])==1 and values[5].isalpha()):
			self._fieldtypes = (str, str, int, float, float, str)
			self._fieldnames = ("name", "bondtype", "at_number", "mass", "charge", "ptype")
			
		elif(len(values[4])==1 and values[4].isalpha()):
			if(values[1][0].isalpha()):
				self._fieldtypes = (str, str, float, float, str)
				self._fieldnames = ("name", "bondtype", "mass", "charge", "ptype")
			else:
				self._fieldtypes = (str, int, float, float, str)
				self._fieldnames = ("name", "at_number", "mass", "charge", "ptype")
		else:
			assert(False)
		
		LineEntry.__init__(self, lineno, line, ifdef_stack)
			

#===============================================================================
class Bondtype(LineEntry):
	pass

class Default(LineEntry):
	pass
	
class Angletype(LineEntry):
	pass

#===============================================================================
class Dihedraltype(LineEntry):
	# Copied from gromacs-4.5.3/src/kernel/toppush.c, row 683
	#
	# This routine accepts dihedraltypes defined from either 2 or 4 atoms.
	#
	# We first check for 2 atoms with the 3th column being an integer 
	# defining the type. If this isn't the case, we try it with 4 atoms
	# and the 5th column defining the dihedral type.
	
	def __init__(self, lineno, line, ifdef_stack):
		values = line.split()
		if(values[4].isdigit()):
			self._fieldtypes = (str, str, str, str, int)
			self._fieldnames = ("ai", "aj", "ak", "al", "funct")
		elif(values[2].isdigit()):
			if(values[3] == '2'):  # improper - the two atomtypes are 1,4. Use wildcards for 2,3
				self._fieldtypes = (str, str, int)
				self._fieldnames = ("ai", "al", "funct")
				self.aj = "X" #wildcard
				self.ak = "X" #wildcard
			else: #proper - the two atomtypes are 2,3. Use wildcards for 1,4 */
				self._fieldtypes = (str, str, int)
				self._fieldnames = ("aj", "ak", "funct")
				self.ai = "X" #wildcard
				self.al = "X" #wildcard
		else:
			assert(False)
		LineEntry.__init__(self, lineno, line, ifdef_stack)
	
#===============================================================================	
class Atom(LineEntry):
	_fieldtypes = (int ,  str       , int     , str       , str   , int    , float   ,  float)
	_fieldnames = ("id", "atomtype", "res_nr", "res_name", "name", "cg_nr", "charge", "mass")
	_min_values = 2 #TODO: check gromacs code
	
class Bond(LineEntry):
	_fieldtypes = (int, int)
	_fieldnames = ("ai", "aj")

class Pair(LineEntry):
	_fieldtypes = (int, int)
	_fieldnames = ("ai", "aj")

class Angle(LineEntry):
	_fieldtypes = (int, int, int)
	_fieldnames = ("ai", "aj", "ak")

class Dihedral(LineEntry):
	_fieldtypes = (int , int , int , int , int)
	_fieldnames = ("ai", "aj", "ak", "al", "funct")
	_min_values = 4
	
class PositionRestraint(LineEntry):
	_fieldtypes = (int,)
	_fieldnames = ("ai",)
	
class Molecule(LineEntry):
	_fieldtypes = (str   , int   )
	_fieldnames = ("name", "mols")

#===============================================================================
class Section(list):
	def __init__(self, name):
		list.__init__(self)
		self.name = name

	def write(self):
		if(len(self) == 0):
			return("")
		output = "[ "+self.name+" ]\n"
		curr_ifdef_stack = []
		for e in self:
			if("\n".join(e.ifdef_stack) != "\n".join(curr_ifdef_stack)):
				output += "#endif\n" * len(curr_ifdef_stack)
				output += "".join([s+"\n" for s in e.ifdef_stack])
				curr_ifdef_stack = e.ifdef_stack
			output += e.asline() +"\n"
		output += "#endif\n" * len(curr_ifdef_stack) #close left open blocks
		return(output+"\n")
			
#===============================================================================
class Moleculetype(object):
	def __init__(self, lineno, line, ifdef_stack):
		self.lineno = lineno
		self.ifdef_stack = ifdef_stack
		self.name = line.split()[0]
		self.nrexcl = line.split()[1]
		self.atoms = Section("atoms")
		self.bonds = Section("bonds")
		self.pairs = Section("pairs")
		self.angles = Section("angles")
		self.dihedrals = Section("dihedrals")
		self.position_restraints = Section("position_restraints")

	def write(self):
		output = "[ moleculetype ]\n"
		output += "%s  %s\n\n"%(self.name, self.nrexcl)
		output += self.atoms.write()
		output += self.pairs.write()
		output += self.bonds.write()
		output += self.angles.write()
		output += self.dihedrals.write()
		output += self.position_restraints.write()
		return(output)
	
#===============================================================================
class Topology(object):
	def write(self):
		#not implementd, yet
		assert(len(self.defaults) == 0)
		
		output = ""
		output += "".join([s+"\n" for s in self.early_includes])
		output += self.atomtypes.write()
		output += self.bondtypes.write()
		output += self.angletypes.write()
		output += self.dihedraltypes.write()
		for mt in self.moleculetypes:
			output += mt.write()
		
		output += "".join([s+"\n" for s in self.late_includes])	
		output += "[ system ]\n"
		output += "%s\n\n"%self.system
		output += self.molecules.write()
		
		return(output)
	
	#---------------------------------------------------------------------------	
	def __init__(self, rawdata):
		self.defaults = []
		self.atomtypes = Section("atomtypes")
		self.bondtypes = Section("bondtypes")
		self.angletypes = Section("angletypes")
		self.dihedraltypes = Section("dihedraltypes")
		self.moleculetypes = []
		self.molecules = Section("molecules")
		self.system = ""
		self.early_includes = []
		self.late_includes = []
		
					
		curr_section = None # this is the currently open section
		ifdef_stack = [] # this is a stack of currently open ifdef/ifndef blocks
		rawlines = rawdata.split("\n")
		for (i, line) in enumerate(rawlines, start=1): 
			try:
				line = re.sub(";.*$", "", line)
				line = line.strip()
				if(len(line) == 0): # ignore empty lines 
					continue
				
				if(line.lower().startswith("#if")):
					ifdef_stack = ifdef_stack + [line] # creates a copy of ifdef_stack
					continue
					
				if(line.lower().startswith("#endif")):
					assert(len(ifdef_stack) > 0) # endif needs prior opened if-block
					ifdef_stack = ifdef_stack[:-1] # creates a copy of ifdef_stack
					continue
				
				if(line.lower().startswith("#include")):
					if(len(self.atomtypes) == 0):
						self.early_includes += [line]
					else:
						self.late_includes += [line]
					continue
					
				if(line.startswith("#")):
					print("Skiping "+line)
					continue
						
				#recognize section headers
				m = re.match("\s*\[\s*(\w*)\s*\]\s*", line)
				if(m != None):
					curr_section = m.group(1)
					continue
			
				if(curr_section == None):
					continue # we might ignore unkown section 
				#assert(curr_section != None) # there should be an open section by now
				
				if(curr_section == "defaults"):
					self.defaults.append(Default(i, line, ifdef_stack))
				elif(curr_section == "atomtypes"):
					self.atomtypes.append(Atomtype(i,line, ifdef_stack))
				elif(curr_section == "bondtypes"):
					self.bondtypes.append(Bondtype(i,line, ifdef_stack))
				elif(curr_section == "angletypes"):
					self.angletypes.append(Angletype(i,line, ifdef_stack))
				elif(curr_section == "dihedraltypes"):
					self.dihedraltypes.append(Dihedraltype(i,line, ifdef_stack))
				elif(curr_section == "moleculetype"):
					self.moleculetypes.append(Moleculetype(i,line, ifdef_stack))
					
				elif(curr_section == "atoms"):
					self.moleculetypes[-1].atoms.append(Atom(i,line, ifdef_stack))
				elif(curr_section == "bonds"):
					self.moleculetypes[-1].bonds.append(Bond(i,line, ifdef_stack))
				elif(curr_section == "pairs"):
					self.moleculetypes[-1].pairs.append(Pair(i,line, ifdef_stack))
				elif(curr_section == "angles"):
					self.moleculetypes[-1].angles.append(Angle(i,line, ifdef_stack))
				elif(curr_section == "dihedrals"):
					self.moleculetypes[-1].dihedrals.append(Dihedral(i,line, ifdef_stack))
				elif(curr_section == "position_restraints"):
					self.moleculetypes[-1].position_restraints.append(PositionRestraint(i, line, ifdef_stack))
				
				
				elif(curr_section == "system"):
					self.system = (self.system+"\n"+line).strip()
				elif(curr_section == "molecules"):
					self.molecules.append(Molecule(i,line, ifdef_stack))
				else:
					print("ignoring unkown section: "+curr_section)
					curr_section = None # skipt the following lines of this section
					
				# except Exception as e:
					# print "exception: ",e
					# print "In section %s in line %d"%(curr_section,i)
					# print line
				# #	print("Ignoring strange line:" +line)
				
			#except Exception as e:
			except:
				print('Latest line: "%s"'%line)
				# print "\n".join(rawlines[max(0, i-5): i-1])
				# print('Latest line: "%s"'%line)
				# print "\n".join(rawlines[max(0, i-5): min(len(rawlines)-1, i+5])
				traceback.print_exc()
				sys.exit()
			
		assert(len(ifdef_stack) == 0) # all if-blocks should be closed at the end		
		
#===============================================================================
# verworfene Alternativen:
# original "cpp" will immer ALLE includes auflösen :-(
# "grompp -pp" braucht viele weitere files um ohne fehler durch zulaufen
# Daher: selber machen
def preprocess(filename, includedirs=GMXLIB):
	#pylint: disable=W0102
	tmp = resolve_includes(filename, includedirs)
	output = resolve_defines(tmp)
	return(output)

#===============================================================================
def resolve_includes(filename, includedirs, filesloaded=set()):
	if(filename in filesloaded):
		raise(Exception("circular include"))
	filesloaded.add(filename)
	rawdata = open(filename).read()
	
	def loadfile(m):
		fn = m.group(1)
		for d in [path.dirname(filename)] + includedirs:
			absfn = path.join(d, fn)
			if(path.exists(absfn)):
				print("Including %s"%absfn)	
				return( resolve_includes(absfn, includedirs, filesloaded) )
		print("Could not include %s"%fn)
		return('\n#include "%s"\n'%fn)
	
	output = re.sub('[\n^]#include\s+"([^"]*)"(?=\s)', loadfile , rawdata) #resolve includes
	return(output)

#===============================================================================
def resolve_defines(input_data):
	defines = dict()
	output = ""
	for line in input_data.split("\n"):
		if(line.lower().startswith("#define ")):
			parts = line.split(None, 2) + [None] #None is for flag-like defines
			defines[ parts[1] ] = parts[2]
			continue
		
		for (k,v) in defines.items():
			if( v!=None ):
				line = line.replace(k, v)
		output += line+"\n"
	return(output)


#===============================================================================
#EOF
