# -*- coding: utf-8 -*-

from optparse import OptionParser

#===============================================================================
class OptionsList(list):
	
	def __getitem__(self, key):
		for o in self:
			if(o.long_name == key):
				return(o)
		raise(KeyError("Option %s not found in OptionList."%key))
	
	#---------------------------------------------------------------------------
	def epytext(self):
		output = "\nOptions\n=======\n"
		for o in self:
			output += "  - B{%s}::\n"%o.long_name
			for k, v in o.__dict__.items():
				if(v):
					output += "    %s: %s\n"%(k,v)
			output += "\n"
		return(output)
		
	#---------------------------------------------------------------------------
	def parse_args(self, argv):
		global GUI_ENABLED #pylint: disable=W0603
		
		parser = OptionParser()
		for o in self:
			if(o.datatype=="bool"):
				dt_args = {'action':"store_true"}
			elif(o.datatype=="choice"):
				dt_args = {'choices': o.choices}
			elif(o.datatype in ("file", "node", "node-list")):
				dt_args = {'type':"str"}
			else:
				dt_args = {'type':o.datatype}
			parser.add_option('-'+o.short_name, '--'+o.long_name, help=o.help_w_default(), default=o.default, **dt_args)
		
		parser.add_option('--gui', help="Enables Gui-Based dialogs", action="store_true")
		parsed_options = parser.parse_args(argv)
		
		#check min/max values
		for o in self:
			if(not hasattr(parsed_options[0], o.long_name)):
				continue
			v = getattr(parsed_options[0], o.long_name)
			if(o.min_value != None):
				assert(o.min_value <= v) 
			if(o.max_value != None):
				assert(o.max_value >= v) 
		
		
		# could get overwritten by calling other zgf-script directly as a module
		GUI_ENABLED = GUI_ENABLED or parsed_options[0].gui
		return(parsed_options)

#===============================================================================
class Option(object):
	#pylint: disable=W0622
	def __init__(self, short_name, long_name, datatype, help="", default=None, min_value=None, max_value=None, extension=None, choices=None):
		assert(datatype in ('str','int','float','bool','choice','file','node', 'node-list'))
		self.short_name = short_name
		self.long_name = long_name 
		self.datatype = datatype 
		self.help = help
		self.default = default
		self.min_value = min_value
		self.max_value = max_value
		self.extension = extension
		self.choices = choices
		if(datatype=="choice"):
			self.default = choices[0]
		
	def help_w_default(self):
		txt = self.help
		if(self.datatype=="choice"):
			txt += " (choices: %s)"%(', '.join(self.choices))
		if(self.default):
			txt += " (default: %s)"%self.default
		return(txt)


	def forward_value(self, parsed_options):
		""" usefull to forward option-values to a subprocess, see e.g. zgf_submit_job_HLRN """
		v = getattr(parsed_options, self.long_name.replace("-","_"))
		if(v==None):
			return([])
		parts = []
		if(self.datatype=="bool"):
			if(v): parts.append("--"+self.long_name)
		else:
			parts.append("--"+self.long_name+'=%s'%v)
			
		return(parts)
	
	def __repr__(self):
		return("<ZIBMolPy.ui.Option "+self.long_name+">")
		
	
#===============================================================================
GUI_ENABLED = False
def userinput(msg, datatype, condition="True", default=None):
	if(GUI_ENABLED):
		return userinput_gui(msg, datatype, condition, default)
	else:
		return userinput_cli(msg, datatype, condition, default)



#===============================================================================
def userchoice(msg, choices):
	if(GUI_ENABLED):
		return userchoice_gui(msg, choices)
	else:
		choices_str = []
		choices_chars = []
		for c in choices:
			i = c.index("_")
			choices_chars += c[i+1:i+2]
			choices_str += [ c[:i] + "(" + c[i+1] +")" + c[i+2:] ]
		msg += " "+ " or ".join(choices_str) + "?"
		return userinput_cli(msg, "str", "x in "+repr(choices_chars))


#===============================================================================
def userchoice_gui(msg, choices):
	import gtk  #pylint: disable=W0404
	buttons = sum([(c, i) for (i,c) in enumerate(choices)], ())
	dialog = gtk.Dialog(title=None, parent=None, flags=0, buttons=buttons)
	dialog.vbox.pack_start(gtk.Label(msg)) #pylint: disable=E1101
	dialog.show_all()
	response = dialog.run()
	dialog.destroy()
	c = choices[response]
	return c[c.index("_")+1]
	

#===============================================================================
def userinput_gui(msg, datatype, condition="True", default=None):
	import gtk #pylint: disable=W0404
	if(datatype == "bool"):
		md = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, message_format=msg)
		response = md.run()
		md.destroy()
		assert(response in (gtk.RESPONSE_YES, gtk.RESPONSE_NO))
		return(response==gtk.RESPONSE_YES)
	
	elif(datatype == "str"):
		cast_func = str
	elif(datatype == "int"):
		cast_func = int
	elif(datatype == "float"):
		cast_func = float
	else:
		raise(Exception("Unkown datatype: "+datatype))

	dialog = gtk.Dialog(title=None, parent=None, flags=0, buttons=(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
	dialog.vbox.pack_start(gtk.Label(msg)) #pylint: disable=E1101
	entry = gtk.Entry()
	if(default != None):
		entry.set_text(str(default))	
	dialog.vbox.pack_start(entry) #pylint: disable=E1101
	dialog.show_all()
	
	while(True):
		responce = dialog.run()
		assert(responce==gtk.RESPONSE_ACCEPT)
		x = entry.get_text()
		try:
			x = cast_func(entry.get_text())
			assert(eval(condition))
			break
		except:
			print "Oops! That was no valid input. Try again!"
	
	dialog.destroy()
	return x
 
	
	
#===============================================================================
def userinput_cli(msg, datatype, condition="True", default=None):
	if(datatype == "str"):
		cast_func = str
	
	elif(datatype == "int"):
		cast_func = int
		
	elif(datatype == "float"):
		cast_func = float
		
	elif(datatype == "bool"):
		msg += " (Y)es or (N)o"
		def cast_func(raw):
			raw = raw.strip().lower()
			assert(raw in ("y", "n", "yes", "no"))
			return(raw in ("y", "yes"))

	else:
		raise(Exception("Unkown datatype: "+datatype))
	
	if(default != None):
		print("Default: "+str(default))
	
	while True:
		try:
			raw = raw_input("\n%s: "%msg)
			if(len(raw)==0 and default!=None):
				print(default)
				return(default)
			x = cast_func(raw)
			assert(eval(condition))
			return(x)
		
		except KeyboardInterrupt:
			raise(KeyboardInterrupt) #forward exception
		except:
			print "Oops! That was no valid input. Try again!"
		
#===============================================================================
#EOF
