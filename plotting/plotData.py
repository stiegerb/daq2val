#! /usr/bin/env python
import sys, os
import re

from os import path

sys.path.insert(0,path.abspath(path.join(
	                       path.dirname(path.realpath(__file__)),
	                       '../daq2Control')))

months_toint = {"Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6,
                "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12}
months_tostr = {1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"May", 6:"Jun",
                7:"Jul", 8:"Aug", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dec"}

##---------------------------------------------------------------------------------
## Utilities
def extractConfig(filename):
	builder = ''
	protocol = ''
	config = ''
	rms = None
	with open(filename, 'r') as f:
		rms_regex = re.compile("## useLogNormal = (\w*), RMS =\s*([\d.]*)$")
		config_regex = re.compile("## (\w*) configuration with (\w*)/(\w*)$")

		found = 0
		for line in f:
			stripped = line.strip()
			if found > 1: break

			r = rms_regex.match(stripped)
			if r is not None:
				rms = float(r.groups()[1])
				found += 1

			r = config_regex.match(stripped)
			if r is not None:
				config, builder, protocol = r.groups()
				found += 1

		if rms == None:
			rms = 0.0
	return config, builder, protocol, rms
def getConfig(string):
	"""Extract number of streams, readout units, builder units, and number of streams
	per frl from strings such as 8x1x2 or 16s8fx2x4 (i.e 8,1,2,0 in the first case,
	16,2,4,2 in the second)
	"""
	string = string.split('_')
	case = string[0].split('x')
	nstreams = 0
	strperfrl = 0

	if len(case) == 2:
		nstreams = 1
		nrus = int(case[0])
		nbus = int(case[1])
	elif len(case) > 2:
		strperfrl = 1
		pattern = re.compile(r'([0-9]+)s([0-9]+)f')
		if pattern.match(case[0]):
			nstreams = int(pattern.match(case[0]).group(1))
			if nstreams > int(pattern.match(case[0]).group(2)): strperfrl = 2

		else: nstreams = int(case[0])
		nrus = int(case[1]) ## Introduces notation: no _ before the trailing tags
		nbus = int(case[2])

	return nstreams, nrus, nbus, strperfrl
def extractDate(filename):
	with open(filename, 'r') as f:
		for line in f:
			if line.startswith('## Testcase:'): continue
			if line.startswith('## useLogNormal'): continue
			if len(line.split(' ')) == 0: return (0,0,0)
			data = line.split(' ')
			if data[0] != '##': continue
			mon, day, year = (data[2],data[3][:-1],data[4])
			return day, mon, year
			# return int(day), int(months_toint[mon]), int(year)
		return (0,0,0)
def getRateGraph(nStreams=4, frag=False, xmax=100000, rate=100):
	'''Returns a TF1 object corresponding to the average throughput at the RU
	necessary for a 100kHz rate of events of a given (super)fragment size '''
	from ROOT import TF1
	rate *= 0.001 ## convert from kHz to MHz
	if frag: rate *= nStreams
	f = TF1("Const Rate", "%f*x"%rate, 0, xmax)
	f.SetLineWidth(1)
	f.SetLineColor(1)
	f.SetLineStyle(2)
	return f
def drawDate(filename):
	from ROOT import TPaveText
	day,month,year = extractDate(filename)

	date_string = "%s %s %s" % (day, month, year)
	pave = TPaveText(0.005, 0.005, 0.1, 0.02, 'NDC')
	pave.SetTextFont(42)
	pave.SetTextSize(0.03)
	pave.SetFillStyle(1001)
	pave.SetFillColor(0)
	pave.SetBorderSize(0)
	pave.SetTextAlign(12)
	pave.AddText(date_string)
	return pave

##---------------------------------------------------------------------------------
## daq2Plotter Class
##---------------------------------------------------------------------------------
class daq2Plotter(object):
	"""docstring for daq2Plotter"""
	def __init__(self, filelist, args):
		self.args = args
		self.filelist = filelist
		self.startfragsize = 256
		self.makePNGs = True

	def processFile(self, filename):
		from numpy import mean, std
		# from logNormalTest import averageFractionSize
		###########################
		## Process .csv file
		f = open(filename,'r')
		if not f: raise RuntimeError, "Cannot open "+filename+"\n"

		data_dict = {} ## Store everything in this dictionary of size -> rate
		for line in f:
			if len(line.strip()) == 0 or line.strip()[0] == '#': continue

			try:
				# sizeru, sizebu: rate1, rate2, rate3, ...
				header, body = line.split(':')
				size, size_bu = tuple([int(_) for _ in header.split(',')])
				if self.args.sizeFromBU: size = size_bu
			except ValueError:
				# size, rate1, rate2, rate3, ...
				line = line.split(',',1)
				size = int(line[0])
				body = line[1]

			# Skip empty lines
			if body == '\n': continue

			rate = [int(float(_)) for _ in body.split(',')]

			if size not in data_dict.keys(): ## First time seeing this size
				data_dict[size] = rate
			else: ## Have already a line with this size
				prev_rate = data_dict[size]

				## Fix different sample sizes:
				if len(rate) > len(prev_rate):
					rate = rate[:len(prev_rate)]
				if len(rate) < len(prev_rate):
					prev_rate = prev_rate[:len(rate)]
				## Add to the previous samples
				data_dict[size] = map(lambda a,b:a+b, prev_rate, rate)
		f.close()
		return data_dict
	def getData(self, filename):
		data_dict = self.processFile(filename)
		from numpy import mean, std
		from logNormalTest import averageFractionSize
		config, builder, protocol, rms = extractConfig(filename)
		nstreams, nrus, nbus, strperfrl = getConfig(config)

		## Check if this is with inputemulator or mstreamio
		## or with FRL input
		isNxN = True if len(config.split('x')) < 3 else False
		## I.e. True means there are only RUs and BUs, False
		## means there are FRLs, RUs, and BUs

		###########################
		## Calculate throughput

		# In case of mstreamio, divide the rates by the number of RUs
		# (But don't do this for the case of nx1, want to plot throughput
		#  per BU in that case.)
		if isNxN:
			if nbus>1:
				if builder == 'mstreamio':
					## For msio, rate is the rate of fragments received, so
					## have to divide by number of clients (senders)
					for size in data_dict.keys():
						newrate = [a/nrus for a in data_dict[size]]
						data_dict[size] = newrate
				else:
					## For gevb2g rate is rate of events built in each BU,
					## but we added them up before, so we have to divide now
					for size in data_dict.keys():
						newrate = [a/nbus for a in data_dict[size]]
						data_dict[size] = newrate

			## IGNORE number of RUs now:
			if builder == 'mstreamio':
				nrus = 1

		# LOWERLIMIT=32
		LOWERLIMIT=24
		UPPERLIMIT=65000
		# UPPERLIMIT=16000
		# if nstreams/nrus==4:  UPPERLIMIT = 64000 ## This is only true for eFEROLs!
		# if nstreams/nrus==8:  UPPERLIMIT = 32000
		# if nstreams/nrus==12: UPPERLIMIT = 21000
		# if nstreams/nrus==16: UPPERLIMIT = 16000
		# if nstreams/nrus==24: UPPERLIMIT = 10000

		data = []

		output_case = 0 ## 0 (fragsize), 1 (superfragsize), 2 (eventsize)
		checked = False

		for size in sorted(data_dict.keys()):
			## Skip empty lines
			if (abs(mean(data_dict[size])) < 0.01 and
			         abs(std(data_dict[size])) < 0.01):
			    continue

			## Determine what the first item in the server.csv file stands for
			if not checked: ## only do this for the first time
				checked = True
				if int(size)//self.startfragsize == 1:
					output_case = 0 ## size = fragment size
				elif int(size)//self.startfragsize == nstreams/nrus:
					output_case = 1 ## size = superfragment size
				elif int(size)//self.startfragsize == nstreams:
					output_case = 2 ## size = event size
				else:
				    output_case = 1 ## default
				if isNxN:
					output_case = 0

			## Extract event size
			eventsize = float(size)*nstreams ## default (output_case == 0)
			if output_case == 1:
				eventsize = float(size)*nrus
			if output_case == 2:
				eventsize = float(size)

			## Calculate fragment and super fragment sizes
			if isNxN:
				if builder == 'mstreamio':
					eventsize = float(size)
					fragsize    = eventsize
					sufragsize  = eventsize
				if builder == 'gevb2g':
					fragsize = float(size)
					sufragsize = nrus*fragsize
				if builder == 'EvB':
					fragsize = float(size)
					sufragsize = nrus*fragsize
			else:
				fragsize    = eventsize/nstreams
				sufragsize  = eventsize/nrus
				if args.correctForEVM:
					sufragsize = (eventsize-1024)/(nrus-1)


			## Correct for RMS:
			if not self.args.sizeFromBU and rms is not None and rms != 0.0:
				fragsize = averageFractionSize(eventsize/nstreams, rms*eventsize/nstreams, LOWERLIMIT, UPPERLIMIT)
				sufragsize = fragsize*nstreams/nrus

			## Calculate rate
			# throughput  = mean(data_dict[size]) ## in MB/s
			# throughputE = std(data_dict[size])
			avrate      = mean(data_dict[size])
			stdrate     = std(data_dict[size])
			throughput  = sufragsize*avrate/1e6 ## in MB/s
			throughputE = sufragsize*stdrate/1e6

			data.append((fragsize, throughput, throughputE))

		return data

	##---------------------------------------------------------------------------------
	## Plotting and printing
	def printTables(self):
		for filename in self.filelist:
			self.printTable(filename)
	def printTable(self, filename):
		config, builder, protocol, rms = extractConfig(filename)
		nstreams, nrus, nbus, strperfrl = getConfig(config)
		data = self.getData(filename)
		print "--------------------------------------------------------------------------------------"
		print "Case: %s (%s/%s, RMS=%4.2f)" % (config, builder, protocol, rms)
		print "--------------------------------------------------------------------------------------"
		print "Superfrag. Size (B) : Fragment Size (B) : Av. Throughput (MB/s) :       Av. Rate     :"
		print "--------------------------------------------------------------------------------------"
		for	fragsize,tp,tpE in data:
			if strperfrl == 0:
				sufragsize = fragsize
			else:
				sufragsize = fragsize*nstreams/nrus
			print ("             %6d :            %6d :      %6.1f +- %6.1f :  %8.1f +- %6.1f" %
			       (sufragsize, fragsize, tp, tpE, tp*1e6/sufragsize, tpE*1e6/sufragsize))

		print "--------------------------------------------------------------------------------------"
	def makeMultiPlot(self):
		from ROOT import gROOT, gStyle, TFile, TTree, gDirectory
		from ROOT import TGraphErrors, TCanvas, TLegend, TH2D, TLatex, TPave
		from operator import itemgetter

		rangey=(self.args.miny, self.args.maxy)
		rangex=(self.args.minx, self.args.maxx)

		## Build caselist
		caselist = []
		for filename in self.filelist:
			caselist.append(path.dirname(filename).split('/')[-1])

		gROOT.SetBatch()
		gStyle.SetOptTitle(0)
		gStyle.SetOptStat(0)

		oname = self.args.outputName
		if oname.endswith('.pdf') or oname.endswith('.png'): oname = oname[:-4]
		if len(oname)==0: ## default
			oname = 'plot_' + reduce(lambda x,y:x+'_'+y, caselist)

		canv = TCanvas(oname, "Plot", 0, 0, 1024, 768)
		canv.cd()
		if not self.args.nologx: canv.SetLogx()
		if self.args.logy: canv.SetLogy()
		canv.SetGridx()
		canv.SetGridy()
		## Cosmetics
		# canv.DrawFrame(rangex[0], rangey[0], rangex[1], rangey[1])
		axes = TH2D('axes', 'A', 100, rangex[0], rangex[1], 100, rangey[0], rangey[1])
		title = args.title if len(args.title) else 'Throughput vs. Fragment Size'
		titleX = args.titleX if len(args.titleX) else 'Fragment Size (bytes)'
		titleY = args.titleY if len(args.titleY) else 'Av. Throughput per RU (MB/s)'
		axes.GetYaxis().SetTitle(titleY)
		axes.GetYaxis().SetTitleOffset(1.4)
		axes.GetXaxis().SetTitleOffset(1.2)
		axes.SetTitle(title)
		axes.GetXaxis().SetTitle(titleX)
		axes.GetXaxis().SetMoreLogLabels()
		axes.GetXaxis().SetNoExponent()
		axes.Draw()

		tl = TLatex()
		tl.SetTextFont(42)
		tl.SetNDC(1)
		if len(self.args.tag) > 0:
			width = 0.12+0.020*len(self.args.tag)
			if width > 0.9: width=0.899
			pave = TPave(0.12, 0.80, width, 0.899, 0, 'NDC')
			pave.SetFillStyle(1001)
			pave.SetFillColor(0)
			pave.Draw()
		if len(self.args.subtag) > 0:
			width2 = 0.12+0.015*len(self.args.subtag)
			if width2 > 0.9: width2=0.899
			pave2 = TPave(0.12, 0.75, width2, 0.899, 0, 'NDC')
			pave2.SetFillStyle(1001)
			pave2.SetFillColor(0)
			pave2.Draw()
		if len(self.args.tag) > 0:
			tl.SetTextSize(0.05)
			tl.DrawLatex(0.14, 0.83, self.args.tag)
		if len(self.args.subtag) > 0:
			tl.SetTextSize(0.035)
			tl.DrawLatex(0.145, 0.77, self.args.subtag)

		graphs = []
		configs = set()
		for filename,case in zip(self.filelist,caselist):
			try:
				graphs.append(self.getGraph(filename))

				config, builder, protocol, rms = extractConfig(filename)
				nstreams, nrus, nbus, strperfrl = getConfig(config)

				if strperfrl == 0:
					nrus = 1 ## ignore number of RUs if MSIO
					configs.add(nrus)
				else:
					configs.add(nstreams//nrus) ## care only about Nstreams per RU
			except AttributeError:
				print "#### Couldn't get graph for ", case, "in file", filename
				return

		if not self.args.hideDate:
			datepave = drawDate(self.filelist[0])
			datepave.Draw()

		# if self.args.daq1:
		# 	daq1_graph = getDAQ1Graph()

		configs = sorted(configs)
		nlegentries = len(self.filelist)
		# nlegentries = len(caselist) if not self.args.daq1 else len(caselist) + 1
		legendpos = (0.44, 0.13, 0.899, 0.20+nlegentries*0.05)
		if strperfrl == 0:
			legendpos = (0.13, 0.73, 0.31, 0.73-nlegentries*0.045)
		# if self.args.legendPos == 'TL':
		# 	legendpos = (0.12, 0.82-nlegentries*0.05, 0.579, 0.898)
		# 	# legendpos = (0.12, 0.71-nlegentries*0.05, 0.579, 0.78)
		leg = TLegend(legendpos[0], legendpos[1], legendpos[2], legendpos[3])
		leg.SetFillStyle(1001)
		leg.SetFillColor(0)
		leg.SetTextFont(42)
		leg.SetTextSize(0.033)
		leg.SetBorderSize(0)

		colors  = [1,2,3,4,51,95,65,39,32]
		markers = [20,21,22,23,34,33,29,24,25,26]

		if (len(self.args.legends) > 0 and
			len(self.args.legends) != len(self.filelist)):
			print "Legends doesn't match with filelist, falling back to default"

		for n,graph in enumerate(graphs):
			graph.SetLineColor(colors[n])
			graph.SetMarkerColor(colors[n])
			graph.SetMarkerStyle(markers[n])

			 ## Custom legends
			if (len(self.args.legends) == len(self.filelist) and
			    len(self.args.legends)>0):
				leg.AddEntry(graph, self.args.legends[n], 'P')
			else: ## Default
				leg.AddEntry(graph, caselist[n], 'P')
			# if self.args.daq1:
			# 	leg.AddEntry(daq1_graph, 'DAQ1 (2011)', 'P')
			graph.Draw("PL")

		# if self.args.daq1:
		# 	daq1_graph.Draw("PL")

		if not self.args.noRateLine:
			for n,streams_per_ru in enumerate(configs):
				func = getRateGraph(streams_per_ru, frag=True,
					                rate=self.args.rate, xmax=rangex[1])
				func.SetLineColor(colors[n])
				func.SetLineWidth(1)
				func.DrawCopy("same")
				if not strperfrl == 0:
					leg.AddEntry(func, '%.0f kHz (%d streams)'%
						                 (self.args.rate, streams_per_ru), 'l')
				else:
					leg.AddEntry(func, '%.0f kHz'% (self.args.rate), 'l')

		leg.Draw()

		## Draw CMS Prelim
		pave = TPave(0.62, 0.80, 0.899, 0.899, 0, 'NDC')
		pave.SetFillStyle(1001)
		pave.SetFillColor(0)
		pave.Draw()
		tl.SetTextFont(62)
		tl.SetTextSize(0.05)
		tl.DrawLatex(0.625, 0.83, "CMS")
		tl.SetTextFont(52)
		tl.DrawLatex(0.71, 0.83, "Preliminary")


		for graph in graphs:
			graph.Draw("PL")

		canv.Print(oname + '.pdf')
		canv.Print(oname + '.png')
		# if self.makePNGs:  canv.Print(oname + '.png')
		# if self.args.makeCFile: canv.SaveAs(oname + '.C')
	def getGraph(self, filename):
		data = self.getData(filename)

		from ROOT import TFile, TTree, gDirectory, TGraphErrors, TCanvas
		from array import array

		nsteps = len(data)
		g = TGraphErrors(nsteps)

		## Loop on the data
		for	n,(fragsize,tp,tpE) in enumerate(data):
			g.SetPoint(      n, fragsize, tp)
			g.SetPointError( n,       0., tpE)

		g.SetLineWidth(2)
		g.SetMarkerSize(1.7)

		return g

##---------------------------------------------------------------------------------
## User interface
def addPlottingOptions(parser):
	parser.add_argument("-o", "--outputName", default="plot.pdf", action="store",
		                type=str, dest="outputName",
		                help="File for plot output [default: %(default)s]")
	parser.add_argument("-t", "--tag", default="", action="store", type=str,
		                dest="tag", help="Title tag in plot canvas")
	parser.add_argument("-t2", "--subtag", default="", action="store", type=str,
		                dest="subtag", help="Subtitle tag in plot canvas")
	parser.add_argument("-tt", "--title", default="", action="store", type=str,
		                dest="title", help="Canvas title")
	parser.add_argument("-xt", "--titleX", default="", action="store", type=str,
		                dest="titleX", help="X axis title")
	parser.add_argument("-yt", "--titleY", default="", action="store", type=str,
		                dest="titleY", help="Y axis title")
	parser.add_argument('--legend', default=[], action="append", type=str,
		                dest="legend", nargs='*',
		                help='Give a list of custom legend entries to be used')
	parser.add_argument("--hideDate", default=False, action="store_true",
		                dest="hideDate", help="Hide date.")
	parser.add_argument("-r", "--rate", default="100", action="store", type=float,
		                dest="rate",
		                help="Rate in kHz to be displayed on the plot:\
		                     [default: %(default)s kHz]")
	parser.add_argument("--noRateLine", default=False, action="store_true",
		                dest="noRateLine", help="Do not draw the rate line")
	parser.add_argument("-q", "--quiet", default=False, action="store_true",
		                dest="quiet", help="Do not print the tables")
	parser.add_argument("--sizeFromBU", default=False, action="store_true",
		                dest="sizeFromBU", help="Take size from BU measurement")
	parser.add_argument("--correctForEVM", default=False, action="store_true",
		                dest="correctForEVM",
		                help=("Assume one RU only has one fragment with 1kB size"
		                      " and correct the throughput to show the other RUs"))

	parser.add_argument("--miny", default="0", action="store", type=float,
		                dest="miny", help="Y axis range, minimum")
	parser.add_argument("--maxy", default="5500", action="store", type=float,
		                dest="maxy", help="Y axis range, maximum")
	parser.add_argument("--minx", default="250", action="store", type=float,
		                dest="minx", help="X axis range, minimum")
	parser.add_argument("--maxx", default="17000", action="store", type=float,
		                dest="maxx", help="X axis range, maximum")
	parser.add_argument("--nologx", default=False, action="store_true", dest="nologx",
		                help="Do not use logarithmic scale on x axis")
	parser.add_argument("--logy", default=False, action="store_true", dest="logy",
		                help="Use logarithmic scale on y axis")

	# parser.add_argument("--legendPos", default="BR", action="store", type=str,
	# 	                dest="legendPos",
	# 	                help="Position for legend, either 'TL' (top left), 'TR'\
	# 	                      (top right), 'BL' (bottom left), 'BR'  (bottom right)\
	# 	                      [default: %(default)s]")
	# parser.add_argument("--makePNGs", default=True, action="store_true",
	# 	                dest="makePNGs",
	# 	                help="Produce also .png file")
	# parser.add_argument("--makeCFile", default=True, action="store_true",
	# 	                dest="makeCFile",
	# 	                help="Produce also .C file")
def buildFileList(inputlist):
	filelist = []
	for location in inputlist:
		if path.isfile(location) and path.splitext(location)[1] == '.csv':
			filelist.append(location)
		elif path.isdir(location) and 'server.csv' in os.listdir(location):
			filelist.append(location+'/server.csv')
		else: pass
	if len(filelist) < 1:
		print "No server.csv files found!"
		exit(-1)
	else: return filelist

if __name__ == "__main__":
	usage = """
	Plots event rates in .csv files as throughput per RU vs fragment\
	size.
	Give .csv files or directories containing a 'server.csv' files as\
	input.

	Examples:
	%(prog)s server.csv
	%(prog)s 20s10fx1x4_RMS_0.0/ 20s10fx1x4_FRL_AutoTrigger_RMS_0.0/\
	temp/custom.csv --tag 'FEROLs/EvB 20s10fx1x4' --legend 'FEROL\
	AutoTrigger' 'FRL AutoTrigger' 'Custom'
	"""
	from argparse import ArgumentParser
	parser = ArgumentParser(usage)
	addPlottingOptions(parser)
	parser.add_argument("inputlist", metavar='file_or_dir', type=str,
		                nargs='+',
		                help='The .csv files or directories (containing\
		                	  .csv files) to be plotted.')
	args = parser.parse_args()

	if len(args.inputlist) > 0:
		filelist = buildFileList(args.inputlist)
		d2P = daq2Plotter(filelist, args)
		if not args.quiet:
			d2P.printTables()

		name, ext = os.path.splitext(args.outputName)
		if ext == '': ## no filename given, interpret as directory
			args.outputName = os.path.join(args.outputName, 'plot.pdf')

		os.system('mkdir -p %s' %os.path.dirname(args.outputName))

		args.legends=[]
		if len(args.legend)>0: args.legends=args.legend[0]
		d2P.makeMultiPlot()
		exit(0)

	parser.print_help()
	exit(-1)
