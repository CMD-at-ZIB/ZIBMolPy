# -*- coding: utf-8 -*-

import re
from os import path


#===============================================================================
class Section(object):
	def __init__(self, name, content):
		self.name = name
		self.content = content
		
	def __repr__(self):
		return("<Section %s>"%self.name)

	def pure_content(self):  
		""" removes empty lines and those starting with # or ; """
		return(re.sub("(?m)^([;#].*|\s*)\n", "", self.content))
		
#===============================================================================
class Moleculetype(object):
	def __init__(self, top, section):
		self.top = top
		self.section = section
		self.num_atoms = 0

	def name(self):
		return(self.section.pure_content().split()[0])

	def __repr__(self):
		return("<Moleculetype %s>"%self.name())

	def add2section(self, sectionname, newcontent):
		i = self.top.sections.index(self.section)
		for s in self.top.sections[i+1:]:
			if(s.name == sectionname):
				s.content += newcontent
				return
			if(s.name == "moleculetype"):
				break
				
		#section not found - create a new one
		new_section = Section(sectionname, newcontent)
		self.top.sections.insert(i+2, new_section) #add after atoms-section
		#raise(Exception("Section with name: %s not found."%sectionname))
		
#===============================================================================
class Topology(object):
	def __init__(self, filename):
		self.moleculetypes = {}
		self.molecules = []		
		self.sections = []
		
	 	#TODO: run through cpp to resolve #include, #IFDEF etc
	 	#alternative: grompp -pp 
		rawdata = open(filename).read()
		def loadfile(m):
			fn = path.join(path.basename(filename), m.group(1))
			if(path.exists(fn)):
				return(open(fn).read())
			return('#include "%s"\n'%m.group(1))

		rawdata = re.sub('#include\s+"([^"]*)"\s+', loadfile , rawdata) #resolve includes

		parts = re.split("\[\s*(\w*)\s*\]", rawdata)
		self.header = parts.pop(0)
		assert(len(parts)%2 == 0) #expecting section-name / section-content pairs
		
		while(len(parts) > 0):
			s = Section(name=parts.pop(0), content=parts.pop(0))
			self.sections.append(s) 
		
		current_mt = None
		for s in self.sections:
			if(s.name == "moleculetype"):
				name = s.pure_content().split()[0]
				current_mt = Moleculetype(self, s)
				self.moleculetypes[name] = current_mt
			elif(s.name == "atoms"):
				current_mt.num_atoms += s.pure_content().count("\n")
			elif(s.name == "molecules"):
				self.molecules += [x.split() for x in s.pure_content().split("\n") if len(x.strip())>0]


	def write(self, filename):
		f = open(filename, "w")
		f.write(self.header)
		for s in self.sections:
			f.write("[ %s ]\n"%s.name)
			f.write(s.content+"\n")
		f.close()
	
	def atomnum2molnum(self, abs_atom_num):
		""" Converts abs. atom number to abs. molecule number """
		abs_mol_counter = 1
		abs_atom_counter = 1
		for (name, num) in self.molecules:
			for dummy in range(int(num)):
				abs_atom_counter += self.moleculetypes[name].num_atoms
				abs_mol_counter += 1
				if(abs_atom_num < abs_atom_counter):
					return(abs_mol_counter -1)
		raise(Exception("Absolute Atom Number too hight: %d"%abs_atom_num))


	def molnum2moltype(self, abs_mol_num):
		abs_mol_counter = 0
		for (name, num) in self.molecules:
			abs_mol_counter += int(num)
			if(abs_mol_num <= abs_mol_counter):
				return(self.moleculetypes[name])
		raise(Exception("Absolute Molecule Number too hight: %d"%abs_mol_num))

	def abs2rel_atomnum(self, abs_atom_num):
		#TODO: more testing
		for (name, num) in self.molecules:
			mol_size = self.moleculetypes[name].num_atoms
			if(abs_atom_num > mol_size * num):
				abs_atom_num -= mol_size * num
			elif(abs_atom_num == mol_size):
				return(mol_size)
			else:
				return(abs_atom_num % mol_size)

		raise(Exception("Absolute Atom Number too hight: %d"%abs_atom_num))

#	def atomnum2moltype(self, abs_atom_num):
#		molnum = self.atomnum2molnum(abs_atom_num)
#		return(self.molnum2moltype(molnum))

#===============================================================================
#EOF
