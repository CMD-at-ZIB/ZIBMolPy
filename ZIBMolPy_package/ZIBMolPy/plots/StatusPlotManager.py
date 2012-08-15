# -*- coding: utf-8 -*-

import gtk
from os import path
import numpy as np

#===============================================================================
class StatusPlotManager(object):
	#pylint: disable=E1101, W0201
	#..., because members are also defined in get_ctrl_panel and in a dynamic way.
	#TODO: maybe create ctrl_panel within __init__
	
	def __init__(self, board):
		self.name = "PoolStatus"
		self.board = board
		self.sortkey = 40
		
	def get_ctrl_panel(self):
		panel = gtk.VBox()
		rb = None
		for x in ("sampling_status", "extension_status", "nodes_vs_alpha", "nodes_vs_chi"):
			rb = gtk.RadioButton(group=rb, label=x.replace("_"," "))
			setattr(self, "rb_"+x, rb)
			rb.connect("toggled", self.update)
			panel.pack_start(rb, expand=False)
		cb =  gtk.CheckButton(label="sorted")
		setattr(self, "cb_sorted", cb)
		cb.connect("toggled", self.update)
		panel.pack_start(cb, expand=False)	

		return(panel)

	def begin_session(self):
		self.board.listeners.append(self.update)
		self.update()

	def end_session(self):
		self.board.listeners.remove(self.update)

	#---------------------------------------------------------------------------
	def update(self, dummy=None):
		self.board.canvas.figure.clear()
		if(len(self.board.pool)<=1):
			return
		self.cb_sorted.set_sensitive(False)
		if(self.rb_sampling_status.get_active()):
			self.make_pie(self.node2status, title="Sampling status")
		if(self.rb_extension_status.get_active()):
			self.make_pie(self.node2extensions, title="Extension status")
		if(self.rb_nodes_vs_alpha.get_active()):
			size = [entry['size'] for entry in self.board.pool.history]
			alpha = [entry['alpha'] for entry in self.board.pool.history]
			size.append(len(self.board.pool))	
			alpha.append(self.board.pool.alpha)	
			ax = self.board.canvas.figure.gca()
			if(self.board.cb_show_title.get_active()):
				ax.set_title("Nodes vs. alpha")
			ax.plot(size, alpha, 'rD--', linewidth=2)
			for (s, a) in zip(size, alpha)[1:]:
				ax.text(s+0.1, a-0.1, "%.4f"%a)
			ax.grid()
			ax.set_xlabel("#Nodes")
			ax.set_xticks([int(t) for t in ax.get_xticks() if t%1 == 0])
			ax.set_ylabel("Alpha")

		if(self.rb_nodes_vs_chi.get_active() and path.exists(self.board.pool.chi_mat_fn)):
			self.cb_sorted.set_sensitive(True)

			npz_file = np.load(self.board.pool.chi_mat_fn)
			chi_mat = npz_file['matrix']
			
			ax = self.board.canvas.figure.gca()
			if(self.board.cb_show_title.get_active()):
				ax.set_title("Nodes vs. chi")

			nodeticklabels = [ int(nn.replace("node","")) for nn in npz_file['node_names'] ]
			plot_range = range( 1, len(nodeticklabels)+1)

			for ic, c in enumerate( chi_mat.transpose() ):				
				if(self.cb_sorted.get_active()):
					c = sorted(c, reverse=True)
				ax.plot(plot_range, c, linewidth=2, label="cluster "+str(ic+1))

			ax.grid()
			ax.set_ylabel("Chi")
			ax.set_xticks( plot_range )
			ax.set_xlim(plot_range[0], plot_range[-1])

			if(self.cb_sorted.get_active()):
				ax.set_xlabel("#Nodes involved")
				ax.set_xticklabels(plot_range) 
			else:
				ax.set_xlabel("Node")
				ax.set_xticklabels(nodeticklabels)

			if(self.board.cb_show_legend.get_active()):
				handles = ax.get_legend_handles_labels()[0]
				labels = ax.get_legend_handles_labels()[1]
				self.board.canvas.figure.legend(handles, labels)

		self.board.canvas.figure.canvas.draw_idle()

	def node2status(self, n):
		if(n.state=='mdrun-able' and n.extensions_counter > 0 and not n.is_locked):
			return("extended") 
		elif(n.is_locked): 
			return("in progress")
		elif(not n.has_trajectory and n.state=="mdrun-able"):
			return('not sampled')
		else:
			return(n.state)

	def node2extensions(self, n):
		if not(n.has_trajectory) and n.state == "mdrun-able": return('not sampled')
		if(hasattr(n, "extensions_counter")):
			return("%d extensions"%n.extensions_counter)
		return("n/a")

	def make_pie(self, node2label, title):
		ax = self.board.canvas.figure.gca()
		states = [ node2label(n) for n in self.board.pool.where("name != '"+self.board.pool.root.name+"'")]
		labels = set(states)
		fracs = [ states.count(l) for l in labels]
		num_labels = []
		for (label, frac) in zip(labels, fracs):
			num_labels.append(label + " \n("+str(frac)+")")
		patches = ax.pie(fracs, explode=[0.05]*len(fracs), labels=num_labels, autopct='%1.f%%')[0]
		if(self.board.cb_show_title.get_active()):
			ax.set_title(title)
		if(self.board.cb_show_legend.get_active()):
			ax.legend(patches, labels)
			

#===============================================================================
#EOF
