#! /usr/bin/env python
from plotData import makeMultiPlot, addPlottingOptions

def createDir(directory):
	from os import mkdir
	try:
		mkdir(directory)
	except OSError as exc:
		import errno, os.path
		if exc.errno == errno.EEXIST and os.path.isdir(directory):
			pass
		else: raise exc

	if not directory.endswith('/'): directory+='/'
	return directory

def processRMSScan(date, casename, prefix, outdir, rootfile, legends=[], tag='', rmslist=[], oname=''):
	outputdir = createDir(outdir+(prefix%date)[5:])
	if len(rmslist) == 0: rmslist = ['RMS_0.0', 'RMS_0.5', 'RMS_1.0', 'RMS_2.0']
	if len(tag)     == 0: tag = prefix.split('/')[1]+':'+prefix.split('/')[2]
	if len(legends) == 0: legends = [casename + ', ' + x.replace('_',' ') for x in rmslist]
	if len(oname)   == 0: oname = outputdir+casename
	else: oname = outputdir + oname

	caselist = []
	for x in rmslist:
		if len(x) > 0: caselist.append(prefix%date + casename + '_' + x)
		else:          caselist.append(prefix%date + casename)

	makeMultiPlot(rootfile, caselist, oname=oname, tag=tag, legends=legends, rate=options.rate)

def makeStandardPlots(rootfile, outdir):
	rootfile_clean = rootfile.replace('.root', '_clean.root')
	outputdir = createDir(outdir)

	outputdir = createDir(outdir+"Oct14")
	legends = ['%s flat (nominal)', '%s 50%% spike', '%s sawtooth']
	case = '8s8fx1x4'
	caselist =  [x%case for x in ['%s_RMS_0.0', '%s_RMS_0.0_spike05', '%s_RMS_0.0_sawtooth']]
	makeMultiPlot(rootfile, ['data/FEROLs/EvB/Oct14/%s'%x for x in caselist], oname=outputdir+'%s_EvB_sizeprofile'%case, tag='EvB/FEROLs', legends=[x%case for x in legends])

	# legends = ['%s flat (nominal)', '%s (150%% / 50%%)', '%s sawtooth']
	# case = '16s8fx1x4'
	# caselist =  [x%case for x in ['%s_RMS_0.0', '%s_RMS_0.0_spikeperfrl', '%s_RMS_0.0_sawtooth']]
	# makeMultiPlot(rootfile, ['data/FEROLs/EvB/Oct14/%s'%x for x in caselist], oname=outputdir+'%s_EvB_sizeprofile'%case, tag='EvB/FEROLs', legends=[x%case for x in legends])

	# outputdir = createDir(outdir+"Oct14")
	# legends = ['%s FEROL AutoTrigger', '%s GTPe (100 kHz)', '%s FRL Auto Trigger']
	# caselist =  [ 'data/FEROLs/EvB/Oct14/%s_RMS_0.0', 'data/FEROLs/GTPe/EvB/Oct14/%s_RMS_0.0', 'data/FEROLs/EvB/Oct14/%s_FRL_AutoTrigger_RMS_0.0']
	# for case,cwnd in zip(['8s8fx1x4', '12s12fx1x4', '16s8fx1x4', '20s10fx1x4'], ['55000', '55000', '35000', '35000']):
	# 	makeMultiPlot(rootfile, [x%case for x in caselist], oname=outputdir+'%s_EvB_GTPe_PauseFrameEnabled_oldCWND'%case, tag='EvB/FEROLs, CWND=%s'%cwnd, legends=[x%case for x in legends])

	# prefix = 'data/FEROLs/GTPe/EvB/%s/'
	# processRMSScan('Oct1', '8s8fx1x4',  prefix, outdir, rootfile, tag='FEROLs:GTPe:EvB', rmslist=['RMS_0.0'], legends=['8s8fx1x4, RMS 0.0, '])


##---------------------------------------------------------------------------------
## User interface
if __name__ == "__main__":
	from optparse import OptionParser
	# usage = """
	# Use to create a batch of standard plots:
	# %prog  --outdir plots/ data.root
	# """
	parser = OptionParser()
	addPlottingOptions(parser)
	# parser.add_option("-o", "--outdir", default="plots/", action="store", type="string", dest="outdir", help="Output directory for the plots [default: %default]")
	# parser.add_option("-r", "--rate",   default=100,      action="store", type=float,    dest="rate",   help="Displayed rate in kHz [default: %default kHz]")
	# parser.add_option("--makePNGs",     default=True,     action="store_true", dest="makePNGs",
	#                   help="Produce also .png files [default: %default]")
	(options, args) = parser.parse_args()

	if len(args) > 0:
		makeStandardPlots(args[0], outdir=options.outdir)
		exit(0)

	makeStandardPlots('data.root', outdir=options.outdir)
	exit(0)

	# parser.print_help()
	# exit(-1)



