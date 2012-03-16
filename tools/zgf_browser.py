#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from os import path
import threading
import numpy as np
import subprocess
import locale
import os
import traceback
import time
import base64
from glob import glob
import pkgutil

import ZIBMolPy.plots
from ZIBMolPy.pool import Pool
import pango # Pango is a library for rendering internationalized texts
import gobject
import gtk
import webbrowser
import ctypes

gobject.threads_init()
gtk.gdk.threads_init()
from warnings import filterwarnings, warn 
filterwarnings("ignore", "Module matplotlib was already imported")
import matplotlib
matplotlib.use('GTKAgg')

from matplotlib.figure import Figure
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas


WIKI_URL = "https://wiki.kobv.de/confluence/display/AGCMD/ZIBMolPy"


#===============================================================================
def main():
	matplotlib.rcParams['font.size'] = 16.0
	
	# turns on icons on gtk.Button(stock=...)
	# does not work everywhere.
	# gtk.settings_get_default().props.gtk_button_images = True
	
	board = Blackboard()
	FileChangesObserver(board)
	board.pool = Pool()
	if(len(board.pool) > 0):
		board.selected_node = board.pool[0]
	
	mw = MainWindow(board)
	mw.show_all()
	try:
		gtk.main()
	except:
		traceback.print_exc()
		gtk.gdk.threads_leave() #avoids dead lock with e.g. RunDialog

#===============================================================================
def get_logo_pixbuf():
	pbl = gtk.gdk.PixbufLoader()
	pbl.write(base64.b64decode(logo_png_b64))
	pbl.close()
	return(pbl.get_pixbuf())
 	
#===============================================================================
class MainWindow(gtk.Window):
	def __init__(self, board):
		gtk.Window.__init__(self)

		self.board = board
		self.set_title("ZIBgridfree Browser")

		# scale window if run on Abteilungsnotebook ;)
		width = 1210
		height = 800
		vpaned_pos = 550
		screen = gtk.gdk.display_get_default().get_default_screen()		
		if(screen.get_height() < 940):
			height = 660
			vpaned_pos = 455
		self.set_size_request(width, height)

		#self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(6400, 6400, 6440))
		self.set_position(gtk.WIN_POS_CENTER)
		self.set_icon(get_logo_pixbuf())
		self.connect("destroy", gtk.main_quit)
		
		
		accel_group = gtk.AccelGroup()
		self.add_accel_group(accel_group)
		
		vbox = gtk.VBox(False, 2)
		self.add(vbox)
		self.menu_bar = Menubar(board, accel_group)
		vbox.pack_start(self.menu_bar, expand=False)
		#vbox.pack_start(Toolbar(board), expand=False)

							
		vpaned = gtk.VPaned()
		vpaned.set_position(vpaned_pos)
		vbox.pack_start(vpaned)
		vbox.pack_start(Statusbar(self.board), expand=False)
					
		hpaned = gtk.HPaned()
		hpaned.set_position(950)
		vpaned.add1(hpaned)
		vpaned.add2(ScrolledWindow(NodeList(self.board)))
		hpaned.add2(ScrolledWindow(CoordinateList(self.board)))
				
		#load everything from ZIBMolPy.plots.
		managers = []
		for m in pkgutil.walk_packages(ZIBMolPy.plots.__path__):
			__import__('ZIBMolPy.plots.'+m[1])
			mod = getattr(ZIBMolPy.plots, m[1])
			constructor = getattr(mod, m[1])
			plot_manager = constructor(board)
			managers.append(plot_manager)
		
		managers.sort(key=lambda x: x.sortkey)
		self.managed_plots_panel = ManagedPlotsPanel(board, managers)
		hpaned.add1(self.managed_plots_panel)
		
		
		self.show_all()
	
#===============================================================================
class Blackboard(object):
	#---------------------------------------------------------------------------	
	def __init__(self):
		self.listeners = []
		self.pool = None
		self.selected_node = None
		self.selected_coords = []
		self.selected_plot_manager = None
	
	# multiple coordinates can be selected, hence selected_coords is a list
	# for legacy and convenience, an interface for single selection is provided
	@property
	def selected_coord(self):
		if(len(self.selected_coords) == 0):
			return(None)
		return(self.selected_coords[0])
	
	# pylint does not understand decorator-magic
	#pylint: disable=E1101, E0102  
	@selected_coord.setter 
	def selected_coord(self, value):
		if(value == None):
			self.selected_coords = []
		else:
			self.selected_coords = [ value ]
	
	#---------------------------------------------------------------------------
	def fire_listeners(self, dummy_widget=None):
		#print("Firing listeners...")
		for callback in self.listeners:
			#t1 = time.time()
			callback()
			#t2 = time.time()
			#print("Callback: %d ms for %s "%((t2-t1)*1000.0, str(callback)))
		#print("")
		
		

#===============================================================================
class FileChangesObserver:
	def __init__(self, board):
		self.board = board
		self.mtime_analysis_dir = -1 # very old
		if(path.exists("./analysis/")):
			self.mtime_analysis_dir = path.getmtime("./analysis/")
		thread = threading.Thread(target=self.run)
		thread.daemon = True
		thread.start()

	#---------------------------------------------------------------------------
	def run(self):
		while(True):
			time.sleep(1)
			try:
				self.check()
			except:
				traceback.print_exc()
				
	#---------------------------------------------------------------------------			
	def check(self):
		if(self.board.pool == None): return
		found_changes = False
		for n in self.board.pool:
			if(not path.exists(n.filename)):
				continue #node not saved to disk, yet
			mt = np.maximum(path.getmtime(n.filename), path.getmtime(n.dir))
			
			#we wait another second until we reload
			if(n.mtime < mt and mt < time.time()-1):
				print("Reloading "+str(n))
				n.reload()
				found_changes = True
		
		if(path.exists(self.board.pool.filename)):
			mt = path.getmtime(self.board.pool.filename)
			if(self.board.pool.mtime < mt and mt < time.time()-1 ):
				print("Reloading pool")
				self.board.pool.reload()
				found_changes = True
		
		if(path.exists("./nodes/")):
			mt = path.getmtime("./nodes/")
			if(self.board.pool.mtime_nodes < mt and mt < time.time()-1 ):
				print("Reloading node-list")
				self.board.pool.reload_nodes()
				found_changes = True

		if(path.exists("./analysis/")):
			mt = path.getmtime("./analysis/")
			if(self.mtime_analysis_dir < mt and mt < time.time()-1 ):
				print("Directory changed: analysis")
				self.mtime_analysis_dir = mt				
				found_changes = True
		
		if(found_changes):
			gtk.gdk.threads_enter()
			self.board.fire_listeners()		
			gtk.gdk.threads_leave()


#===============================================================================
class AboutDialog(gtk.AboutDialog):
	def __init__(self):
		gtk.AboutDialog.__init__(self)
		citation = "M. Weber, S. Kube, L. Walter, P. Deuflhard:\nStable computation of probability densities\nfor metastable dynamical systems,\nMultiscale Board. Simul. 6(2):396-416, 2007"
		self.set_name("ZIBgridfree")
		self.set_version("v0.0")
		self.set_copyright("© Zuse Institut Berlin"+"\nPlease cite:\n"+citation)
		self.set_comments("pool-format: "+str(Pool.FORMAT_VERSION))
		#self.set_license("unkown license")
		#self.set_website(WIKI_URL)
		#self.set_website_label("wiki of the ZIBMolPy project")
		self.set_authors(["Ole Schütt", "Alexander Bujotzek", "Marcus Weber"])
		self.set_logo(get_logo_pixbuf())
		
#===============================================================================
class Statusbar(gtk.Statusbar):
	def __init__(self, board):
		gtk.Statusbar.__init__(self)
		self.board = board
		board.listeners.append(self.update)
		self.update()
	

	def update(self):
		if(len(self.board.pool)==0):
			return
		
		msg_parts = []

		size_msg = "pool-size=1"
		n_refined = len(self.board.pool.where("state == 'refined'"))
		if(n_refined > 1):
			size_msg += "+%d"%(n_refined-1)
		n_active = len(self.board.pool)-n_refined
		if(n_active > 0):
			size_msg += "+%d"%n_active
		n_needy = len(self.board.pool.where("state != 'converged'")) - n_refined
		if(n_needy > 0):
			size_msg += "(%d)"%n_needy

		msg_parts.append(size_msg)
	
		if(self.board.pool.alpha!=None):
			msg_parts.append("α=%.2f"%self.board.pool.alpha)
		
		t_left = 0 #time still needed (estimate) 
		t_used = 0 #time already used
		
		for n in self.board.pool:
			if(not hasattr(n,"extensions_max")):
				continue #this is probably the root-node
			expected_exts = n.extensions_max/2.0 #how many extension do we expect?
			if n.is_sampled:
				t_used += n.sampling_length + n.extensions_length * n.extensions_counter
			elif(n.extensions_counter == 0):
				t_left += n.sampling_length +  n.extensions_length * expected_exts 
			else:
				t_used += n.sampling_length + n.extensions_length * n.extensions_counter
				t_left +=  n.extensions_length * max(1, expected_exts - n.extensions_counter)
		
		msg_parts.append("time-used=%d ps"%t_used)
		msg_parts.append("time-left (est.)=%d ps"%t_left)
		ctx = self.get_context_id("foobar")
		self.pop(ctx)
		self.push(ctx, "   ".join(msg_parts))
		#"put something interesting here last update: "+str(time.time())

#===============================================================================
class ScrolledWindow(gtk.ScrolledWindow):
	def __init__(self, inner_widget):
		gtk.ScrolledWindow.__init__(self)
		self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.add(inner_widget)



#===============================================================================
class Menubar(gtk.MenuBar):
	def __init__(self, board, accel_group):
		gtk.MenuBar.__init__(self)
		self.board = board
		self.accel_group = accel_group
		
		self.tool_buttons = []
		all_tools = [path.basename(fn)[:-3] for fn in glob(path.dirname(sys.argv[0])+"/zgf_*.py")]
		PIPELINE_TOOLS = ("zgf_create_pool", "zgf_create_nodes", "zgf_setup_nodes", "zgf_grompp", "zgf_mdrun", "zgf_refine", "zgf_reweight", "zgf_analyze")
		other_tools = sorted([t for t in all_tools if t not in PIPELINE_TOOLS and t!="zgf_browser"])
		self.mk_tools_menu(PIPELINE_TOOLS, "Pipeline", accelerate=True)
		self.mk_tools_menu(other_tools, "Tools")
		self.mk_menu_plot()
		self.mk_menu_misc()
		self.mk_menu_help()
		
		board.listeners.append(self.update)
		self.update()
	
	#---------------------------------------------------------------------------
	def mk_tools_menu(self, tools, label, accelerate=False):
		menu = gtk.Menu()
		for (i,t) in enumerate(tools):
			try:
				__import__(t)
			except:
				warn("Could not import tool %s."%t)
				#traceback.print_exc()
				continue
				
			mi = gtk.MenuItem(t, use_underline=False)
			self.tool_buttons.append(mi)
			mi.connect("activate", self.on_tool_clicked)
			if(accelerate):
				mi.add_accelerator("activate", self.accel_group, gtk.gdk.keyval_from_name("F%d"%(i+1)), 0, gtk.ACCEL_VISIBLE)
			menu.append(mi)
		menuitem_label = gtk.MenuItem(label)
		menuitem_label.set_submenu(menu)
		self.append(menuitem_label)
	
	#---------------------------------------------------------------------------
	def mk_menu_plot(self):
		plot_menu = gtk.Menu()
		for x in ("title", "legend", "colors"):
			cbi =  gtk.CheckMenuItem(label="show "+x)
			cbi.add_accelerator("activate", self.accel_group, gtk.gdk.keyval_from_name(x[0]), 0, gtk.ACCEL_VISIBLE)
			cbi.set_active(True)
			setattr(self.board, "cb_show_"+x, cbi)
			cbi.connect("activate", self.board.fire_listeners)
			plot_menu.append(cbi)
		
		# item_save_figure get connected in MainWindow
		self.item_save_figure = gtk.ImageMenuItem(gtk.STOCK_SAVE)
		self.item_save_figure.set_property("always-show-image", True)
		self.item_save_figure.connect("activate", self.on_save_figure)
		self.item_save_figure.add_accelerator("activate", self.accel_group, gtk.gdk.keyval_from_name("S"), gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

		plot_menu.append(self.item_save_figure)
				
		plot_menuitem = gtk.MenuItem("Plot")
		plot_menuitem.set_submenu(plot_menu)
		self.append(plot_menuitem)
	
	
	#---------------------------------------------------------------------------
	def mk_menu_misc(self):
		plot_menu = gtk.Menu()
		self.board.cb_validate_locks =  gtk.CheckMenuItem(label="Validate locks")
		self.board.cb_validate_locks.set_active(False)
		self.board.cb_validate_locks.connect("activate", self.board.fire_listeners)
		self.board.cb_validate_locks.add_accelerator("activate", self.accel_group, gtk.gdk.keyval_from_name("V"), 0, gtk.ACCEL_VISIBLE)
		plot_menu.append(self.board.cb_validate_locks)
		plot_menuitem = gtk.MenuItem("Misc")
		plot_menuitem.set_submenu(plot_menu)
		self.append(plot_menuitem)
	
	#---------------------------------------------------------------------------
	def mk_menu_help(self):
		menu_help = gtk.Menu()
		mi_wiki = gtk.MenuItem("Open Wiki")
		mi_wiki.connect("activate", self.on_open_wiki_clicked)
		menu_help.append(mi_wiki)
		
		mi_about = gtk.ImageMenuItem(gtk.STOCK_DIALOG_INFO)
		mi_about.set_label("About")
		mi_about.set_property("always-show-image", True)
		mi_about.connect("activate", self.on_about_clicked)
		menu_help.append(mi_about)
		
		menuitem_help = gtk.MenuItem("Help")
		menuitem_help.set_submenu(menu_help)
		self.append(menuitem_help)
		
	#---------------------------------------------------------------------------
	def on_about_clicked(self, dummy_widget):
		d = AboutDialog()
		d.run()
		d.destroy()
	
	def on_open_wiki_clicked(self, dummy_widget):
		webbrowser.open_new(WIKI_URL)
	
	def on_tool_clicked(self, widget):
		StartDialog(widget.get_label())
		
	#---------------------------------------------------------------------------
	def on_save_figure(self, dummy_event):
		buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK)
		file_chooser = gtk.FileChooserDialog(title="Save Figure", action=gtk.FILE_CHOOSER_ACTION_SAVE, buttons=buttons)
		#file_chooser.set_property('do-overwrite-confirmation',True)
		
		for x in ("png", "pdf"):
			ff = gtk.FileFilter()
			ff.set_name(x.upper()+" Image")
			ff.add_pattern("*."+x)
			ff.extension = x #a new attribute for our own use
			file_chooser.add_filter(ff) 
		
		sug_fn = self.board.selected_plot_manager.name+"_"+self.board.selected_node.name + "_" + self.board.selected_coord.label + "_" + str(int(time.time()))
		file_chooser.set_current_name(sug_fn) #suggested filename - without extendsion
		
		response = file_chooser.run()
		if(response == gtk.RESPONSE_OK):
			fn = file_chooser.get_filename()+"."+file_chooser.get_filter().extension
			self.board.canvas.figure.savefig(fn, dpi=200, bbox_inches='tight')
			print("Saved figure to: "+fn)
		file_chooser.destroy()

	#---------------------------------------------------------------------------
	def update(self):
		self.item_save_figure.set_sensitive(self.board.selected_node!=None and self.board.selected_coord!=None)
		for btn in self.tool_buttons:
			zgf_command = btn.get_label()
			module = __import__(zgf_command)
			if(not hasattr(module, "is_applicable")):
				continue
			
			if(hasattr(module, "is_applicable")):
				try:
					a = module.is_applicable()
					btn.set_sensitive(a)
				except:
					warn("Could not run %s.is_applicable() ."%module.__name__)
					#traceback.print_exc()

	
#===============================================================================	
class ManagedPlotsPanel(gtk.HBox):
	def __init__(self, board, managers):
		gtk.HBox.__init__(self)
		self.board = board
		self.managers = managers
		self.notebook = gtk.Notebook()
		self.notebook.set_tab_pos(gtk.POS_LEFT)
		
		figure = Figure(figsize=(1,1), dpi=60)
		self.board.canvas = FigureCanvas(figure)
		
		
		for m in self.managers:
			tab = m.get_ctrl_panel()
			tab_label = gtk.Label(m.name)
			tab_label.set_angle(90)
			self.notebook.append_page(tab, tab_label)
		self.notebook.connect("switch-page", self.on_switch_page)	
		
				
		self.pack_start(self.notebook, expand=False)
		self.pack_start(self.board.canvas)
	
	def on_switch_page(self, dummy_widget, dummy_page, page_num):
		if(self.board.selected_plot_manager != None):
			self.board.selected_plot_manager.end_session()
		self.board.selected_plot_manager = self.managers[page_num]
		self.board.selected_plot_manager.begin_session()


#===============================================================================
class MyComboBox(gtk.ComboBox):
	def __init__(self, option):
		#equivalent to gtk.combo_box_new_text()
		# TODO: evtl von VBox erben und ^^^^ benutzen
		liststore = gtk.ListStore(gobject.TYPE_STRING)
		gtk.ComboBox.__init__(self, liststore)
		cell = gtk.CellRendererText()
		self.pack_start(cell, True)
		self.add_attribute(cell, 'text', 0)
		
		for c in option.choices:
			self.append_text(c)
		self.set_active(0)
		
	def get_text(self):
		return self.get_active_text()

#-------------------------------------------------------------------------------
class MyEntry(gtk.Entry):
	def __init__(self, option):
		gtk.Entry.__init__(self)
		if(option.default):
			self.set_text(str(option.default))

#-------------------------------------------------------------------------------
class MySpinButton(gtk.SpinButton):
	def __init__(self, option):
		gtk.SpinButton.__init__(self)
		self.option = option
		assert(option.datatype in ('int', 'float'))
		(min_value, max_value)  = (-1*float(sys.maxint), float(sys.maxint))
		if(option.min_value != None):
			min_value = float(option.min_value)
		if(option.max_value != None):
			max_value = float(option.max_value)
		self.set_range(min_value, max_value)
		if(option.datatype == "float"):
			self.set_digits(1) #TODO: make adaptive
			self.set_increments(0.1, 1)  #TODO: make adaptive
		else:
			self.set_increments(1, 10)  #TODO: make adaptive
		if(option.default):
			self.set_value(option.default)
		
	def get_text(self):
		v = self.get_adjustment().get_value()
		if(self.option.datatype == 'int'):
			return( str(int(v)) )
		return str(v)

#-------------------------------------------------------------------------------
class MyCheckButton(gtk.CheckButton):
	def __init__(self, option):
		gtk.CheckButton.__init__(self)
		self.set_active(option.default)
	
	def get_text(self):
		if(self.get_active()):
			return(" ")
		else:
			return("")
		#return str(int(self.get_active()))
		
#-------------------------------------------------------------------------------
class MyFileChooser(gtk.FileChooserButton):
	def __init__(self, option):
		gtk.FileChooserButton.__init__(self, 'Select a File')
		f = gtk.FileFilter()
		f.add_pattern("*."+option.extension)
		self.set_filter(f)
		if(option.default):
			self.set_filename(option.default)
	
	def get_text(self):
		fn = self.get_filename()
		if(fn == None):
			return("")
		return path.relpath(fn, os.getcwd())

#-------------------------------------------------------------------------------
class MyNodeChooser(gtk.ScrolledWindow):
	def __init__(self, multiples=False):
		gtk.ScrolledWindow.__init__(self)
		self.liststore = gtk.ListStore(gobject.TYPE_STRING)
		self.view = gtk.TreeView(self.liststore)
		for n in Pool():
			self.liststore.append((n.name,))
		self.view = gtk.TreeView(self.liststore)
		self.view.set_headers_visible(False)
		column = gtk.TreeViewColumn()
		cell = gtk.CellRendererText()
		column.pack_start(cell)
		column.add_attribute(cell,'text',0)
		self.view.append_column(column)
		if(multiples):
			self.view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
		self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.add(self.view)
		
	def get_text(self):
		rows = self.view.get_selection().get_selected_rows()[1]
		names = [self.liststore[i][0] for i in rows]
		return(",".join(names))

#-------------------------------------------------------------------------------
class StartDialog(gtk.Dialog):
	def __init__(self, zgf_command):
		gtk.Dialog.__init__(self, title=zgf_command)
		self.command = zgf_command
		self.resize(350,400)
		tooltips = gtk.Tooltips()
		self.module = __import__(zgf_command)
		self.entries = {}
		
		if(hasattr(self.module, "options_desc")):
			for o in self.module.options_desc:
				if(o.datatype=="choice"):
					w = MyComboBox(o)
				elif(o.datatype=="file"):
					w = MyFileChooser(o)
				elif(o.datatype=="bool"):
					w = MyCheckButton(o)
				elif(o.datatype in ("int", "float")):
					w = MySpinButton(o)
				elif(o.datatype=="str"):
					w = MyEntry(o)
				elif(o.datatype=="node"):
					w = MyNodeChooser()
				elif(o.datatype=="node-list"): 
					w = MyNodeChooser(multiples=True)
				else:
					raise(Exception("Unkown datatype: "+o.datatype))
				
				hbox = gtk.HBox()
				label = gtk.Label(o.long_name+":")
				label.set_alignment(0, 0)
				label.set_width_chars(18)
				hbox.pack_start(label, expand=False)
				hbox.pack_start(w, expand=True)
				tooltips.set_tip(hbox, o.help)
				self.vbox.pack_start(hbox, expand=False)
				self.entries[o.long_name] = w
		
		
		b_cancel = gtk.Button(stock=gtk.STOCK_CANCEL)
		b_cancel.connect("clicked", self.on_clicked)
		self.action_area.pack_start(b_cancel)
			
		b_ok = gtk.Button(stock=gtk.STOCK_OK)
		b_ok.connect("clicked", self.on_clicked)
		self.action_area.pack_start(b_ok)
		
		if(len(self.entries) == 0):
			self.on_clicked(b_ok) #skip empty dialog
		else:
			self.show_all()
				
	#---------------------------------------------------------------------------
	def on_clicked(self, widget):
		if(widget.get_label() == "gtk-ok"):
			cmd = [self.command+".py"]
			if(hasattr(self.module, "options_desc")):
				cmd += ["--gui"]
				for o in self.module.options_desc:
					value = self.entries[o.long_name].get_text()
					if(len(value)>0):
						cmd += ["--"+o.long_name, value]
				
			RunDialog(cmd, self.command).show_all()
			
		self.destroy()
	
	
#===============================================================================
class RunDialog(gtk.Dialog):
	def __init__(self, command, title):
		gtk.Dialog.__init__(self, title=title)
		self.command = command
		self.process = None
		#self.command = ["ping", "www.google.de"]
		self.set_title(title)
		sw = gtk.ScrolledWindow()
		sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.textview = gtk.TextView()
		#Courier 12
		#Luxi Mono 12
		pangoFont = pango.FontDescription("Courier 10")
		self.textview.modify_font(pangoFont)
		
		sw.add(self.textview)

		width = 600
		height = 800
		screen = gtk.gdk.display_get_default().get_default_screen()		
		if(screen.get_height() < 940):
			height = 660
		self.resize(width, height)

		self.vbox.pack_start(sw)
		
		self.button = gtk.Button("Cancel")
		self.button.connect("clicked", self.on_clicked)
		self.action_area.pack_start(self.button)
			
		self.thread = threading.Thread(target=self.run)
		self.thread.start()
	
	#---------------------------------------------------------------------------
	def run(self):
		encoding = locale.getpreferredencoding()
		def utf8conv(x): return(unicode(x, encoding).encode('utf8'))
		self.write2buffer("Running: %s\n"%str(self.command))
		
		#ensure, that childprocess dies when parent dies. Alternative: write own signal-handler e.g for atexit-modeul
		#http://stackoverflow.com/questions/1884941/killing-the-child-processes-with-the-parent-process
		libc = ctypes.CDLL('libc.so.6')
		PR_SET_PDEATHSIG = 1; TERM = 15
		implant_bomb = lambda: libc.prctl(PR_SET_PDEATHSIG, TERM)
		try:
			self.process = subprocess.Popen(self.command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,  preexec_fn=implant_bomb)
		except:
			self.write2buffer(traceback.format_exc())
			self.set_closeable()
			return
			
		while True:
			line = self.process.stdout.readline()
			if not line:
				break
			self.write2buffer(utf8conv(line))
		self.process.communicate() # better than wait - should not block and sets returncode
		self.write2buffer("\nProcess finished. Returncode: %d\n"%self.process.returncode)
		self.set_closeable()
	
	#---------------------------------------------------------------------------
	def set_closeable(self):
		self.process = None
		gtk.gdk.threads_enter()
		self.button.set_label("Close")
		gtk.gdk.threads_leave()
		
	#---------------------------------------------------------------------------
	def write2buffer(self, line_utf8):
		gtk.gdk.threads_enter()
		b = self.textview.get_buffer()
		i = b.get_end_iter()
		b.place_cursor(i)
		b.insert(i, line_utf8)
		self.textview.scroll_to_mark(b.get_insert(), 0.1)
		gtk.gdk.threads_leave()
	
	
	#---------------------------------------------------------------------------
	def on_clicked(self, dummy_widget):
		if(self.process):
			gtk.gdk.threads_leave()
			self.write2buffer("\nTerminating Process...")
			gtk.gdk.threads_enter()
			self.process.terminate()
		else:
			self.destroy()
		
#===============================================================================
class CoordinateList(gtk.TreeView):
	def __init__(self, board):
		self.board = board
		self.board.listeners.append(self.update)
		self.updateing = False # prevents cirular board <-> treeview updates
		
		#liststore = gtk.ListStore(str, str, str)
		liststore = gtk.ListStore(str, str)
		gtk.TreeView.__init__(self, liststore)
		renderer = gtk.CellRendererText()
		self.append_column(gtk.TreeViewColumn("Label", renderer, text=0))
		self.append_column(gtk.TreeViewColumn("Atoms", renderer, text=1))
		#self.append_column(gtk.TreeViewColumn("Weight", renderer, text=2))
		self.append_column(gtk.TreeViewColumn("")) #placeholder
		self.set_sensitive(False)
		selection = self.get_selection()
		selection.set_mode(gtk.SELECTION_MULTIPLE)
		selection.connect("changed", self.on_select)
		self.update()
				
	#---------------------------------------------------------------------------
	def update(self):
		#TODO: noch nicht perfekt bei pool-wechsel
		if(self.board.pool.converter != None):
			coords = self.board.pool.converter
		else:
			coords = []

		self.set_sensitive(len(coords) > 0)
		  		
		if(len(coords) != self.get_model().iter_n_children(None)):
			self.get_model().clear()
			for c in coords:
				#self.get_model().append([c.label, str(c.atoms), "%1.3f"%c.weight])
				self.get_model().append([c.label, str(c.atoms)])
			#self.get_selection().select_path((0,)) #select first element
			self.board.selected_coord = self.board.pool.converter[0]
			self.board.fire_listeners()
  		
  		
		self.updateing = True  # prevents cirular board <-> treeview updates
		for c in coords:
			if(c in self.board.selected_coords):
				self.get_selection().select_path((c.index,))
			else:
				self.get_selection().unselect_path((c.index,))
		
		self.updateing = False # prevents cirular board <-> treeview updates
  		
	#---------------------------------------------------------------------------	
	def on_select(self, dummy_widget):
		if(self.updateing):  # prevents cirular board <-> treeview updates
			return
			
		cursor = self.get_cursor()[0][0] # give the latest selected row
		idxs = [ r[0] for r in self.get_selection().get_selected_rows()[1] ]
		
		# put cursor before other rows
		idxs_wo_cursor = [ i for i in idxs if i!=cursor ]
		idxs_ordered = [cursor] + idxs_wo_cursor
		
		coords = [ self.board.pool.converter[i] for i in idxs_ordered ]
		self.board.selected_coords = coords
		self.board.fire_listeners()


#===============================================================================
class NodeList(gtk.TreeView):
	def __init__(self, board):
		liststore = gtk.ListStore(str, str, str, bool, str, bool, str, str, bool, bool, bool)
		gtk.TreeView.__init__(self, liststore)
		self.board = board
		self.board.listeners.append(self.update)
		self.updateing = False # prevents cyclic-events between update and on_select
		# beefy row colors (nice for text)
		#self.colors = {'default': '#FFFFFF', 'refined': '#969696', 'active': '#00A120', 'stale': '#C40000'}
		# flimsy row colors	(nice for background)
		self.colors = {'default': '#FFFFFF', 'refined': '#D8D8D8', 'active': '#A6E8A6', 'stale': '#E8A6A7'}

		renderer1 = gtk.CellRendererText()
		
		renderer2 = gtk.CellRendererToggle()
		renderer2.connect('toggled', self.on_toggled_convlog)
				
		renderer3 = gtk.CellRendererToggle()
		renderer3.connect('toggled', self.on_toggled_weightlog)
		
		renderer4 = gtk.CellRendererToggle()
		renderer4.connect('toggled', self.on_toggled_trajectory)
		
		renderer5 = gtk.CellRendererToggle()
		renderer5.connect('toggled', self.on_toggled_mdlog)
		
		renderer6 = gtk.CellRendererToggle()
				
		self.append_column(gtk.TreeViewColumn("Name", renderer1, text=1))
		self.append_column(gtk.TreeViewColumn("State", renderer1, text=2))
		self.append_column(gtk.TreeViewColumn("Restrained", renderer6, active=3))
		self.append_column(gtk.TreeViewColumn("Extension", renderer1, text=4))
		self.append_column(gtk.TreeViewColumn("ConvLog", renderer2, active=5))
		self.append_column(gtk.TreeViewColumn("Weight (dir.)", renderer1, text=6))
		self.append_column(gtk.TreeViewColumn("Weight (corr.)", renderer1, text=7))
		self.append_column(gtk.TreeViewColumn("WeightLog", renderer3, active=8))
		self.append_column(gtk.TreeViewColumn("Trajectory", renderer4, active=9))
		self.append_column(gtk.TreeViewColumn("MDLog", renderer5, active=10))
		self.append_column(gtk.TreeViewColumn("")) # placeholder
						 

		# TODO: images would be nicer than toogles, 
		# but I do not kown how to receive click events from CellRendererPixbuf
		# http://stackoverflow.com/questions/4940351/gtk-treeview-place-image-buttons-on-rows
		
		# renderer1 = gtk.CellRendererText()
		# 
		# renderer2 = gtk.CellRendererPixbuf()
		# renderer2.set_property("stock_id", gtk.STOCK_OPEN)
		# renderer2.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
		# renderer2.connect('clicked', self.on_toggled_convlog)
		# 
		# renderer3 = gtk.CellRendererPixbuf()
		# renderer3.set_property("stock_id", gtk.STOCK_OPEN)
		# renderer3.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
		# renderer3.connect('clicked', self.on_toggled_weightlog)
		# 
		# renderer4 = gtk.CellRendererPixbuf()
		# renderer4.set_property("stock_id", gtk.STOCK_OPEN)
		# renderer4.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
		# renderer4.connect('clicked', self.on_toggled_trajectory)
		# 
		# renderer5 = gtk.CellRendererPixbuf()
		# renderer5.set_property("stock_id", gtk.STOCK_OPEN)
		# renderer5.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
		# renderer5.connect('clicked', self.on_toggled_mdlog)
				# 
		# self.append_column(gtk.TreeViewColumn("Name", renderer1, text=1))
		# self.append_column(gtk.TreeViewColumn("State", renderer1, text=2))
		# self.append_column(gtk.TreeViewColumn("Extension", renderer1, text=3))
		# self.append_column(gtk.TreeViewColumn("ConvLog", renderer2, sensitive=4))
		# self.append_column(gtk.TreeViewColumn("Weight (dir.)", renderer1, text=5))
		# self.append_column(gtk.TreeViewColumn("Weight (corr.)", renderer1, text=6))
		# self.append_column(gtk.TreeViewColumn("WeightLog", renderer3, sensitive=7))
		# self.append_column(gtk.TreeViewColumn("Trajectory", renderer4, sensitive=8))
		# self.append_column(gtk.TreeViewColumn("MDLog", renderer5, sensitive=9))
		# self.append_column(gtk.TreeViewColumn("")) # placeholder
		
		for c in self.get_columns():
			for r in c.get_cell_renderers():
				c.add_attribute(r, "cell-background", 0)
		
		selection = self.get_selection()
		selection.set_mode(gtk.SELECTION_BROWSE)
		selection.connect("changed", self.on_select)
		self.set_sensitive(False)
		self.update()
		
		#self.connect("row-activated", self.hello) #double-clicks after row is selected
		
	#---------------------------------------------------------------------------	
	def update(self):
		if(self.updateing):
			return
		self.updateing = True
		self.set_sensitive(len(self.board.pool) > 0)
			
		M = self.get_model() # shortens the following code
		
		for (i,n) in enumerate(self.board.pool):
			(ext_c, ext_m) = ("?", "?")
			if(hasattr(n, "extensions_counter")):
				ext_c =  str(n.extensions_counter)
			if(hasattr(n, "extensions_max")):
				ext_m =  str(n.extensions_max)
			ext_txt = "(%s/%s)"%(ext_c, ext_m)
			
			color = self.colors['default']
			if n.is_locked:
				color = self.colors['active']
				if(self.board.cb_validate_locks.get_active()):
					if(not n.is_lock_valid):
						color = self.colors['stale']
			elif(n.state == 'refined'):
				color = self.colors['refined']
						
			weight_direct = "n/a"
			if('weight_direct' in n.obs):
				weight_direct = "%1.10f"%n.obs.weight_direct

			weight_corrected = "n/a"
			if('weight_corrected' in n.obs):
				weight_corrected = "%1.10f"%n.obs.weight_corrected
				
			row = [color, n.name, n.state, n.has_restraints, ext_txt, n.has_convergence_log, weight_direct, weight_corrected, n.has_reweighting_log, n.has_trajectory, n.has_mdrun_log]
			
			# Updating the entire list, without clearing it. 
			# This preserves the selection and the up/down-keys still work :-)
				
			if(i >= len(M)):
				M.append(row)
			else:
				row_iter = M.get_iter((i,))
				for (j, v) in enumerate(row):
					M.set_value(row_iter, j, v)
		
			if(n == self.board.selected_node): 
				self.get_selection().select_path((i,))
	
		#delete_list must not be a generator
		delete_list = list(reversed(range(len(self.board.pool), len(M))))
		for i in delete_list:
			M.remove( M.get_iter((i,)) )
		
		self.updateing = False
		
		#TODO: is this call really nessecary???
		#self.on_select() # just in case the selected node got remove
		
  	#---------------------------------------------------------------------------
	def on_select(self, dummy_widget=None):
		selection = self.get_selection().get_selected_rows()

		if(len(selection[1]) == 0): #selection might be empty...
			new_selected_node =  None
			if(len(self.board.pool) > 0):
				new_selected_node = self.board.pool[0] #... then select the root
		else:
			i = selection[1][0][0]
			new_selected_node = self.board.pool[i]
		
		if(self.board.selected_node != new_selected_node):
			self.board.selected_node = new_selected_node
			self.board.fire_listeners()
		 	
	#---------------------------------------------------------------------------
	def on_toggled_convlog(self, widget, selection):
		if widget.get_active():
			fn = self.board.pool[int(selection)].convergence_log_fn
			RunDialog(['tail', '-f', '-n', '9999999999999999',fn], fn).show_all()   
			
	def on_toggled_weightlog(self, widget, selection):
		if widget.get_active():
			fn = self.board.pool[int(selection)].reweighting_log_fn
			RunDialog(['tail', '-f', '-n', '9999999999999999',fn], fn).show_all()   
	
	def on_toggled_trajectory(self, widget, selection):
		if widget.get_active():
			n = self.board.pool[int(selection)]
			#if(subprocess.call(['command', '-v', 'vmd'])): # is vmd installed?
			RunDialog(['vmd', n.pdb_fn, n.trr_fn], "VMD of "+str(n)).show_all()
			#else:
			#	RunDialog(['ngmx', '-f', n.trr_fn, '-s', n.tpr_fn], "ngmx of "+str(n)).show_all()
	
	def on_toggled_mdlog(self, widget, selection):
		if widget.get_active():
			fn = self.board.pool[int(selection)].mdrun_log_fn
			RunDialog(['tail', '-f', '-n', '200',fn], fn).show_all()   


#===============================================================================
logo_png_b64 = \
"""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"""

#===============================================================================
if(__name__=="__main__"):
	main()

#EOF
