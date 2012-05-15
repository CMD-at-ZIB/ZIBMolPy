# -*- coding: utf-8 -*-

import gtk
import numpy as np

import zgf_reweight

#===============================================================================
class FrameweightPlotManager(object):
	#pylint: disable=E1101, W0201
	#..., because members are also defined in get_ctrl_panel and in a dynamic way.
	#TODO: maybe create ctrl_panel within __init__
	
	def __init__(self, board):
		self.name = "FrameWeights"
		self.board = board
		self.sortkey = 20
		
	def get_ctrl_panel(self):
		panel = gtk.VBox()
		for x in ("restraint", "restraint_gmx", "phi", "frame_weights", "mean_frame_weight", "mean_phi"):
			cb =  gtk.CheckButton(label=x.replace("_"," "))
			cb.set_active(True)
			setattr(self, "cb_show_"+x, cb)
			cb.connect("toggled", self.update)
			panel.pack_start(cb, expand=False)
		return(panel)
	
	def begin_session(self):
		self.board.listeners.append(self.update)
		self.update()

	def end_session(self):
		self.board.listeners.remove(self.update)
		
	def update(self, dummy=None):
		self.board.canvas.figure.clear()
		if(len(self.board.pool)==0 or self.board.selected_node==None):
			return
		axes = self.board.canvas.figure.gca() # create new axes
		axes.grid()
		axes.set_ylabel('Energy [kJ/mol]')
		axes.set_xlabel('Frame')
		axes2 = axes.twinx() # create twin axes
		axes2.set_ylabel('Weight')

		if(self.board.cb_show_colors.get_active()):
			plotargs_phi = {'linewidth':4, 'color':'magenta', 'linestyle':'--'}
			plotargs_restraint = {'linewidth':4, 'color':'red'}
			plotargs_restraint_gmx = {'linewidth':4, 'color':'orange', 'linestyle':'--'}
			plotargs_frameweight = {'linewidth':4, 'color':'green'}
			plotargs_mean_phi = {'linewidth':4, 'color':'magenta', 'linestyle':':'}
			plotargs_mean_frameweight = {'linewidth':4, 'color':'green', 'linestyle':':'}
		else:
			plotargs_phi = {'linewidth':4, 'color':'grey', 'linestyle':'--'} 
			plotargs_restraint = {'linewidth':4, 'color':'dimgrey'}
			plotargs_restraint_gmx = {'linewidth':4, 'color':'lightgrey', 'linestyle':'--'}
			plotargs_frameweight = {'linewidth':4, 'color':'black'}
			plotargs_mean_phi = {'linewidth':4, 'color':'grey', 'linestyle':':'}
			plotargs_mean_frameweight = {'linewidth':4, 'color':'black', 'linestyle':':'}
			
		n = self.board.selected_node
		if(self.board.cb_show_title.get_active()):
			parent_name = "n/a"
			if n.parent:
				parent_name = n.parent.name
			axes.set_title("%s : frame weights (parent: %s)"%(n.name, parent_name))

		if(n.has_trajectory and n.has_internals and n.has_restraints):
			if self.cb_show_restraint.get_active():
				axes.plot(n.penalty_potential, label='Restraint', **plotargs_restraint)
			if self.cb_show_frame_weights.get_active():		
				axes2.plot(n.frameweights, label='Frame weight', **plotargs_frameweight)
			if self.cb_show_phi.get_active():
				axes2.plot(n.phi_values, label='Phi', **plotargs_phi)			
			if self.cb_show_mean_frame_weight.get_active():
				axes2.axhline(y=np.mean(n.frameweights), label='Mean frame weight', **plotargs_mean_frameweight)
			if self.cb_show_mean_phi.get_active():
				axes2.axhline(y=np.mean(n.phi_values), label='Mean phi', **plotargs_mean_phi)
			if self.cb_show_restraint_gmx.get_active():
				axes.plot(zgf_reweight.check_restraint_energy(n), label='Restraint from GMX', **plotargs_restraint_gmx)
		
		if(self.board.cb_show_legend.get_active()):
			handles = axes.get_legend_handles_labels()[0] + axes2.get_legend_handles_labels()[0] 
			labels = axes.get_legend_handles_labels()[1] + axes2.get_legend_handles_labels()[1]
			if(len(handles) > 0):
				self.board.canvas.figure.legend(handles, labels)
		
		# redraw
		self.board.canvas.draw_idle()

#===============================================================================
#EOF
