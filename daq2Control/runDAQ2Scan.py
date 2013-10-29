#! /usr/bin/env python
import daq2Utils as utils
from daq2Control import daq2Control, separator
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import sleep, printError, printWarningWithWait, testBuilding, SIZE_LIMIT_TABLE

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
	usage = """
	%prog [options] config.xml relRMS

	Examples:
	%prog config.xml
	%prog --short --maxSize 8192 --duration 300 --useRate 100 config.xml 0.0
	"""
	addOptions(parser)
	parser.add_option("--maxSize",     default=16000, action="store", type="int", dest="maxSize",     help="Maximum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--minSize",     default=256,   action="store", type="int", dest="minSize",     help="Minimum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--short",       default=False, action="store_true",        dest="short",       help="Run a short scan with only a few points")
	parser.add_option("--stopRestart", default=False, action="store_true",        dest="stopRestart", help="Stop XDAQ processes after each step and restart instead of changing the size on the fly. [default: %default]")

	(options, args) = parser.parse_args()

	if options.useRate == 0: options.useRate = 'max'

	#####################################
	## Check input parameters
	if len(args) < 1:
		print "Not enough arguments: need to specify at least a configuration file."
		exit(-1)

	configfile = args[0]
	try:
		options.relRMS = float(args[1])
		options.useLogNormal = True
	except IndexError:
		options.relRMS = 0.0
		options.useLogNormal = False

	#####################################
	## First stop anything already running
	sm = daq2SymbolMap()
	utils.stopXDAQs(sm, verbose=options.verbose, dry=options.dry)
	print separator

	#####################################
	## Set up daq2Control
	d2c = daq2Control(configfile, options)
	d2c.setup()

	#####################################
	## Get the scanning steps
	steps = getListOfSizes(options.maxSize, minSize=options.minSize, short=options.short)

	#####################################
	## Check maxSize from table and merging case:
	mergingby = d2c.config.nStreams//len(d2c.config.RUs)
	if not utils.checkScanLimit(steps[-1], mergingby):
		message = """
WARNING: Your maximum size for scanning doesn't seem to
         make sense. Please consider!
 Is set to: %d. Expected to scan only until: %d
 		(i.e. use option --maxSize %d)
		""" % (steps[-1], SIZE_LIMIT_TABLE[mergingby][1], SIZE_LIMIT_TABLE[mergingby][1])
		printWarningWithWait(message, waitfunc=sleep, waittime=10)

	d2c.start(options.minSize, float(options.relRMS)*options.minSize, rate=options.useRate)

	#####################################
	## Test event building first
	if not testBuilding(d2c, 1000, options.testTime, verbose=options.verbose, dry=options.dry):
		if options.verbose > 0: print 'Test failed, built less than 1000 events!'
		utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
		exit(-1)
	if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'

	#####################################
	## Start the scanning
	for step in steps:
		d2c.changeSize(step, float(options.relRMS)*step, rate=options.useRate)

		## Test whether the GTPe did start up properly:
		if d2c.config.useGTPe:
			if not testBuilding(d2c, minevents=10, waittime=5, verbose=0, dry=options.dry):
				if options.verbose > 0: print 'GTPe does not seem to be running, will stop and restart.'
				d2c.changeSize(step, float(options.relRMS)*step, rate=options.useRate)
				if not testBuilding(d2c, minevents=10, waittime=5, verbose=0, dry=options.dry):
					if options.verbose > 0: printError('Failed to start event building.', self)
					raise RuntimeError

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
			sleep(options.duration, options.verbose, options.dry)
			## For eFEROLs, or when stopping and restarting after each step, get results after each step
			if len(d2c.config.eFEROLs) > 0 or options.stopRestart: d2c.getResults()
		if options.verbose > 0: print "Done"

		## Dump FEROL infospace
		d2c.saveFEROLInfoSpaces()

	## For FEROLs, and when changing the size on the fly, get results at the very end
	if len(d2c.config.FEROLs) > 0 and not d2c.config.useEvB and not options.stopRestart: d2c.getResults()

	#####################################
	## Pause GTPe and stop everything
	utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
	print separator
	print ' DONE '
	print separator
	exit(0)

