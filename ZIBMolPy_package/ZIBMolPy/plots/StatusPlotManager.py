# -*- coding: utf-8 -*-

import gtk

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
		for x in ("sampling_status", "extension_status", "nodes_vs_alpha"):
			rb = gtk.RadioButton(group=rb, label=x.replace("_"," "))
			setattr(self, "rb_"+x, rb)
			rb.connect("toggled", self.update)
			panel.pack_start(rb, expand=False)
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
		self.board.canvas.figure.canvas.draw_idle()

	def node2status(self, n):
		if(n.is_extended): return("extended") 
		if(n.is_locked): return("in progress")
		if not(n.has_trajectory) and n.state == "mdrun-able": return('not sampled')
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
