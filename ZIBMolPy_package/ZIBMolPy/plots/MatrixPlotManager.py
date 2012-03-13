# -*- coding: utf-8 -*-

import gtk
import numpy as np
from os import path

#===============================================================================
class MatrixPlotManager(object):
	#pylint: disable=E1101, W0201
	#..., because members are also defined in get_ctrl_panel and in a dynamic way.
	#TODO: maybe create ctrl_panel within __init__
	
	def __init__(self, board):
		self.name = "Matrices"
		self.board = board
		self.sortkey = 50
		
	def get_ctrl_panel(self):
		panel = gtk.VBox()
		rb = None                                                     
		for x in ("s_matrix", "s_matrix_corrected", "k_matrix", "k_matrix_corrected", "chi_matrix", "qc_matrix"):
			rb = gtk.RadioButton(group=rb, label=x.replace("_"," "))
			setattr(self, "rb_show_"+x, rb)
			rb.connect("toggled", self.update)
			panel.pack_start(rb, expand=False)
		return(panel)

	def begin_session(self):
		self.board.listeners.append(self.update)
		self.update()

	def end_session(self):
		self.board.listeners.remove(self.update)

	def update(self, dummy=None):
		self.board.canvas.figure.clear()
		if(self.rb_show_s_matrix.get_active()):
			self.plot_matrix(self.board.pool.s_mat_fn, "S matrix")
		elif(self.rb_show_s_matrix_corrected.get_active()):
			self.plot_matrix(self.board.pool.s_corr_mat_fn, "S matrix (corrected)")
		elif(self.rb_show_k_matrix.get_active()):
			self.plot_matrix(self.board.pool.k_mat_fn, "K matrix")
		elif(self.rb_show_k_matrix_corrected.get_active()):
			self.plot_matrix(self.board.pool.k_corr_mat_fn, "K matrix (corrected)")
		elif(self.rb_show_chi_matrix.get_active()):
			self.plot_matrix(self.board.pool.chi_mat_fn, "Chi matrix")
		elif(self.rb_show_qc_matrix.get_active()):
			self.plot_matrix(self.board.pool.qc_mat_fn, "Qc matrix")
		self.board.canvas.draw_idle()

	def plot_matrix(self, matrix_path, title):
		if(not path.exists(matrix_path)):
			return
		plt = self.board.canvas.figure.add_subplot(111)	
		mat = np.load(matrix_path)
		nodeticklabels = [ int(l.replace("node","")) for l in mat["node_names"] ]
		mat = mat["matrix"]
		plt.matshow(mat)
		plt.set_xticks(np.arange(0, mat.shape[1]))
		plt.set_yticks(np.arange(-1, mat.shape[0]+1))
		n_nodes = len(nodeticklabels)
		if mat.shape[0] == n_nodes:
			plt.set_yticklabels([0]+nodeticklabels)
		if mat.shape[1] == n_nodes:
			plt.set_xticklabels(nodeticklabels)
		if(self.board.cb_show_title.get_active()):
			title += " [%d x %d]"%(mat.shape[0], mat.shape[1])
			plt.set_title(title)


#===============================================================================
#EOF
