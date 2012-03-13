# -*- coding: utf-8 -*-

import gtk
import numpy as np

#===============================================================================
class NodeWeightPlotManager(object):
	#pylint: disable=E1101, W0201
	#..., because members are also defined in get_ctrl_panel and in a dynamic way.
	#TODO: maybe create ctrl_panel within __init__
	
	def __init__(self, board):
		self.name = "NodeWeights"
		self.board = board
		self.sortkey = 30
		
	def get_ctrl_panel(self):
		panel = gtk.VBox()
		rb = None
		for x in ("mean_potential", "free_energy"):
			rb =  gtk.RadioButton(group=rb, label=x.replace("_"," "))
			setattr(self, "rb_set_"+x, rb)
			rb.connect("toggled", self.update)
			panel.pack_start(rb, expand=False)

		panel.pack_start(gtk.Label("weight threshold:"), expand=False)
		rb = None
		for x in ("direct", "corrected"):
			rb =  gtk.RadioButton(group=rb, label=x)
			setattr(self, "rb_set_"+x, rb)
			rb.connect("toggled", self.update)
			panel.pack_start(rb, expand=False)
		
		self.cobo_threshold = gtk.combo_box_new_text()
		for v in ("all", "top 100", "top 50", "top 10", "top 3"):
			self.cobo_threshold.append_text(v)
		self.cobo_threshold.set_active(0)
		self.cobo_threshold.connect('changed', self.update)
		panel.pack_start(self.cobo_threshold, expand=False)

		panel.pack_start(gtk.Label("show weights:"), expand=False)
		weight_panel = gtk.VBox()
		rb = None                                                     
		for x in ("both", "direct", "corrected"):
			rb = gtk.RadioButton(group=rb, label=x.replace("_"," "))
			setattr(self, "rb_show_"+x, rb)
			rb.connect("toggled", self.update)
			weight_panel.pack_start(rb, expand=False)
		panel.pack_start(weight_panel, expand=False)
		
		return(panel)

	def begin_session(self):
		self.board.listeners.append(self.update)
		self.update()

	def end_session(self):
		self.board.listeners.remove(self.update)
		
	#---------------------------------------------------------------------------
	def update(self, dummy=None):
		self.board.canvas.figure.clear()
		nodes = self.board.pool.where("'weight_direct' in obs or 'weight_corrected' in obs")
		
		# filter nodes according to self.rb_set_direct and self.cobo_threshold   
		if(self.cobo_threshold.get_active_text() != "all"):
			if(self.rb_set_direct.get_active()):
				nodes = nodes.where("'weight_direct' in obs")
				weights = [ n.obs.weight_direct for n in nodes ]
			else:
				nodes = nodes.where("'weight_corrected' in obs")
				weights = [ n.obs.weight_corrected for n in nodes ]
			ntop = int(self.cobo_threshold.get_active_text()[4:])
			if(len(nodes) > ntop):
				threshold = sorted(weights, reverse=True)[ntop]
				nodes = [n for (n,w) in zip(nodes,weights) if w > threshold]

		if(len(nodes) == 0):
			self.board.canvas.draw_idle()
			return

		# assigns text-labels showing the hight of each bar
		def autolabel(rects, target_axes, color='black'): # attach some text labels		
			for rect in rects:
				height = rect.get_height()
				target_axes.text(rect.get_x()+rect.get_width()/2., 1.01*height, '%.2f'%height, ha='center', va='bottom', color=color)
				
		# prepare axes
		ax1 = self.board.canvas.figure.gca() # create new axes
		if(self.board.cb_show_title.get_active()):
			ax1.set_title("Node weights and averages")
		ax1.set_ylabel('Energy [kJ/mol]')
		ax1.set_xlabel('Node')
		ax1.set_xlim(0, len(nodes))
		ax2 = ax1.twinx() # create twin axes		
		ax2.set_ylim(0, 1)
		ax2.set_ylabel('Weight')
		ax2.grid()
		width = 0.4 # width of the bars
		ind = np.arange(len(nodes))+width # x-locations for the groups
		ax1.set_autoscalex_on(False)
		ax1.set_autoscaley_on(True)
		ax2.set_autoscalex_on(False)
		ax2.set_autoscaley_on(False)
		
		# plot energies		
		obs_std_V = np.array([ n.obs.std_V for n in nodes ])
		if(self.rb_set_mean_potential.get_active()):
			obs_mean_V = np.array([ n.obs.mean_V for n in nodes ])
			rects1 = ax1.bar(ind, obs_mean_V, width, color='lightgrey', yerr=obs_std_V, label='Mean potential')
		elif(self.rb_set_free_energy.get_active()):
			obs_A = np.array([ n.obs.A for n in nodes ])
			rects1 = ax1.bar(ind, obs_A, width, color='grey', label='Free energy')			
			obs_TdeltaS = self.board.pool.temperature*np.array([ n.obs.S for n in nodes ])
			ax1.bar(ind, obs_TdeltaS, width, color='yellow', label='Entropy') # =rects2
		autolabel(rects1, ax1)
						
		# plot weights
		bars_direct = np.array([ (i, n.obs.weight_direct) for (i, n) in enumerate(nodes) if 'weight_direct' in n.obs ])
		bars_corr   = np.array([ (i, n.obs.weight_corrected) for (i, n) in enumerate(nodes) if 'weight_corrected' in n.obs ])
		if(self.rb_show_both.get_active()):
			rect3a = ax2.bar(bars_direct[:,0], bars_direct[:,1], width/2, color='limegreen', label='Weight direct')
			autolabel(rect3a, ax2, 'black')
			if(bars_corr.size > 0):
				rect3b = ax2.bar(bars_corr[:,0]+width/2, bars_corr[:,1], width/2, color='lightskyblue', label='Weight corrected')
				autolabel(rect3b, ax2, 'black')
		elif(self.rb_show_direct.get_active()):
			rect3 = ax2.bar(bars_direct[:,0], bars_direct[:,1], width, color='limegreen', label='Weight direct')
			autolabel(rect3, ax2, 'black')
		elif(self.rb_show_corrected.get_active()):
			if(bars_corr.size > 0):
				rect3 = ax2.bar(bars_corr[:,0], bars_corr[:,1], width, color='lightskyblue', label='Weight corrected')
				autolabel(rect3, ax2, 'black')
	
		# build legend
		if(self.board.cb_show_legend.get_active()):
			handles = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0] 
			labels = ax1.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
			if(len(handles) > 0):
				self.board.canvas.figure.legend(handles, labels)
			
		# assign tick-labels
		ax1.set_xticks(ind)
		ax1.set_xticklabels([ int(n.name.replace("node","")) for n in nodes ])
				
		# redraw
		self.board.canvas.draw_idle()

#===============================================================================
#EOF
