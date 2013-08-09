#! /usr/bin/env python

## Replace .pop() by [-1] ?
import re
import sys, os

##---------------------------------------------------------------------------------
## Utilities
def getConfig(string):
	"""Extract number of streams, readout units, builder units, and RMS from strings such as
	8x1x2 or 16s8fx2x4_RMS_0.5 (i.e 8,1,2,None in the first case, 16,2,4,0.5 in the second)
	"""
	string = string.split('_')
	case = string[0].split('x')
	rms = None
	if re.match(r'([0-9]+)s[0-9]+f', case[0]):
		nstreams = int(re.match(r'([0-9]+)s[0-9]+f', case[0]).group(1))
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

	return nstreams, nrus, nbus, rms
def fillTreeForDir(treefile, subdir, files):
	if options.verbose > 0: print "  ... processing", subdir
	if not 'server.csv' in files: return

	nstreams, nrus, nbus, rms = getConfig(subdir.split('/').pop())
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
	if mean(data) > 0 and std(data)/mean(data) > quality:
		clean_data = []
		pos = 0
		stretch = data[:length]
		try:
			# while mean(stretch) == 0 or mean(stretch) > 0 and std(stretch)/mean(stretch) > quality and pos+length < len(data):
			while mean(stretch) == 0 or mean(stretch) > 0 and std(stretch)/mean(stretch) > quality:
				# print stretch
				# print pos, len(data)
				pos += step
				stretch = data[pos:length+pos]
		except FloatingPointError, KeyError:
			# print "Didn't find a clean stretch in:"
			# print data
			return data

		for r in data:
			if abs(r-mean(stretch)) > cutoff*std(stretch):
				clean_data.append(mean(stretch))
			else: clean_data.append(r)

		# print std(clean_data)/mean(clean_data)
		return clean_data
	else: return data
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
			for d in cleandata:
				o.write
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
##  (this is where the magic happens)
def fillTree(filename, treefile, dirname, nStreams, nBus, nRus, rms=0, startfragsize=128, doCleaning=False):
	from ROOT import TFile, TTree, gDirectory, TGraphErrors, TCanvas
	from array import array
	from numpy import mean,std
	from math import sqrt
	from logNormalTest import averageFractionSize
	# def averageFractionSize(mean, sigma, lowerLimit, upperLimit):

	f = open(filename,'r')
	if not f: raise RuntimeError, "Cannot open "+filename+"\n"

	of = TFile(treefile, 'update')
	if not of.GetDirectory(dirname):
		of.mkdir(dirname)
	of.cd(dirname)

	t = TTree('t', 'daq2val tree')

	fragsize    = array('f', [0])
	sufragsize  = array('f', [0])
	throughput  = array('f', [0])
	throughputE = array('f', [0])
	nruns       = array('i', [0])
	maxruns     = 200
	rate        = array('i', maxruns*[0])
	avrate      = array('f', [0])
	stdrate     = array('f', [0])
	nfes        = array('i', [0])
	nbus        = array('i', [0])
	nrus        = array('i', [0])

	t.Branch('FragSize',    fragsize,    'FragSize/F')
	t.Branch('SuFragSize',  sufragsize,  'SuFragSize/F')
	t.Branch('nRuns',       nruns,       'nRuns/I')
	t.Branch('Rate',        rate,        'Rate[nRuns]/I')
	t.Branch('AvRate',      avrate,      'AvRate/F')
	t.Branch('SigmaRate',   stdrate,     'SigmaRate/F')
	t.Branch('ThroughPut',  throughput,  'ThroughPut/F')
	t.Branch('ThroughPutE', throughputE, 'ThroughPutE/F')
	t.Branch('nFEROLs',     nfes,        'nFEROLs/I')
	t.Branch('nBUs',        nbus,        'nBUs/I')
	t.Branch('nRUs',        nrus,        'nRUs/I')

	sufragsize[0] = -1

	nfes[0] = nStreams
	nbus[0] = nBus
	nrus[0] = nRus

	added   = False
	checked = False

	LOWERLIMIT=32
	UPPERLIMIT=16000
	if nStreams/nRus==4:  UPPERLIMIT = 64000 ## This is only true for eFEROLs!
	if nStreams/nRus==8:  UPPERLIMIT = 32000
	if nStreams/nRus==12: UPPERLIMIT = 21000
	if nStreams/nRus==16: UPPERLIMIT = 16000

	### Adding up nBU lines of event rates
	prev_size = 0
	prev_rate = []

	for line in f:
		if len(line.strip()) == 0 or line.strip()[0] == '#': continue
		spline = line.replace("\n","").split(",")

		## Fill the tree variables
		nruns[0] = len(spline)-1
		if nruns[0]>maxruns: raise RuntimeError("Number of runs (%d) exceeds maximum (%d). Increase maxruns!\n"%(len(spline[1:]),maxruns))

		rate = map(lambda x: int(float(x)), spline[1:])
		if doCleaning: rate = metaCleaning(rate)
		# if doCleaning: rate = cleanData(rate)

		## Two cases of output files (Grrrr):
		##  1. beginning of line is super frag size, and BU's are not added
		##  2. beginning of line is fragment size, and BU's are already added up

		if not checked: ## only do this for the first time
			checked = True
			if int(spline[0])//nStreams < startfragsize: added = True
			else: added = False

		if added: ## fragmentsize, BUs added
			fragsize[0]    = float(spline[0])
			if abs(mean(rate)) < 0.01 and abs(std(rate)) < 0.01: continue ## skip empty lines

			if rms is not None and rms != 0.0:
				fragsize[0] = averageFractionSize(fragsize[0], rms*fragsize[0], LOWERLIMIT, UPPERLIMIT)

			eventsize = nStreams*fragsize[0]

			avrate[0]      = mean(rate)
			stdrate[0]     = std(rate)
			# fragsize[0]    = eventsize/nStreams
			sufragsize[0]  = eventsize/nRus
			throughput[0]  = sufragsize[0]*avrate[0]/1e6 ## in MB/s
			throughputE[0] = sufragsize[0]*stdrate[0]/1e6

			t.Fill()
			continue

		else: ## superfragmentsize, BUs not added
			eventsize = float(spline[0])
			prev_rate = rate
			for i in xrange(nBus-1):
				line = next(f, 'EOF')
				if len(line.strip()) == 0 or line.strip()[0] == '#': line = next(f, 'EOF')
				spline = line.replace("\n","").split(",")
				rate = map(lambda x: int(float(x)), spline[1:])
				if doCleaning: rate = metaCleaning(rate)
				# if doCleaning: rate = cleanData(rate)

				prev_rate = map(lambda a,b:a+b, prev_rate, rate) ## add up the elements of the two rate lists

			avrate[0]      = mean(prev_rate)
			stdrate[0]     = std(prev_rate)
			fragsize[0]    = eventsize/nStreams
			sufragsize[0]  = eventsize/nRus

			if rms is not None and rms != 0.0:
				fragsize[0] = averageFractionSize(eventsize/nStreams, rms*eventsize/nStreams, LOWERLIMIT, UPPERLIMIT)
				sufragsize[0] = fragsize[0]*nStreams/nRus

			throughput[0]  = sufragsize[0]*avrate[0]/1e6 ## in MB/s
			throughputE[0] = sufragsize[0]*stdrate[0]/1e6

			prev_size = eventsize
			prev_rate      = rate

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
		print "Didn't find tree", treeloc, "in file", file
		raise e

	f.Close()
def makeMultiPlot(filename, caselist, rangey=(0,5500), rangex=(250,17000), oname='', frag=False, logx=True, logy=False, tag=''):
	from ROOT import gROOT, gStyle, TFile, TTree, gDirectory, TGraphErrors, TCanvas, TLegend, TH2D, TPaveText
	from operator import itemgetter

	gROOT.SetBatch()
	gStyle.SetOptStat(0)
	f = TFile(filename)
	if not f.IsOpen(): raise RuntimeError, "Cannot open "+filename+"\n"

	canv = TCanvas("Plot", "Plot", 0, 0, 1024, 768)
	canv.cd()
	if logx: canv.SetLogx()
	if logy: canv.SetLogy()
	canv.SetGridx()
	canv.SetGridy()
	## Cosmetics
	canv.DrawFrame(rangex[0], rangey[0], rangex[1], rangey[1])
	axes = TH2D('axes', 'A', 10, rangex[0], rangex[1], 10, rangey[0], rangey[1])
	axes.GetYaxis().SetTitle("Av. Throughput per RU (MB/s)")
	axes.GetYaxis().SetTitleOffset(1.4)
	axes.GetXaxis().SetTitleOffset(1.2)
	if(frag):
		axes.SetTitle("Throughput vs. Fragment Size")
		axes.GetXaxis().SetTitle("Fragment Size (bytes)")
	else:
		axes.SetTitle("Throughput vs. Superfragment Size")
		axes.GetXaxis().SetTitle("Superfragment Size (bytes)")
	axes.Draw()
	if len(tag) > 0:
		pave = TPaveText(0.12, 0.75, 0.30, 0.88, 'NDC')
		pave.SetTextFont(42)
		pave.SetTextSize(0.06)
		pave.SetFillStyle(1001)
		pave.SetFillColor(0)
		pave.SetBorderSize(0)
		pave.AddText(tag)
		pave.Draw()

	graphs = []
	configs = set()
	for case in caselist:
		graphs.append(getGraph(f, case, frag=frag))
		configs.add(getConfig(case.split('/').pop())[:2])

	configs = sorted(configs, key=itemgetter(0))
	leg = TLegend(0.38, 0.13, 0.899, 0.20+len(caselist)*0.05)
	leg.SetFillStyle(1001)
	leg.SetFillColor(0)
	leg.SetTextFont(42)
	leg.SetTextSize(0.033)
	leg.SetBorderSize(0)

	colors = [1,2,3,4]

	for n,graph in enumerate(graphs):
		graph.SetLineColor(colors[n])
		graph.SetMarkerColor(colors[n])

		leg.AddEntry(graph, caselist[n].split('/').pop(), 'P')
		graph.Draw("PL")

	if not frag:
		func = get100kHzRateGraph()
		func.Draw("same")
		leg.AddEntry(func, '100 kHz', 'l')

	else:
		for n,c in enumerate(configs):
			func = get100kHzRateGraph(c[0]/c[1], frag=frag)
			func.SetLineColor(colors[n])
			func.SetLineWidth(1)
			leg.AddEntry(func, '100 kHz (%d streams)'% c[0], 'l')
			func.DrawCopy("same")

	leg.Draw()
	if len(oname)==0: ## default
		oname = 'plot_' + reduce(lambda x,y:x+'_'+y, caselist) + '.pdf'
	canv.Print(oname)
	f.Close()
def get100kHzRateGraph(nStreams=4, frag=False, xmax=100000):
	'''Returns a TF1 object corresponding to the average throughput at the RU
	necessary for a 100kHz rate of events of a given (super)fragment size '''
	from ROOT import TF1
	rate = 0.1
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

		g.SetMarkerStyle(20)
		g.SetLineWidth(2)

		return g
	except AttributeError as e:
		print "Didn't find tree", treeloc, "in file", file
		raise e

def makeStandardPlots():
	outputdir = 'plots/Aug8/'
	rootfile  = 'data/Aug7.root'
	prefix = 'data/Aug7/eFEROLs/'

	## Case lists:
	list_8x1x2_lognormals_gevb2g  = [ prefix + 'gevb2g/dummyFerol/' + x for x in ['8x1x2_RMS_0_useLogNormal_false', '8x1x2_RMS_0.5_useLogNormal_true', '8x1x2_RMS_1_useLogNormal_true', '8x1x2_RMS_2_useLogNormal_true']]
	list_16x1x2_lognormals_gevb2g = [ prefix + 'gevb2g/dummyFerol/' + x for x in ['16x1x2_RMS_0_useLogNormal_false', '16x1x2_RMS_0.5_useLogNormal_true', '16x1x2_RMS_1_useLogNormal_true', '16x1x2_RMS_2_useLogNormal_true']]
	list_x1x2_lognormals_gevb2g   = [ prefix + 'gevb2g/dummyFerol/' + x for x in ['8x1x2_RMS_0_useLogNormal_false', '8x1x2_RMS_1_useLogNormal_true', '16x1x2_RMS_0_useLogNormal_false', '16x1x2_RMS_1_useLogNormal_true']]

	list_8x1x4_lognormals_EvB     = [ prefix + 'EvB/' + x for x in ['8x1x4_RMS_0_useLogNormal_false',  '8x1x4_RMS_0.5_useLogNormal_true', '8x1x4_RMS_1_useLogNormal_true', '8x1x4_RMS_2_useLogNormal_true']]
	list_16x1x4_lognormals_EvB    = [ prefix + 'EvB/' + x for x in ['16x1x4_RMS_0_useLogNormal_false', '16x1x4_RMS_0.5_useLogNormal_true', '16x1x4_RMS_1_useLogNormal_true', '16x1x4_RMS_2_useLogNormal_true']]
	list_16x2x4_lognormals_EvB    = [ prefix + 'EvB/' + x for x in ['16x2x4_RMS_0_useLogNormal_false', '16x2x4_RMS_0.5_useLogNormal_true', '16x2x4_RMS_1_useLogNormal_true', '16x2x4_RMS_2_useLogNormal_true']]

	list_32x2x4_lognormals_EvB    = [ prefix + 'EvB/' + x for x in ['32x2x4_RMS_0_useLogNormal_false', '32x2x4_RMS_0.5_useLogNormal_true', '32x2x4_RMS_1_useLogNormal_true', '32x2x4_RMS_2_useLogNormal_true']]
	list_x1x4_lognormals_EvB      = [ prefix + 'EvB/' + x for x in ['8x1x4_RMS_0_useLogNormal_false', '8x1x4_RMS_1_useLogNormal_true', '16x1x4_RMS_0_useLogNormal_false', '16x1x4_RMS_1_useLogNormal_true']]


	## Do the plots
	makeMultiPlot(rootfile, list_8x1x2_lognormals_gevb2g,  oname=outputdir+'8x1x2_lognormals_gevb2g_frag.pdf',  frag=True,  tag='gevb2g')
	makeMultiPlot(rootfile, list_16x1x2_lognormals_gevb2g, oname=outputdir+'16x1x2_lognormals_gevb2g_frag.pdf', frag=True,  tag='gevb2g')
	makeMultiPlot(rootfile, list_8x1x4_lognormals_EvB,     oname=outputdir+'8x1x4_lognormals_EvB_frag.pdf',     frag=True,  tag="EvB")
	makeMultiPlot(rootfile, list_16x1x4_lognormals_EvB,    oname=outputdir+'16x1x4_lognormals_EvB_frag.pdf',    frag=True,  tag="EvB")
	makeMultiPlot(rootfile, list_16x2x4_lognormals_EvB,    oname=outputdir+'16x2x4_lognormals_EvB_frag.pdf',    frag=True,  tag="EvB")
	makeMultiPlot(rootfile, list_32x2x4_lognormals_EvB,    oname=outputdir+'32x2x4_lognormals_EvB_frag.pdf',    frag=True,  tag="EvB")
	makeMultiPlot(rootfile, list_x1x2_lognormals_gevb2g,   oname=outputdir+'x1x2_lognormals_gevb2g_frag.pdf',   frag=True,  tag='gevb2g')
	makeMultiPlot(rootfile, list_x1x4_lognormals_EvB,      oname=outputdir+'x1x4_lognormals_EvB_frag.pdf',      frag=True,  tag='EvB')

	makeMultiPlot(rootfile, list_x1x2_lognormals_gevb2g,   rangex=(1500, 150000), oname=outputdir+'x1x2_lognormals_gevb2g_sufrag.pdf', frag=False, tag='gevb2g')
	makeMultiPlot(rootfile, list_x1x4_lognormals_EvB,      rangex=(1500, 150000), oname=outputdir+'x1x4_lognormals_EvB_sufrag.pdf',    frag=False, tag='EvB')


##---------------------------------------------------------------------------------
## User interface
if __name__ == "__main__":
	from optparse import OptionParser
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

	parser = OptionParser(usage=usage)
	parser.add_option("-d", "--dir", default="data/",
	                  action="store", type="string", dest="dir",
	                  help="Input directory containing subdirectories with server.csv files [default: %default]")
	parser.add_option("-o", "--outputName", default="plot.pdf",
	                  action="store", type="string", dest="outputName",
	                  help="File for plot output [default: %default]")
	parser.add_option("-p", "--print", default=False,
	                  action="store_true", dest="print_table",
	                  help="Print mode, give .root file and case as arguments")
	parser.add_option("-C", "--doCleaning", default=False,
	                  action="store_true", dest="doCleaning",
	                  help="Remove outliers in the rates when filling the trees")

	parser.add_option("-v", "--verbose", default="1",
	                  action="store", type="int", dest="verbose",
	                  help="Verbose level [default: %default (semi-quiet)]")

	parser.add_option("--miny", default="0",
	                  action="store", type="float", dest="miny",
	                  help="Y axis range, minimum")
	parser.add_option("--maxy", default="5500",
	                  action="store", type="float", dest="maxy",
	                  help="Y axis range, maximum")
	parser.add_option("--minx", default="250",
	                  action="store", type="float", dest="minx",
	                  help="X axis range, minimum")
	parser.add_option("--maxx", default="17000",
	                  action="store", type="float", dest="maxx",
	                  help="X axis range, maximum")
	parser.add_option("--frag", default=True,
	                  action="store_true", dest="frag",
	                  help="Set to false to plot vs super fragment size instead of fragment size")
	parser.add_option("--logx", default=True,
	                  action="store_true", dest="logx",
	                  help="Use logarithmic scale on x axis")
	parser.add_option("--logy", default=False,
	                  action="store_true", dest="logy",
	                  help="Use logarithmic scale on y axis")

	(options, args) = parser.parse_args()

	if len(args) < 1:
		makeStandardPlots()
		exit(0)
		pass

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
			makeMultiPlot(args[0], args[1:], rangey=(options.miny, options.maxy), rangex=(options.minx, options.maxx), frag=options.frag, oname=options.outputName, logx=options.logx, logy=options.logy)
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
