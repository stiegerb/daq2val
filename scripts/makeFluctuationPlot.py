#! /usr/bin/env python
import os
from plotData import getConfig


def processFile(filename, config):
	from numpy import mean, std
	f = open(filename,'r')
	if not f: raise RuntimeError, "Cannot open "+filename+"\n"

	data = []
	nstreams, nrus, nbus, rms, strperfrl = config
	for line in f:
		if len(line.strip()) == 0 or line.strip()[0] == '#': continue
		spline = line.replace("\n","").split(",")

		rate = map(lambda x: int(float(x)), spline[1:])
		eventsize = int(spline[0]) ## convert already to fragment size and throughput per RU
		fragsize = eventsize/nstreams
		sufragsize = eventsize/nrus
		data.append((fragsize, sufragsize*mean(rate)/1e6, sufragsize*std(rate)/1e6))

	f.close()
	return data

def getGraph(data, name='graph', offset=0):
	from ROOT import TGraphErrors
	g = TGraphErrors(len(data))
	for n,(_, throughput, throughputE) in enumerate(data):
		g.SetPoint(     n, offset+n, throughput)
		g.SetPointError(n,       0., throughputE)
	g.SetName(name)
	g.SetLineWidth(2)
	g.SetMarkerSize(1.7)
	return g


if __name__ == "__main__":
	usage = """
	[%prog] [options] casestring directory

	"""
	from optparse import OptionParser
	parser = OptionParser()
	parser.add_option("-v", "--verbose", default=0, action="store", type="int", dest="verbose", help="Verbose level")
	# parser.add_option("-d", "--dir", default="data/", action="store", type="string", dest="dir", help="Input directory containing subdirectories with server.csv files [default: %default]")
	parser.usage = usage
	(options, args) = parser.parse_args()

	## Check arguments
	if len(args) < 2 or not os.path.isdir(args[1]):
		parser.print_help()
		exit(-1)

	case = args[0]
	config = getConfig(case)
	directory = args[1]
	if not directory.endswith('/'): directory += '/'

	## Extract the data
	data = {}
	sizes = set()
	cwnds = set()
	for item in os.listdir(directory):
		## 16s8fx1x4_RMS_0.0_flucScan_2kB_CWND_35000
		if not os.path.isdir(directory+item) or case not in item: continue
		print "... processing", directory+item
		if not os.path.exists(directory+item+'/server.csv'):
			print "   didn't find server.csv file in", directory+item
			continue
		cwnd = item.split("_")[-1]
		size = item.split("_")[-3]
		cwnds.add(cwnd)
		sizes.add(size)
		data[size+"_"+cwnd] = processFile(directory+item+"/server.csv", config)
		nruns = len(data[size+"_"+cwnd])

		if options.verbose > 0:
			print size+"_"+cwnd
			for s, tp, tpE in data[size+"_"+cwnd]:
				print s, tp, tpE


	sizes = sorted(sizes)
	cwnds = sorted(cwnds)

	if options.verbose > 0:
		print sizes
		print cwnds

	## Plotting
	import ROOT
	ROOT.gROOT.SetBatch()
	ROOT.gStyle.SetOptStat(0)

	colors  = [2,3,4,51,95]
	markers = [20,21,22,23,34,33]

	oname = directory+case+"_flucScan"
	canv = ROOT.TCanvas(oname, "Plot", 0, 0, 1024, 768)
	canv.cd()

	rangex=(0,20)
	rangey=(0, 5500)
	axes = ROOT.TH2D('axes', 'A',       len(cwnds), rangex[0], rangex[1], 100, rangey[0], rangey[1])
	axes.GetYaxis().SetTitle("Av. Throughput per RU (MB/s)")
	axes.GetYaxis().SetTitleOffset(1.4)
	axes.SetTitle("Throughput vs. CWND Settings")
	axes.GetXaxis().SetLabelSize(0.05)
	for n,cwnd in enumerate(cwnds):
		axes.GetXaxis().SetBinLabel(n+1, "TCP_CWND="+cwnd)
	axes.Draw()

	legendpos = (0.65, 0.17, 0.899, 0.25+len(sizes)/2*0.06)
	leg = ROOT.TLegend(legendpos[0], legendpos[1], legendpos[2], legendpos[3])
	leg.SetFillStyle(1001)
	leg.SetFillColor(0)
	leg.SetTextFont(42)
	leg.SetTextSize(0.033)
	leg.SetBorderSize(0)

	tag = '%s FEROLs/EvB' % case
	tl = ROOT.TLatex()
	tl.SetTextFont(42)
	tl.SetTextSize(0.04)
	tl.SetNDC(1)
	tl.DrawLatex(0.15, 0.20, tag)
	tag = '%d runs, pause frames enabled' % nruns
	tl.SetTextSize(0.03)
	tl.DrawLatex(0.15, 0.16, tag)

	strtosize = {'1kB':1024, '2kB':2048, '4kB':4096, '8kB':8192}

	offset = 0
	graphs = []
	for cwnd in cwnds:
		for n,size in enumerate(sizes):
			key = size+"_"+cwnd
			graph = getGraph(data[key], key, offset)
			graph.SetLineColor(colors[n])
			graph.SetMarkerColor(colors[n])
			graph.SetMarkerStyle(markers[n])
			graphs.append(graph)
			legentry = "%d B fragment size" % strtosize[size]
			if offset==0: leg.AddEntry(graph, legentry, 'P')
		offset += nruns

	for graph in graphs:
		graph.Draw("P")
	leg.Draw()

	canv.Print(oname + '.pdf')
	canv.Print(oname + '.png')




