#!/usr/bin/python
# -*- coding: utf-8 -*-

import numpy as np
#from Scientific.Geometry import Vector
from warnings import warn

_str_in = lambda x: x.strip()
_float_out_83 = lambda x: "%8.3f"%x


#http://www.wwpdb.org/documentation/format32/sect9.html
PDB_FIELDS = [{'start':7, 'end':11, 'in_filter':int, 'name':'serial'},
	{'start':13, 'end':16, 'in_filter':_str_in, 'name':'name'},
    {'start':17, 'end':17, 'in_filter':_str_in, 'name':'altLoc','default':''},
	{'start':18, 'end':20, 'in_filter':_str_in, 'name':'resName'},
	{'start':22, 'end':22, 'in_filter':_str_in, 'name':'chainID'},
	{'start':23, 'end':26, 'in_filter':int, 'name':'resSeq'},
	{'start':27, 'end':27, 'in_filter':_str_in, 'name':'iCode','default':''},
	{'start':31, 'end':38, 'in_filter':float, 'name':'x','out_filter':_float_out_83}, #8.3
	{'start':39, 'end':46, 'in_filter':float, 'name':'y','out_filter':_float_out_83}, #8.3
	{'start':47, 'end':54, 'in_filter':float, 'name':'z','out_filter':_float_out_83}, #8.3
	{'start':55, 'end':60, 'in_filter':float, 'name':'occupancy','default':'1.00'}, #6.3
	{'start':61, 'end':66, 'in_filter':float, 'name':'tempFactor','default':'0.00'}, #6.3
	{'start':77, 'end':78, 'in_filter':_str_in, 'name':'element','default':''}, #6.3
	{'start':79, 'end':80, 'in_filter':_str_in, 'name':'charge','default':''}]

#===============================================================================
def format_atom(raw):
	line = "ATOM  "
	i = 7
	for field in PDB_FIELDS:
		if(raw.has_key(field['name'])):
			value = raw[field['name']]
		else:
			value = field['default']
			
		if(field.has_key('out_filter')):
			value = field['out_filter'](value)
		else:
			value = str(value)
		line += ' '*(field['start'] -i-1) #if there is space between fields
		i = field['end']
		line += value.rjust(field['end'] - field['start']+1)
	return(line)

#===============================================================================
def read_pdb(filename):
	f = open(filename)
	lines = f.readlines()
	f.close()

	s = Structure()
	for line in lines:
		
		if(not line.startswith('ATOM')): continue
		raw = dict()
		for f in PDB_FIELDS:
			v = line[f['start']-1:f['end']]
			raw[f['name']] = f['in_filter'](v)
		#print raw
		position = np.array([raw['x'],raw['y'],raw['z']])
		a = Atom(raw['name'], position )
		s.addAtom(raw['chainID'], raw['resName'], raw['resSeq'], a)
	return(s)

#===============================================================================
class Structure(object):
	def __init__(self):
		self.objects = []
		
	def addAtom(self, chainID, resName, resSeq, atom):
		for c in self.objects:
			if(c.chain_id == chainID):
				c.addAtom(resName, resSeq, atom)
				return
		#if chain not found:
		self.objects.append(Chain(chainID))
		self.objects[-1].addAtom(resName, resSeq, atom)
		
	def writeToFile(self, filename):
		output = "HEADER\n"
		counters = {'atom_num':0} 
		for o in self.objects:
			output += o.to_pdb(counters)
		output += "END\n"
		f = open(filename, "w")
		f.write(output)
		f.close()
		
	def get_atom_number(self, given_atom):
		""" B{Caution: method not trustworthy} """
		warn("method not trustworthy") #TODO
		i = 0
		for o in self.objects:
			for r in o.residues:
				for a in r.atoms:
					i += 1
					if(a == given_atom):
						return(i)

		return(None)

	def get_atom_by_atomnumber(self, atomnumber):
		""" B{Caution: method not trustworthy} """
		warn("method not trustworthy") #TODO
		i = 0
		for o in self.objects:
			for r in o.residues:
				for a in r.atoms:
					i += 1
					if(i == atomnumber):
						return(a)
		return(None)
		
#===============================================================================
class Chain(object):
	def __init__(self, ID):
		self.chain_id = ID
		self.residues = []
		self.resSeq2resIndex = {} #only needed during reading

	def insertResidueAfter(self, before_residue, new_residue):
		i = self.residues.index(before_residue)
		self.residues.insert(i+1, new_residue)

	
	def addAtom(self, resName, resSeq, atom):
		if(not self.resSeq2resIndex.has_key(resSeq)):
			self.residues.append( Residue(resName) )
			self.resSeq2resIndex[resSeq] = len(self.residues)-1
		i = self.resSeq2resIndex[resSeq]
		self.residues[i].addAtom(atom)
		
	
	# old version - got problem with pdb from trjconv. counts residues continuesly after change of chain
	#def addAtom(self, resName, resSeq, atom):
	#	if(len(self.residues) < resSeq):
	#		self.residues.append(Residue(resName))
	#	self.residues[resSeq-1].addAtom(atom)

	def to_pdb(self, counters):
		output = ""
		# filtering out empty residues
		self.residues = [r for r in self.residues if len(r.atoms) > 0]
		for (res_num, r) in  enumerate(self.residues):
			output += r.to_pdb(self.chain_id, res_num+1, counters)
		return(output)
	
	#def deleteResidue(self, residue):
	#	self.residues.remove(residue)
	

#===============================================================================
class Residue(object):
	def __init__(self, name):
		self.name = name
		self.atoms = list()
	
	def addAtom(self, atom):
		self.atoms.append(atom)
	
	def deleteAtom(self, atom):
		self.atoms.remove(atom)
		
	def atomByName(self, atomname):
		for a in self.atoms:
			if(a.name == atomname):
				return(a)
		raise(Exception("Atom not found: "+atomname))

	def to_pdb(self, chain_id, res_num, counters):
		output = ""
		for a in self.atoms:
			output += a.to_pdb(chain_id, self.name, res_num, counters)
		return(output)
	
	def getCenter(self):
		raise(Exception("Not working at the moment"))
		#center = sum([a.position for a in self.atoms], Vector(0,0,0))
		#center = center / len(self.atoms)
		#return(center)

	def moveCenter(self, vector):
		for a in self.atoms:
			a.position += vector

	def rotate(self, matrix):
		for a in self.atoms:
			a.position = matrix*a.position
	

#===============================================================================
class Atom(object):
	def __init__(self, name, position):
		self.name = name
		self.position = position
	
	def to_pdb(self, chain_id, resName, res_num, counters):
		counters['atom_num'] += 1
		raw = {'serial':counters['atom_num'], 'name':self.name, 'resName':resName, 'chainID':chain_id, 'resSeq':res_num}
		raw['x'] = self.position.x()
		raw['y'] = self.position.y()
		raw['z'] = self.position.z()
		return(format_atom(raw)+"\n")
		
#===============================================================================



#EOF
