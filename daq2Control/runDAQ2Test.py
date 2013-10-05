#! /usr/bin/env python

import daq2Utils as utils
from daq2Control import daq2Control
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import sleep, printError, printWarningWithWait, SIZE_LIMIT_TABLE

separator = 70*'-'

def testBuilding(d2c, minevents=1000, waittime=15):
	if options.verbose > 0: print separator
	if options.verbose > 0: print 'Testing event building for', waittime, 'seconds...'
	sleep(waittime, options.verbose, options.dry)
	if options.dry: return True
	eventCounter = []
	for n,bu in enumerate(d2c.config.BUs):
		if d2c.config.useEvB: nEvts = utils.getParam(bu.host, bu.port, d2c.config.namespace+'BU', str(n), 'nbEventsBuilt', 'xsd:unsignedInt',  verbose=options.verbose, dry=options.dry)
		else:                 nEvts = utils.getParam(bu.host, bu.port, d2c.config.namespace+'BU', str(n), 'eventCounter',  'xsd:unsignedLong', verbose=options.verbose, dry=options.dry)
		try:
			eventCounter.append(int(nEvts))
		except ValueError:
			printError('Error getting number of events built. Message was:\n%s'%nEvts)
			return False
		if options.verbose > 1: print bu.name, 'number of events built: ', int(nEvts)
	print separator

	totEvents = 0
	for evtCount in eventCounter:
		if evtCount < minevents:
			return False
		else:
			totEvents += evtCount
	return True

def getListOfSizes(maxSize, minSize=256):
	stepsize = 256
	allsteps = [ n*stepsize for n in xrange(1, 1000) if n*stepsize <= 8192] ## multiples of stepsize up to 8192
	allsteps += [9216, 10240, 11264, 12288, 13312, 14336, 15360, 16000]
	# if options.short: allsteps = [1024, 16000]
	if options.short: allsteps = [256, 512, 1024, 2048, 3072, 4096, 6144, 8192, 12288, 16000]

	steps = []
	for step in allsteps:
		if step >= minSize and step <= maxSize: steps.append(step)

	print ' Will scan over the following sizes:', steps
	return steps

## Run a single test
def runTest(configfile, fragSize, options, relRMS=0.0):
	"""Usage: runTest(configfile, fragSize)
	Run a test reading the setup from configfile and using fragment size fragSize"""
	d2c = daq2Control(configfile, options)
	d2c.setup()

	utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
	d2c.start(fragSize, relRMS*fragSize, rate=options.useRate)

	if not options.dropAtRU and not testBuilding(d2c, 1000, options.testTime):
		if options.verbose > 0: print 'Test failed, built less than 1000 events!'
		utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
		exit(-1)
	if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'

	if options.verbose > 0: print "Building events for %d seconds..." % options.duration
	if options.useIfstat:
		## Get throughput directly from RU using ifstat script
		d2c.getResultsFromIfstat(options.duration)
	elif d2c.config.useEvB:
		## Get results ala testRubuilder script every 5 seconds
		d2c.getResultsEvB(options.duration, interval=5)
	else:
		## Wait for the full duration, then get all the results at once
		sleep(options.duration,options.verbose,options.dry)
		d2c.getResults()

	if options.waitBeforeStop: raw_input("Press Enter to stop the XDAQs...")

	utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
	print separator
	print ' DONE '
	print separator

## Run a scan over fragment sizes
def runScan(configfile, options, relRMS=-1):
	"""Usage: runScan(configfile, options, relRMS=0.0)
	Run a scan of fragment sizes reading the setup from configfile"""
	d2c = daq2Control(configfile, options)
	d2c.setup()

	steps = getListOfSizes(options.maxSize, minSize=options.minSize)

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
	d2c.start(options.minSize, float(relRMS)*options.minSize, rate=options.useRate)

	if not testBuilding(d2c, 1000, options.testTime):
		if options.verbose > 0: print 'Test failed, built less than 1000 events!'
		utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
		exit(-1)
	if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'

	for step in steps:
		d2c.changeSize(step, float(relRMS)*step, rate=options.useRate)
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

######################################################################
## main
def addOptions(parser):
	usage = """
	%prog [options] --start config.xml fragsize
	%prog [options] --changeSize config.xml newfragsize
	%prog [options] --changeSize config.xml newfragsize relRMS

	%prog [options] --runTest config.xml fragsize
	%prog [options] --runTest config.xml fragsize fragsizerms
	%prog [options] --runScan config.xml
	%prog [options] --runScan config.xml fragsizerms

	%prog [options] --runRMSScan config.xml

	Examples:
	%prog [options] --runTest --duration 30 /nfshome0/mommsen/daq/dev/daq/evb/test/cases/daq2val/FEROLs/16s8fx1x4/configuration.template.xml 1024
	%prog [options] --runTest ~/andrea_test/cases/eFEROLs/gevb2g/dummyFerol/16x2x2/configuration.template.xml 1024 0.5
	%prog [options] --runScan ../cases/FEROLs/gevb2g/16s16fx2x2/configuration.template.xml 2.0
	%prog [options] --runTest --useRate 100 config.template.xml 1024 0.5
	"""
	parser.usage = usage

	## Standard interface:
	parser.add_option("--runTest",        default=False, action="store_true",        dest="runTest",        help="Run a test setup, needs two arguments: config and fragment size")
	parser.add_option("--runScan",        default=False, action="store_true",        dest="runScan",        help="Run a scan over fragment sizes, set the range using the options --maxSize and --minSize")
	parser.add_option("--runMultiScan",   default=False, action="store_true",        dest="runMultiScan",   help="Run scans over a list of configs with common options")
	parser.add_option("--runRMSScan",     default=False, action="store_true",        dest="runRMSScan",     help="Run four scans over fragment sizes with different RMS values")

	parser.add_option("-d", "--duration", default=120,   action="store", type="int", dest="duration",       help="Duration of a single step in seconds, [default: %default s]")
	# parser.add_option("--useLogNormal",   default=False, action="store_true",        dest="useLogNormal",   help="Use lognormal generator for e/FEROLs (will use the dummyFerol instead of the Client in case of the eFEROLS). You need to provide the relative rms (i.e. in multiples of the fragment size) as an argument.")
	parser.add_option("--useRate",        default=0,     action="store", type="int", dest="useRate",        help="Event rate in kHz, [default is maximum rate]")
	parser.add_option("--maxSize",        default=16000, action="store", type="int", dest="maxSize",        help="Maximum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--minSize",        default=256,   action="store", type="int", dest="minSize",        help="Minimum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--short",          default=False, action="store_true",        dest="short",          help="Run a short scan with only a few points")
	parser.add_option("--testTime",       default=10,    action="store", type="int", dest="testTime",       help="Time for which event building is tested before starting, [default is %default]")
	parser.add_option("--stopRestart",    default=True,  action="store_true",        dest="stopRestart",    help="Stop XDAQ processes after each size and restart instead of changing the size on the fly (only relevant for scans)")
	parser.add_option("--dropAtRU",       default=False, action="store_true",        dest="dropAtRU",       help="Run with dropping the fragments at the RU without building. (Use with --useIfstat to get throughput)")
	parser.add_option("--useIfstat",      default=False, action="store_true",        dest="useIfstat",      help="Instead of getting the number of built events from the BU, use ifstat script on the RU to determine throughput")

	## Debugging options:
	parser.add_option("--dry",                  default=False, action="store_true",        dest="dry",            help="Just print the commands without sending anything")
	parser.add_option("-w", "--waitBeforeStop", default=False, action="store_true",        dest="waitBeforeStop", help="For for key press before stopping the event building")
	parser.add_option("-v", "--verbose",        default=1,     action="store", type='int', dest="verbose",        help="Set the verbose level, [default: %default (semi-quiet)]")

	## Control:
	parser.add_option("--start",               default=False, action="store_true", dest="start",      help="Read a config, set up and start running. Needs config, size, optionally rms as arguments.")
	parser.add_option("--changeSize",          default=False, action="store_true", dest="changeSize", help="Halt, change size and resume. Needs config and new size as arguments.")
	parser.add_option("--stop", "--stopXDAQs", default=False, action="store_true", dest="stop",       help="Stop all the XDAQ processes and exit")

	parser.add_option("-m", "--symbolMap", default='', action="store", type="string", dest="symbolMap",      help="Use a symbolmap different from the one set in the environment")

if __name__ == "__main__":
	from optparse import OptionParser
	parser = OptionParser()
	addOptions(parser)
	(options, args) = parser.parse_args()

	if options.useRate == 0: options.useRate = 'max'

	######################
	## --stop
	if options.stop:
		sm = daq2SymbolMap()
		utils.stopXDAQs(sm, verbose=options.verbose, dry=options.dry)
		print separator
		exit(0)

	######################
	## --start
	if options.start and len(args) > 1:
		fragSize = int(args[1])
		if len(args) > 2:
			relRMS = float(args[2])
			options.useLogNormal = True
			options.relRMS = relRMS
		else:
			relRMS = 0
			options.useLogNormal = False
			options.relRMS = None

		d2c = daq2Control(args[0], options)

		## Stop previously running things
		utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)

		d2c.setup()
		d2c.start(fragSize, relRMS*fragSize, rate=options.useRate)

		if not testBuilding(d2c, 1000, options.testTime):
			if options.verbose > 0: print 'Test failed, built less than 1000 events!'
			exit(-1)
		if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'
		exit(0)

	######################
	## --changeSize
	if options.changeSize and len(args) > 1:
		fragSize = int(args[1])
		if len(args) > 2:
			relRMS = float(args[2])
			options.useLogNormal = True
			options.relRMS = relRMS
		else:
			relRMS = 0
			options.useLogNormal = False
			options.relRMS = None

		d2c = daq2Control(args[0], options)
		d2c.changeSize(fragSize, relRMS*fragSize, rate=options.useRate)
		exit(0)

	######################
	## --runTest
	if options.runTest and len(args) > 1:
		fragSize = int(args[1])
		if len(args) > 2:
			relRMS = float(args[2])
			options.useLogNormal = True
			options.relRMS = relRMS
		else:
			relRMS = 0
			options.useLogNormal = False
			options.relRMS = None

		runTest(args[0], fragSize, options, relRMS=relRMS)
		exit(0)

	######################
	## --runScan
	if options.runScan and len(args) > 0:
		if len(args) > 1:
			relRMS = float(args[1])
			options.useLogNormal = True
			options.relRMS = relRMS
		else:
			relRMS = 0
			options.useLogNormal = False
			options.relRMS = None

		runScan(args[0], options, relRMS=relRMS)
		exit(0)

	######################
	## --runMultiScan
	if options.runMultiScan and len(args) > 1:
		configs = []
		try:
			options.relRMS = float(args[-1])
			options.useLogNormal = True
			configs = args[:-1]
		except ValueError:
			options.relRMS = None
			options.useLogNormal = False
			configs = args

		for conf in configs:
			print 80*'#'
			print 80*'#'
			print '## STARTING SCAN OF CONFIG =', conf
			print 80*'#'
			print 80*'#'

			runScan(conf, options, relRMS=options.relRMS)
		print 80*'#'
		print 80*'#'
		print '## EVERYTHING DONE'
		print 80*'#'
		print 80*'#'
		exit(0)

	######################
	## --runRMSScan
	if options.runRMSScan and len(args) > 0:
		config = args[0]
		# options.useLogNormal = True
		rms_values = [0.5, 2.0]
		# rms_values = [0.0, 0.5, 1.0, 2.0]
		for rms in rms_values:
			print 80*'#'
			print 80*'#'
			print '## STARTING SCAN OF RMS =', rms
			print 80*'#'
			print 80*'#'
			options.useLogNormal = True
			options.relRMS       = rms
			runScan(config, options, relRMS=rms)
		print 80*'#'
		print 80*'#'
		print '## EVERYTHING DONE'
		print 80*'#'
		print 80*'#'
		exit(0)

	parser.print_help()
	exit(-1)

