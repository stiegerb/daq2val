#! /usr/bin/env python

## TODO:
#  - handling of 'previous' directories?
#  - implement this as a class
#  - fix --makePNGs option
import re
import sys, os

months = {"Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6, "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12}

##---------------------------------------------------------------------------------
## Utilities
def getConfig(string):
	"""Extract number of streams, readout units, builder units, and RMS from strings such as
	8x1x2 or 16s8fx2x4_RMS_0.5 (i.e 8,1,2,None in the first case, 16,2,4,0.5 in the second)
	"""
	string = string.split('_')
	case = string[0].split('x')
	rms = None
	strperfrl = 1
	pattern = re.compile(r'([0-9]+)s([0-9]+)f')
	if pattern.match(case[0]):
		nstreams = int(pattern.match(case[0]).group(1))
		if nstreams > int(pattern.match(case[0]).group(2)): strperfrl = 2

	else: nstreams = int(case[0])
	nrus = int(case[1]) ## Introduces notation: no _ before the trailing tags
	nbus = int(case[2])

	for i in xrange(len(string)):
		if string[i] == 'RMS':
			try:
				rms = float(string[i+1])
			except ValueError, StopIteration:
				print 'RMS needs to be a floating point number'
				rms = None

	return nstreams, nrus, nbus, rms, strperfrl
def fillTreeForDir(treefile, subdir, files):
	if options.verbose > 0: print "  ... processing", subdir
	if not 'server.csv' in files: return

	nstreams, nrus, nbus, rms, strperfrl = getConfig(subdir.split('/').pop())
	if options.verbose > 1:
		feedback = "    with %2s streams, %1d readout units, and %1d builder units." % (nstreams, nrus, nbus)
		if rms is not None: feedback += " RMS is %4.2f" % rms
		print feedback

	fillTree(subdir+'/server.csv', treefile, subdir, nstreams, nbus, nrus, rms, doCleaning=options.doCleaning)
	if options.doCleaning:
		cleanFile(subdir+'/server.csv')

	return None
def processDirs(directory):
	if not os.path.isdir(directory):
		print directory, "is not a directory."
		return

	treefile = directory.strip('/')+'.root'
	if options.outputName != 'plot.pdf':
		treefile = options.outputName

	os.path.walk(directory, fillTreeForDir, treefile)

	return None

##---------------------------------------------------------------------------------
## Cleaning of outliers in a data set
def cleanData(data, step=1, length=4, cutoff=3, quality=0.05):
	from numpy import mean,std,seterr
	# 1. find a stretch of data where the std is less than X% of the mean, store that mean/std
	# 2. loop on the data and replace values more than 10% off with the mean of the clean stretch
	seterr(invalid='raise')
	found_clean_stretch = False

	if mean(data) < 0.01 or std(data)/mean(data) < quality: return data

	pos, stretch = 0, data[:length]
	try:
		# while mean(stretch) == 0 or mean(stretch) > 0 and std(stretch)/mean(stretch) > quality and pos+length < len(data):
		while mean(stretch) == 0 or mean(stretch) > 0 and std(stretch)/mean(stretch) > quality and pos+length < len(data):
			if options.verbose > 4: print stretch
			if options.verbose > 4: print pos, pos+length, std(stretch)/mean(stretch)
			pos += step
			stretch = data[pos:length+pos]
	except FloatingPointError, KeyError:
		# print "Didn't find a clean stretch in:"
		# print data
		return data

	if not std(stretch)/mean(stretch) <= quality: return data

	clean_data = []
	for r in data:
		if abs(r-mean(stretch)) > cutoff*std(stretch):
			clean_data.append(mean(stretch))
		else: clean_data.append(r)

	return clean_data
def metaCleaning(data, maxlength=15, minlength=4, cutoff=3, quality=0.05):
	from numpy import mean,std,seterr

	## Skip empty data:
	if abs(mean(data)) < 0.01 and abs(std(data)) < 0.01: return data

	seterr(invalid='raise')
	length = maxlength

	try:
		while std(data)/mean(data) > quality and length >= minlength:
			data = cleanData(data, step=1, length=length, cutoff=cutoff, quality=quality)
			length -= 1

	except FloatingPointError, KeyError:
		print "Didn't find a clean stretch in:", data
		return data
	return data
def cleanFile(filename):
	with open(filename, 'r') as f, open(filename.replace('.csv','')+'_clean.csv', 'w') as o:
		for line in f:
			if len(line.strip()) == 0 or line.strip()[0] == '#':
				o.write(line)
				continue
			spline = line.strip('\n').split(',')
			data = map(lambda x: int(float(x)), spline[1:])
			o.write(spline[0])
			o.write(',')
			cleandata = metaCleaning(data)
			# cleandata = cleanData(data)
			cleandata = map(int, cleandata)
			newline = reduce(lambda x,y: str(x)+','+str(y), cleandata)
			o.write(newline)
			o.write('\n')
		f.close()
		o.close()
def cleanFilesInDir(subdir):
	if not os.path.isdir(subdir): return
	if not os.path.exists(subdir+'/server.csv'):
		print "  could not locate", directory+subdir+'/server.csv', "... skipping"
		return
	cleanFile(subdir+'/server.csv')

##---------------------------------------------------------------------------------
## Storing information in a ROOT tree for later plotting
##  (this is where the meat is)
def extractDate(filename):
	with open(filename, 'r') as f:
		for line in f:
			if line.startswith('## Testcase:'): continue
			if line.startswith('## useLogNormal'): continue
			if len(line.split(' ')) == 0: return (0,0,0)
			data = line.split(' ')
			if data[0] != '##': continue
			mon, day, year = (data[2],data[3][:-1],data[4])
			return int(day), int(months[mon]), int(year)
		return (0,0,0)
def fillTree(filename, treefile, dirname, nStreams, nBus, nRus, rms=0, startfragsize=256, doCleaning=False):
	from ROOT import TFile, TTree, gDirectory, TGraphErrors, TCanvas
	from array import array
	from numpy import mean,std
	from math import sqrt
	from logNormalTest import averageFractionSize

	f = open(filename,'r')
	if not f: raise RuntimeError, "Cannot open "+filename+"\n"


	## Process .cvs file first
	data = {} ## store everything in this dictionary of size -> rate
	for line in f:
		if len(line.strip()) == 0 or line.strip()[0] == '#': continue
		spline = line.replace("\n","").split(",")

		rate = map(lambda x: int(float(x)), spline[1:])
		if doCleaning: rate = metaCleaning(rate)

		if int(spline[0]) not in data.keys():
			data[int(spline[0])] = rate
		else:
			prev_rate = data[int(spline[0])]
			if len(rate) > len(prev_rate):
				rate = rate[:len(prev_rate)]
			if len(rate) < len(prev_rate):
				prev_rate = prev_rate[:len(rate)]
			data[int(spline[0])] = map(lambda a,b:a+b, prev_rate, rate)


	of = TFile(treefile, 'update')
	if not of.GetDirectory(dirname):
		of.mkdir(dirname)
	of.cd(dirname)

	t = TTree('t', 'daq2val tree')

	fragsize    = array('f', [0])
	sufragsize  = array('f', [0])
	throughput  = array('f', [0])
	throughputE = array('f', [0])
	avrate      = array('f', [0])
	stdrate     = array('f', [0])
	nfes        = array('i', [0])
	nbus        = array('i', [0])
	nrus        = array('i', [0])

	t.Branch('FragSize',    fragsize,    'FragSize/F')
	t.Branch('SuFragSize',  sufragsize,  'SuFragSize/F')
	t.Branch('AvRate',      avrate,      'AvRate/F')
	t.Branch('SigmaRate',   stdrate,     'SigmaRate/F')
	t.Branch('ThroughPut',  throughput,  'ThroughPut/F')
	t.Branch('ThroughPutE', throughputE, 'ThroughPutE/F')
	t.Branch('nFEROLs',     nfes,        'nFEROLs/I')
	t.Branch('nBUs',        nbus,        'nBUs/I')
	t.Branch('nRUs',        nrus,        'nRUs/I')

	nfes[0] = nStreams
	nbus[0] = nBus
	nrus[0] = nRus

	output_case = 0 ## 0 (fragsize), 1 (superfragsize), 2 (eventsize)
	checked = False

	# LOWERLIMIT=32
	LOWERLIMIT=24
	UPPERLIMIT=16000
	if nStreams/nRus==4:  UPPERLIMIT = 64000 ## This is only true for eFEROLs!
	if nStreams/nRus==8:  UPPERLIMIT = 32000
	if nStreams/nRus==12: UPPERLIMIT = 21000
	if nStreams/nRus==16: UPPERLIMIT = 16000
	if nStreams/nRus==24: UPPERLIMIT = 10000

	##################################################
	## Fuckups:
	if 'Aug25' in dirname and nStreams/nRus==24: UPPERLIMIT = 21000
	##################################################

	if options.verbose > 4: print 'UPPERLIMIT is ', UPPERLIMIT

	for size in sorted(data.keys()):
		if abs(mean(data[size])) < 0.01 and abs(std(data[size])) < 0.01: continue ## skip empty lines

		## Determine what the first item in the server.csv file stands for
		if not checked: ## only do this for the first time
			checked = True
			if   int(size)//startfragsize == 1:             output_case = 0
			elif int(size)//startfragsize == nStreams/nRus: output_case = 1
			elif int(size)//startfragsize == nStreams:      output_case = 2
			else:                                           output_case = 1 ## default

		## Extract event size
		if output_case == 0: ## fragment size
			eventsize = float(size)*nStreams
		if output_case == 1: ## superfragment size
			eventsize = float(size)*nRus
		if output_case == 2: ## event size
			eventsize = float(size)

		## Calculate fragment and super fragment sizes
		fragsize[0]    = eventsize/nStreams
		sufragsize[0]  = eventsize/nRus
		if rms is not None and rms != 0.0:
			fragsize[0] = averageFractionSize(eventsize/nStreams, rms*eventsize/nStreams, LOWERLIMIT, UPPERLIMIT)
			sufragsize[0] = fragsize[0]*nStreams/nRus

		## Calculate rate
		avrate[0]      = mean(data[size])
		stdrate[0]     = std(data[size])
		throughput[0]  = sufragsize[0]*avrate[0]/1e6 ## in MB/s
		throughputE[0] = sufragsize[0]*stdrate[0]/1e6

		t.Fill()

	of.Write()
	of.Close()
	f.close()

##---------------------------------------------------------------------------------
## Plotting and printing
def printTable(filename, case):
	from ROOT import TFile, TTree, gDirectory

	f = TFile(filename)
	if not f.IsOpen(): raise RuntimeError, "Cannot open "+filename+"\n"
	treeloc = case+"/t"
	try:
		t = gDirectory.Get(treeloc)

		entries = t.GetEntriesFast()

		## Loop on the tree
		print "--------------------------------------------------------------------------------------"
		print "Case: " + case
		print "--------------------------------------------------------------------------------------"
		print "Superfrag. Size (B) : Fragment Size (B) : Av. Throughput (MB/s) :       Av. Rate     :"
		print "--------------------------------------------------------------------------------------"
		for	jentry in xrange(entries):
			if t.GetEntry(jentry) <= 0: continue
			# if t.BU+1==t.nBUs: ## Only check the sums
				# deltaTP =
			print "             %6d :            %6d :      %6.1f +- %6.1f :  %8.1f +- %6.1f" % \
			(t.SuFragSize, t.FragSize, t.ThroughPut, t.ThroughPutE, t.AvRate, t.SigmaRate)

		print "--------------------------------------------------------------------------------------"
	except AttributeError as e:
		print "Didn't find tree", treeloc, "in file", filename
		raise e

	f.Close()
def makeMultiPlot(filename, caselist, rangey=(0,5500), rangex=(250,17000), oname='', frag=True, logx=True, logy=False, tag='', legends=[], makePNGs=True, rate=100):
	from ROOT import gROOT, gStyle, TFile, TTree, gDirectory, TGraphErrors, TCanvas, TLegend, TH2D, TPaveText
	from operator import itemgetter

	gROOT.SetBatch()
	gStyle.SetOptStat(0)
	f = TFile(filename)
	if not f.IsOpen(): raise RuntimeError, "Cannot open "+filename+"\n"

	if oname.endswith('.pdf') or oname.endswith('.png'): oname = oname[:-4]
	if len(oname)==0: ## default
		oname = 'plot_' + reduce(lambda x,y:x+'_'+y, caselist)

	canv = TCanvas(oname, "Plot", 0, 0, 1024, 768)
	canv.cd()
	if logx: canv.SetLogx()
	if logy: canv.SetLogy()
	canv.SetGridx()
	canv.SetGridy()
	## Cosmetics
	# canv.DrawFrame(rangex[0], rangey[0], rangex[1], rangey[1])
	axes = TH2D('axes', 'A', 100, rangex[0], rangex[1], 100, rangey[0], rangey[1])
	axes.GetYaxis().SetTitle("Av. Throughput per RU (MB/s)")
	axes.GetYaxis().SetTitleOffset(1.4)
	axes.GetXaxis().SetTitleOffset(1.2)
	if(frag):
		axes.SetTitle("Throughput vs. Fragment Size")
		axes.GetXaxis().SetTitle("Fragment Size (bytes)")
	else:
		axes.SetTitle("Throughput vs. Superfragment Size")
		axes.GetXaxis().SetTitle("Superfragment Size (bytes)")
	axes.GetXaxis().SetMoreLogLabels()
	axes.GetXaxis().SetNoExponent()
	axes.Draw()
	if len(tag) > 0:
		width = 0.022*len(tag)
		pave = TPaveText(0.12, 0.80, 0.12+width, 0.899, 'NDC')
		pave.SetTextFont(42)
		pave.SetTextSize(0.05)
		pave.SetFillStyle(1001)
		pave.SetFillColor(0)
		pave.SetBorderSize(0)
		pave.SetTextAlign(12)
		pave.AddText(tag)
		pave.Draw()

	graphs = []
	configs = set()
	for case in caselist:
		try:
			graphs.append(getGraph(f, case, frag=frag))
			configs.add(getConfig(case.split('/').pop())[:2])
		except AttributeError:
			print "#### Couldn't get graph for ", case, "in file", filename
			return

	# if options.daq1:
	# 	daq1_graph = getDAQ1Graph()

	configs = sorted(configs, key=itemgetter(0))
	nlegentries = len(caselist)
	# nlegentries = len(caselist) if not options.daq1 else len(caselist) + 1
	legendpos = (0.44, 0.13, 0.899, 0.20+nlegentries*0.05)
	# if options.legendPos == 'TL':
	# 	legendpos = (0.12, 0.82-nlegentries*0.05, 0.579, 0.898)
	# 	# legendpos = (0.12, 0.71-nlegentries*0.05, 0.579, 0.78)
	leg = TLegend(legendpos[0], legendpos[1], legendpos[2], legendpos[3])
	leg.SetFillStyle(1001)
	leg.SetFillColor(0)
	leg.SetTextFont(42)
	leg.SetTextSize(0.033)
	leg.SetBorderSize(0)

	colors  = [1,2,3,4,51,95]
	markers = [20,21,22,23,34,33]

	if len(legends) > 0 and len(legends) != len(caselist):
		print "Legends doesn't match with caselist, falling back to default"

	for n,graph in enumerate(graphs):
		graph.SetLineColor(colors[n])
		graph.SetMarkerColor(colors[n])
		graph.SetMarkerStyle(markers[n])

		if len(legends) == len(caselist) and len(legends)>0: ## Custom legends
			leg.AddEntry(graph, legends[n], 'P')
		else: ## Default
			leg.AddEntry(graph, caselist[n].split('/').pop(), 'P')
		# if options.daq1:
		# 	leg.AddEntry(daq1_graph, 'DAQ1 (2011)', 'P')
		graph.Draw("PL")

	# if options.daq1:
	# 	daq1_graph.Draw("PL")

	if not frag:
		func = getRateGraph(rate=rate)
		func.Draw("same")
		leg.AddEntry(func, '100 kHz', 'l')

	else:
		for n,c in enumerate(configs):
			func = getRateGraph(c[0]/c[1], frag=frag, rate=rate)
			func.SetLineColor(colors[n])
			func.SetLineWidth(1)
			leg.AddEntry(func, '%.0f kHz (%d streams)'% (rate, c[0]/c[1]), 'l')
			func.DrawCopy("same")

	leg.Draw()

	for graph in graphs: graph.Draw("PL")

	canv.Print(oname + '.pdf')
	if makePNGs:  canv.Print(oname + '.png')
	# if options.makePNGs:  canv.Print(oname + '.png')
	# if options.makeCFile: canv.SaveAs(oname + '.C')

	f.Close()
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
def getGraph(file, subdir, frag=False):
	from ROOT import TFile, TTree, gDirectory, TGraphErrors, TCanvas
	from array import array

	if not file.IsOpen(): raise RuntimeError("File not open")
	treeloc = subdir+"/t"
	try:
		t = gDirectory.Get(treeloc)
		entries = t.GetEntriesFast()
		nsteps  = t.GetEntries()
		step    = 0

		g = TGraphErrors(nsteps)

		## Loop on the tree
		for	jentry in xrange(entries):
			if t.GetEntry(jentry) <= 0: continue
			if(frag): g.SetPoint(step, t.FragSize,   t.ThroughPut)
			else:     g.SetPoint(step, t.SuFragSize, t.ThroughPut)
			g.SetPointError(     step,           0., t.ThroughPutE)
			step+=1

		g.SetLineWidth(2)
		g.SetMarkerSize(1.7)

		return g
	except AttributeError as e:
		print "#### Didn't find tree", treeloc, "in file", file
		raise e

def getDAQ1Graph():
	from ROOT import TGraph
	data = [
	(   256, 33.92),
	(   512, 67.74),
	(  1024, 133.12),
	(  1536, 206.90),
	(  2048, 241.66),
	(  2560, 259.07),
	(  3008, 271.92),
	(  3840, 276.48),
	(  4096, 278.12),
	(  5120, 275.97),
	(  6400, 276.48),
	(  7840, 298.70),
	(  8192, 299.01)]
	# ( 65536, 347.34),
	# (102400, 357.38)]

	g = TGraph(len(data))
	for n,(size,tp) in enumerate(data):
		g.SetPoint(n, size, tp)
	g.SetMarkerStyle(21)
	g.SetMarkerColor(52)
	g.SetLineWidth(2)
	g.SetLineColor(52)
	return g
def makeDAQ1vsDAQ2Plot(filename, case):
	options.daq1 = True
	makeMultiPlot(filename, [case], oname='daq1vsdaq2', rangey=(options.miny, options.maxy), rangex=(options.minx, options.maxx), frag=options.frag, logx=options.logx, logy=options.logy, rate=options.rate, legends=['DAQ2 (2013) (merging 12 streams)'])

##---------------------------------------------------------------------------------
## User interface
def addPlottingOptions(parser):
	usage = """

	First produce the ROOT file with tree from csv files with:
	 	%prog [options] path/to/directory/
	where directory contains subdirectories of cases.
	If --doCleaning is given, the data is cleaned, and a cleaned .csv file is produced.
	Afterwards, produce plots with:
	 	%prog [options] path/to/file.root case1 case2 case3
	or print a table to stdout with:
	 	%prog [options] --print path/to/file.root case

	Cases can be referred to by the path to the directory which contains the ROOT file,
	e.g. data/Aug7/eFEROLs/EvB/32x2x4_RMS_0.5_useLogNormal_true
	I tested until up to four cases per plot.
	"""

	parser.usage = usage
	parser.add_option("-d", "--dir", default="data/", action="store", type="string", dest="dir", help="Input directory containing subdirectories with server.csv files [default: %default]")
	parser.add_option("-o", "--outputName", default="plot.pdf", action="store", type="string", dest="outputName", help="File for plot output [default: %default]")
	parser.add_option("--outdir", default="plots/", action="store", type="string", dest="outdir", help="Output directory for the plots [default: %default]")
	parser.add_option("-p", "--print", default=False, action="store_true", dest="print_table", help="Print mode, give .root file and case as arguments")
	parser.add_option("-C", "--doCleaning", default=False, action="store_true", dest="doCleaning", help="Remove outliers in the rates when filling the trees")

	parser.add_option("-v", "--verbose", default="1", action="store", type="int", dest="verbose", help="Verbose level [default: %default (semi-quiet)]")

	parser.add_option("-r", "--rate", default="100", action="store", type="float", dest="rate", help="Verbose level [Rate in kHz to be displayed on the plot: %default kHz]")

	parser.add_option("--makeDAQ1vsDAQ2Plot", default=False, action="store_true", dest="makeDAQ1vsDAQ2Plot", help="Make daq1 vs daq2 overlay plot")
	parser.add_option("--daq1", default=False, action="store_true", dest="daq1", help="Overlay daq1 performance?")

	parser.add_option("--miny", default="0", action="store", type="float", dest="miny", help="Y axis range, minimum")
	parser.add_option("--maxy", default="5500", action="store", type="float", dest="maxy", help="Y axis range, maximum")
	parser.add_option("--minx", default="250", action="store", type="float", dest="minx", help="X axis range, minimum")
	parser.add_option("--maxx", default="17000", action="store", type="float", dest="maxx", help="X axis range, maximum")
	parser.add_option("--frag", default=True, action="store_true", dest="frag", help="Set to false to plot vs super fragment size instead of fragment size")
	parser.add_option("--logx", default=True, action="store_true", dest="logx", help="Use logarithmic scale on x axis")
	parser.add_option("--logy", default=False, action="store_true", dest="logy", help="Use logarithmic scale on y axis")
	parser.add_option("--legendPos", default="BR", action="store", type="string", dest="legendPos", help="Position for legend, either 'TL' (top left), 'TR' (top right), 'BL' (bottom left), 'BR'  (bottom right) [default: %default]")
	parser.add_option("--makePNGs", default=True, action="store_true", dest="makePNGs", help="Produce also .png file")
	parser.add_option("--makeCFile", default=True, action="store_true", dest="makeCFile", help="Produce also .C file")

if __name__ == "__main__":
	from optparse import OptionParser
	parser = OptionParser()
	addPlottingOptions(parser)
	(options, args) = parser.parse_args()

	## DAQ1 vs DAQ2 plot
	if len(args) == 2 and options.makeDAQ1vsDAQ2Plot:
		makeDAQ1vsDAQ2Plot(args[0], args[1])
		exit(0)

	## Argument is a directory
	if len(args) > 0 and os.path.isdir(args[0]):
		processDirs(args[0])
		exit(0)

	## Argument is a root file
	if len(args) > 1 and os.path.isfile(args[0]) and os.path.splitext(args[0])[1] == '.root':
		if options.print_table:
			printTable(args[0], args[1])
			exit(0)
		else:
			makeMultiPlot(args[0], args[1:], rangey=(options.miny, options.maxy), rangex=(options.minx, options.maxx), frag=options.frag, oname=options.outputName, logx=options.logx, logy=options.logy, rate=options.rate)
			exit(0)

	## Argument is a csv file
	if len(args) > 0 and os.path.isfile(args[0]) and os.path.splitext(args[0])[1] == '.csv':
		if options.doCleaning:
			cleanFile(args[0])
			exit(0)
		else:
			parser.print_help()
			exit(-1)

	else:
		parser.print_help()
		exit(-1)
