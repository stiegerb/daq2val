#! /usr/bin/env python
import daq2Utils as utils
from daq2Control import daq2Control

def getListOfSizes(maxSize, minSize=256, short=False):
	stepsize = 256
	allsteps = [ n*stepsize for n in xrange(1, 1000) if n*stepsize <= 8192] ## multiples of stepsize up to 8192
	allsteps += [9216, 10240, 11264, 12288, 13312, 14336, 15360, 16000]
	# if short: allsteps = [1024, 16000]
	if short: allsteps = [256, 512, 1024, 2048, 3072, 4096, 6144, 8192, 12288, 16000]

	steps = []
	for step in allsteps:
		if step >= minSize and step <= maxSize: steps.append(step)

	print ' Will scan over the following sizes:', steps
	return steps

if __name__ == "__main__":
	from optparse import OptionParser
	from runDAQ2Test import addOptions, testBuilding
	parser = OptionParser()
	addOptions(parser)
	parser.add_option("--maxSize", default=16000, action="store", type="int", dest="maxSize",     help="Maximum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--minSize", default=256,   action="store", type="int", dest="minSize",     help="Minimum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--short",   default=False, action="store_true",        dest="short",       help="Run a short scan with only a few points")

	(options, args) = parser.parse_args()

	if options.useRate == 0: options.useRate = 'max'

	######################
	if len(args) < 2:
		print "Not enough arguments: need to specify at least a configuration file and a fragment size."
		exit(-1)

	configfile = args[0]
	fragSize = int(args[1])
	try:
		options.relRMS = float(args[2])
		options.useLogNormal = True
	except KeyError:
		options.relRMS = None
		options.useLogNormal = False

	######################
	d2c = daq2Control(configfile, options)
	d2c.setup()

	steps = getListOfSizes(options.maxSize, minSize=options.minSize, short=options.short)

	## Check maxSize from table and merging case:
	mergingby = d2c.config.nStreams//len(d2c.config.RUs)
	if not utils.checkScanLimit(steps[-1], mergingby):
		message = """
WARNING: Your maximum size for scanning doesn't seem to
         make sense. Please consider!
 Is set to: %d. Expected to scan only until: %d
		""" % (steps[-1], SIZE_LIMIT_TABLE[mergingby][1])
		printWarningWithWait(message, waitfunc=sleep, waittime=10)
		sleep(10,options.verbose,options.dry)

	utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
	d2c.start(options.minSize, float(options.relRMS)*options.minSize, rate=options.useRate)

	## Test event building first
	if not testBuilding(d2c, 1000, options.testTime, verbose=options.verbose, dry=options.dry):
		if options.verbose > 0: print 'Test failed, built less than 1000 events!'
		utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
		exit(-1)
	if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'

	## Start the scan
	for step in steps:
		d2c.changeSize(step, float(options.relRMS)*step, rate=options.useRate)
		if options.verbose > 0: print separator
		if options.verbose > 0: print "Building events at fragment size %d for %d seconds..." % (step, options.duration)
		if options.useIfstat:
			## Get throughput directly from RU using ifstat script
			d2c.getResultsFromIfstat(options.duration)
		elif d2c.config.useEvB:
			## Get results ala testRubuilder script every 5 seconds
			d2c.getResultsEvB(options.duration, interval=5)
		else:
			## Wait for the full duration and get results at the end
			sleep(options.duration,options.verbose,options.dry)
			## For eFEROLs, get results after each step
			if len(d2c.config.eFEROLs) > 0 or options.stopRestart: d2c.getResults()
		if options.verbose > 0: print "Done"

	## For FEROLs, get results at the end
	if len(d2c.config.FEROLs) > 0 and not d2c.config.useEvB and not options.stopRestart: d2c.getResults()

	utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
	print separator
	print ' DONE '
	print separator
	exit(0)

