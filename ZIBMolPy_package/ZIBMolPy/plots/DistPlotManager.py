# -*- coding: utf-8 -*-

import gtk
from ZIBMolPy.utils import get_phi_contrib, get_phi_contrib_potential
import numpy as np
import os

#===============================================================================
class DistPlotManager(object):
	#pylint: disable=E1101, W0201
	#..., because members are also defined in get_ctrl_panel and in a dynamic way.
	#TODO: maybe create ctrl_panel within __init__
	
	def __init__(self, board):
		self.board = board
		self.name = "NodeDist"
		self.sortkey = 10
		self.active = False
				
	def get_ctrl_panel(self):
		panel = gtk.VBox()
		for x in ("phi", "phi_potential", "restraint", "sampling","use_frameweights", "parent_sampling", "marker", "child_markers", "refpoints", "reweighted_hist"):
			cb =  gtk.CheckButton(label=x.replace("_"," "))
			cb.set_active(True)
			setattr(self, "cb_"+x, cb)
			cb.connect("toggled", self.update)
			panel.pack_start(cb, expand=False)	
		rwght_panel = gtk.VBox()
		rb = None                                                     
		for x in ("both", "direct", "corrected"):
			rb = gtk.RadioButton(group=rb, label=x.replace("_"," "))
			setattr(self, "rb_show_"+x, rb)
			rb.connect("toggled", self.update)
			rb.set_sensitive(False)
			rwght_panel.pack_start(rb, expand=False)
		panel.pack_start(rwght_panel, expand=False)
		clstr_panel = gtk.HBox()
		self.cb_cluster = gtk.CheckButton(label="cluster")
		self.cb_cluster.set_active(False)
		self.cb_cluster.connect("toggled", self.update)
		clstr_panel.pack_start(self.cb_cluster, expand=False)
		self.spin_cluster = gtk.SpinButton()
		self.spin_cluster.set_range(1, 1) #otherwise, one first use: overlapping calls of update() 
		self.spin_cluster.set_increments(1, 1)
		self.spin_cluster.set_wrap(True)
		self.spin_cluster.connect("value-changed", self.update)
		clstr_panel.pack_start(self.spin_cluster, expand=False)
		panel.pack_start(clstr_panel, expand=False)
		self.cb_intra_cluster = gtk.CheckButton(label="intra-cluster")
		self.cb_intra_cluster.set_active(True)
		self.cb_intra_cluster.connect("toggled", self.update)
		self.cb_intra_cluster.set_sensitive(False)
		panel.pack_start(self.cb_intra_cluster, expand=False)

		#triggers update() - need all widgets instanciated first	
		# expensive plots - disabled be default
		self.cb_refpoints.set_active(False) 
		self.cb_reweighted_hist.set_active(False) 
		
		return(panel)

		
	def begin_session(self):
		self.active = True
		self.cid1 = self.board.canvas.mpl_connect('button_press_event', self.on_click)
		self.cid2 = self.board.canvas.mpl_connect('pick_event', self.on_pick)
		self.board.listeners.append(self.update)
		self.update()
		
	def end_session(self):
		self.active = False
		self.board.canvas.mpl_disconnect(self.cid1)
		self.board.canvas.mpl_disconnect(self.cid2)
		self.board.listeners.remove(self.update)
		(self.cid1, self.cid2) = (None, None)
	
	#---------------------------------------------------------------------------
	def on_pick(self, event):
		i = int(event.artist.get_text())
		self.board.selected_node = self.board.pool[i]
		self.board.fire_listeners()
	
	def on_click(self, event):
		i = self.board.selected_coord.index
		if(event.button == 2):
			i += 1
		elif(event.button == 3):
			i -= 1
		else:
			return
		conv = self.board.pool.converter 
		i %= len(conv)
		self.board.selected_coord = conv[i]
		self.board.fire_listeners()

	
	#---------------------------------------------------------------------------
	def update(self, dummy=None):
		if(not self.active):
			return
		self.spin_cluster.set_sensitive(False)
		if(not self.board.selected_coord or not self.board.selected_node):
			return
		
		current_coord = self.board.selected_coord
		#throwing away all axes (might me two because of twiny)
		#But otherwise e.g. autoscaling behaves strange when twinx are added and removed
		self.board.canvas.figure.clear()  
		axes1 = self.board.canvas.figure.gca() # create new axes
		axes1.grid()
		axes1.set_ylabel('Probability')
		parent_name = "n/a"
		if self.board.selected_node.parent:
			parent_name = self.board.selected_node.parent.name
		if(self.board.cb_show_title.get_active()):
			axes1.set_title( "%s : %s (parent: %s)"%(self.board.selected_node.name, current_coord.label, parent_name) )
		axes1.set_autoscalex_on(False)
		axes1.set_ylim(0, 1)
		axes1.set_autoscaley_on(False)
		
		axes1.set_xlabel(current_coord.plot_label)
		scale = current_coord.plot_scale
						
		xvalues = self.board.pool.coord_range(current_coord)
		(lower, upper) = (min(xvalues), max(xvalues))

		axes1.set_xlim( scale(lower), scale(upper) )
		axes2 = axes1.twinx()
		axes2.set_zorder(axes1.get_zorder() + 1) #axes2 should receive the pick_events
		#axes1.patch.set_visible(False) # hide the 'canvas' - makes axes2 visible
		axes2.set_autoscalex_on(False)
		axes2.set_autoscaley_on(True)
		axes2.set_ylabel('Energy')

		if(self.board.cb_show_colors.get_active()):
			plotargs_nodemarker = { 'bbox' : {'facecolor':'red'} }
			plotargs_childmarker = { 'bbox' : {'facecolor':'green'} }
			plotargs_sampling = {'facecolor':'blue'}
			plotargs_parent = {'facecolor':'red', 'alpha':0.1}
			plotargs_restraint = {'linewidth':2, 'color':'red'}
			plotargs_phi = {'linewidth':2, 'color':'magenta', 'linestyle':'--'}
			plotargs_phipotential = {'linewidth':2, 'color':'dimgrey', 'linestyle':'-'}
			plotargs_cluster = {'facecolor':'red', 'label':'cluster', 'alpha':0.8}
			plotargs_refpoints = {'facecolor':'orange', 'label':'refpoints', 'alpha':0.7}
			plotargs_direct = {'facecolor':'limegreen'}
			plotargs_corrected = {'facecolor':'lightskyblue'}
		else:		
			plotargs_nodemarker = { 'bbox' : {'facecolor':'white'} }
			plotargs_childmarker = { 'bbox' : {'facecolor':'lightgrey'} }
			plotargs_sampling = {'facecolor':'grey'}
			plotargs_parent = {'facecolor':'grey', 'alpha':0.2}
			plotargs_restraint = {'linewidth':4, 'color':'black'}
			plotargs_phi = {'linewidth':4, 'color':'dimgrey', 'linestyle':'--'}
			plotargs_phipotential = {'linewidth':4, 'color':'black', 'linestyle':'--'}
			plotargs_cluster = {'facecolor':'lightgrey', 'label':'cluster', 'alpha':1.0}
			plotargs_refpoints = {'facecolor':'black', 'label':'refpoints', 'alpha':0.8}
			plotargs_direct = {'facecolor':'white'}
			plotargs_corrected = {'facecolor':'black'}

		# NodeMarker
		children = self.board.selected_node.children
		for n in reversed(self.board.pool):
			if(n == self.board.pool.root):
				continue
			label_pos = scale( n.internals.getcoord(current_coord) )
			text = str(self.board.pool.index(n))
			if(self.cb_marker.get_active() and n==self.board.selected_node):
				axes2.text(label_pos, 0.0, text, picker=5, **plotargs_nodemarker)
			elif(self.cb_child_markers.get_active() and (n in children)):
				axes2.text(label_pos, 0.0, text, picker=5, **plotargs_childmarker)

		# Histogram Plot
		for n in self.board.pool:
			if(self.cb_sampling.get_active() and n==self.board.selected_node):
				plotargs = {'label':'sampling'}
				plotargs.update(plotargs_sampling)
			elif(self.cb_parent_sampling.get_active() and n==self.board.selected_node.parent):
				plotargs = {'label':'parent sampling'}
				plotargs.update(plotargs_parent)
			else:
				continue
			if(not n.has_trajectory): continue
			#not using plt.hist() - it's doesn't allow scaling y-axis to 0..1
			samples = scale(n.trajectory.getcoord(current_coord))
			edges = scale(np.linspace(np.min(xvalues), np.max(xvalues), num=50))
			weights = None
			if(self.cb_use_frameweights.get_active() and n.has_internals and n.has_restraints):
				weights = n.frameweights
			hist = np.histogram(samples, bins=edges, weights=weights)[0]
			height = hist.astype('float') / np.max(hist)
			width = np.diff(edges)
			left = edges[:-1]
			axes1.bar(left, height, width, **plotargs)
			
		# Restraint-, Phi- and Phi-Potential Plot
		for n in self.board.pool.where("state != 'refined'"):
			if(n != self.board.selected_node): continue
			#node_value = n.internals.getcoord(current_coord)
			if(self.cb_restraint.get_active()):
				restraint = n.restraints[current_coord.index]
				penalties = restraint.energy(xvalues)
				axes2.plot(scale(xvalues), penalties, label="restraint", **plotargs_restraint)
			if(self.cb_phi.get_active()):
				yvalues = get_phi_contrib(xvalues, n, current_coord)	
				axes1.plot(scale(xvalues), yvalues, label='phi', **plotargs_phi)
			if(self.cb_phi_potential.get_active()):
				yvalues = get_phi_contrib_potential(xvalues, n, current_coord)
				axes2.plot(scale(xvalues), yvalues, label="phi potential", **plotargs_phipotential)
		
		# WeightedSamplingHistogram
		if(self.cb_reweighted_hist.get_active()):
			for rb in [self.rb_show_both, self.rb_show_direct, self.rb_show_corrected]:
				rb.set_sensitive(True)
			edges = scale(np.linspace(np.min(xvalues), np.max(xvalues), num=50))
			hist_direct = np.zeros(edges.size-1)
			hist_corr = np.zeros(edges.size-1)
			for n in self.board.pool.where("'weight_direct' in obs or 'weight_corrected' in obs"):
				samples = scale( n.trajectory.getcoord(current_coord) )
				hist_node = np.histogram(samples, bins=edges, weights=n.frameweights, normed=True)[0]
				if('weight_direct' in n.obs):
					hist_direct += n.obs.weight_direct * hist_node
				if('weight_corrected' in n.obs):
					hist_corr += n.obs.weight_corrected * hist_node
			width = np.diff(edges)
			left = edges[:-1]
			if(np.max(hist_direct) > 0 and not self.rb_show_corrected.get_active()):
				height_direct = hist_direct.astype('float') / np.max(hist_direct)
				axes1.bar(left, height_direct, width/2, label="weighted direct", **plotargs_direct)
			if(np.max(hist_corr) > 0 and not self.rb_show_direct.get_active()):
				height_corr = hist_corr.astype('float') / np.max(hist_corr)
				axes1.bar(left+width/2, height_corr, width/2, label="weighted corrected", **plotargs_corrected)
		else:
			for rb in [self.rb_show_both, self.rb_show_direct, self.rb_show_corrected]:
				rb.set_sensitive(False)

		# ClusterHistogram
		if(self.cb_cluster.get_active()):
			self.cb_intra_cluster.set_sensitive(True)
			if(os.path.exists(self.board.pool.chi_mat_fn)):
				chi_threshold = 1E-3
				npz_file = np.load(self.board.pool.chi_mat_fn)
				chi_mat = npz_file['matrix']
				node_names = npz_file['node_names']
				n_clusters = chi_mat.shape[1]
				self.spin_cluster.set_sensitive(True)
				self.spin_cluster.set_range(1, n_clusters)
				i = int(self.spin_cluster.get_value())
				
				# presort to make (intra-cluster) plot faster
				relevant_nodes = node_names[np.argwhere(chi_mat[:,i-1] > chi_threshold)]

				edges = scale(np.linspace(np.min(xvalues), np.max(xvalues), num=50))
				hist_cluster = np.zeros(edges.size-1)
				hist_all = np.zeros(edges.size-1)
				for (n, chi) in zip([n for n in self.board.pool if n.name in node_names], chi_mat[:,i-1]):
					if n.name not in relevant_nodes:
						if self.cb_intra_cluster.get_active():
							continue
						else:
							samples = scale( n.trajectory.getcoord(current_coord) )
							hist_node = np.histogram(samples, bins=edges, weights=n.frameweights, normed=True)[0]
							hist_all += n.obs.weight_corrected * hist_node
					else:
						samples = scale( n.trajectory.getcoord(current_coord) )
						hist_node = np.histogram(samples, bins=edges, weights=n.frameweights, normed=True)[0]
						hist_all += n.obs.weight_corrected * hist_node
						hist_cluster += n.obs.weight_corrected * hist_node * chi
					
				if self.cb_intra_cluster.get_active():
					hist_all = hist_cluster

				width = np.diff(edges)
				left = edges[:-1]
				if(np.max(hist_cluster) > 0):
					height_cluster = hist_cluster.astype('float') / np.max(hist_all)
				axes1.bar(left, height_cluster, width, **plotargs_cluster)

				max_val = scale(np.linspace(np.min(xvalues), np.max(xvalues), num=50))[np.argmax(hist_cluster)]		
				axes1.text(axes1.get_xlim()[0], -0.1, "max=%.4f"%max_val, ha='left', bbox=dict(boxstyle="round", fc="1.0"))
				axes1.text(axes1.get_xlim()[0], 1.05, "#involved nodes=%d"%len(relevant_nodes), ha='left', bbox=dict(boxstyle="round", fc="1.0"))
				weight = np.load(self.board.pool.qc_mat_fn)["weights"][i-1]
				axes1.text(axes1.get_xlim()[1], -0.1, "weight=%.4f"%weight, ha='right', bbox=dict(boxstyle="round", fc="1.0"))
		else:
			self.cb_intra_cluster.set_sensitive(False)
	
		# RefpointsHistogram
		if(self.cb_refpoints.get_active()):
			if('refpoints' in self.board.selected_node.obs):
				edges = scale(np.linspace(np.min(xvalues), np.max(xvalues), num=50))
				refternals = self.board.selected_node.trajectory.getframes(self.board.selected_node.obs['refpoints'])
				hist = np.histogram(scale(refternals.getcoord(current_coord)), bins=edges, weights=None)[0]
				height = hist.astype('float') / np.max(hist)
				width = np.diff(edges)
				left = edges[:-1]
				n_ref = len(self.board.selected_node.obs['refpoints'])
				n_steps = len(self.board.selected_node.trajectory)
				axes1.bar(left, height, width, **plotargs_refpoints)
				axes1.text(axes1.get_xlim()[1], -0.1, "ratio=%d/%d=%.2f"%(n_ref, n_steps, float(n_ref)/float(n_steps)), ha='right', bbox=dict(boxstyle="round", fc="1.0"))

		# update legend
		if(self.board.cb_show_legend.get_active()):
			handles = axes2.get_legend_handles_labels()[0] + axes1.get_legend_handles_labels()[0] 
			labels = axes2.get_legend_handles_labels()[1] + axes1.get_legend_handles_labels()[1]
			if(len(handles) > 0):
				self.board.canvas.figure.legend(handles, labels)
		
		# redraw
		self.board.canvas.draw_idle()


#===============================================================================
#EOF
