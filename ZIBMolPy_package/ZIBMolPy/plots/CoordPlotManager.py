# -*- coding: utf-8 -*-

import gtk
import numpy as np
from mpl_toolkits.mplot3d import Axes3D

#===============================================================================
class CoordPlotManager(object):
	#pylint: disable=E1101, W0201
	#..., because members are also defined in get_ctrl_panel and in a dynamic way.
	#TODO: maybe create ctrl_panel within __init__
	
	def __init__(self, board):
		self.name = "2DCoordDist"
		self.board = board
		self.sortkey = 55
		
	def get_ctrl_panel(self):

		panel = gtk.VBox()
		rb = None
		for x in ("presampling", "sampling"):
			rb =  gtk.RadioButton(group=rb, label=x.replace("_"," "))
			setattr(self, "rb_show_"+x, rb)
			rb.connect("toggled", self.update)
			panel.pack_start(rb, expand=False)

		sep1 = gtk.HSeparator()
		panel.pack_start(sep1, expand=False)
		
		panel.pack_start(gtk.Label("node weights:"), expand=False)
		rb = None
		for x in ("none", "direct", "corrected"):
			rb =  gtk.RadioButton(group=rb, label=x)
			setattr(self, "rb_weights_"+x, rb)
			rb.connect("toggled", self.update)
			panel.pack_start(rb, expand=False)
		
		sep2 = gtk.HSeparator()
		panel.pack_start(sep2, expand=False)

		panel.pack_start(gtk.Label("histogram bins:"), expand=False)
		self.cobo_nbins = gtk.combo_box_new_text() #TODO: is there a native int combo box?
		for v in ("50", "100", "180"):
			self.cobo_nbins.append_text(v)
		self.cobo_nbins.set_active(0)
		self.cobo_nbins.connect('changed', self.update)
		panel.pack_start(self.cobo_nbins, expand=False)
		return(panel)

	def begin_session(self):
		self.board.listeners.append(self.update)
		self.update()

	def end_session(self):
		self.board.listeners.remove(self.update)

	def update(self, dummy=None):
		self.board.canvas.figure.clear()
		cmap = "gray_r"
		if(self.board.cb_show_colors.get_active()):
			cmap = "jet"
		if(len(self.board.selected_coords) == 2):
			nbins = int(self.cobo_nbins.get_active_text())
			self.plot_3dhist(nbins, cmap)
		self.board.canvas.draw_idle()

	def plot_3dhist(self, nbins, cmap):
		xbins = ybins = nbins
		coord1 = self.board.selected_coords[1]
		coord2 = self.board.selected_coords[0]

		axes1 = Axes3D(self.board.canvas.figure)

		#axes1 = self.board.canvas.figure.gca(projection='3d') # problems mit matplotlib 0.99
		axes1.grid()
		if(self.board.cb_show_title.get_active()):
			axes1.set_title( "%s vs. %s"%(coord1.label, coord2.label) )

		axes1.set_xlabel(coord1.label+" ["+coord1.plot_label+"]")
		xscale = coord1.plot_scale
		axes1.set_ylabel(coord2.label+" ["+coord2.plot_label+"]")
		yscale = coord2.plot_scale
		
		xvalues = self.board.pool.coord_range(coord1)
		xedges = xscale(np.linspace(np.min(xvalues), np.max(xvalues), num=xbins))
		xlims = (min(xedges), max(xedges))
		axes1.set_xlim3d(xlims)

		yvalues = self.board.pool.coord_range(coord2)
		yedges = yscale(np.linspace(np.min(yvalues), np.max(yvalues), num=ybins))
		ylims = (min(yedges), max(yedges))
		axes1.set_ylim3d(ylims)

		axes1.set_zlim3d(0.0, 1.0)
		axes1.set_zlabel('Probability')

		if(self.rb_show_presampling.get_active()):
			#plotargs = {'label':'presampling'}

			xsamples = xscale(self.board.pool.root.trajectory.getcoord(coord1))
			ysamples = yscale(self.board.pool.root.trajectory.getcoord(coord2))

			hist = np.histogram2d(xsamples, ysamples, normed=True, bins=[xbins, ybins])[0]
		elif(self.rb_show_sampling.get_active()):
			#plotargs = {'label':'sampling'}

			hist = np.zeros((xbins, ybins))
			for n in self.board.pool.where("state != 'refined' and has_trajectory"):
				xsamples = xscale(n.trajectory.getcoord(coord1))
				ysamples = yscale(n.trajectory.getcoord(coord2))

				hist_node = np.histogram2d(xsamples, ysamples, normed=True, bins=[xbins, ybins], weights=n.frameweights)[0]
				if(self.rb_weights_none.get_active()):
					hist += hist_node
				elif(self.rb_weights_direct.get_active() and 'weight_direct' in n.obs):
					hist += n.obs.weight_direct * hist_node
				elif(self.rb_weights_corrected.get_active() and 'weight_corrected' in n.obs):
					hist += n.obs.weight_corrected * hist_node
		else:
			return

		X, Y = np.meshgrid(xedges, yedges)
		Z = hist

		axes1.plot_surface(X, Y, Z, rstride=1, cstride=1, alpha=1.0, cmap=cmap, antialiased=True)


#===============================================================================
#EOF
