#! /usr/bin/env python
import daq2Utils as utils
from daq2Control import daq2Control, separator
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import sleep, printError, printWarningWithWait
from daq2Utils import testBuilding, SIZE_LIMIT_TABLE

def getListOfSizes(maxSize, minSize=256, short=False, stepSize=256):
	## multiples of stepsize up to 8192
	#allsteps = [ n*stepSize for n in xrange(1, 1000) if n*stepSize <= maxSize]
	# allsteps = [ n*stepSize for n in xrange(1, 1000) if n*stepSize <= 8192]
	# allsteps += [9216, 10240, 11264, 12288, 13312, 14336, 15360, 16000]
	# allsteps += [9216, 10240, 11264, 12288, 13312, 14336, 15360,
	#              16384, 20480, 24576, 28672, 32500]
	#allsteps = [256, 512, 768, 1024, 1536, 2048, 3072, 4096, 5120, 6144, 7168,
    #            8192, 10240, 12288, 14336, 16384, 17408, 18432, 19456,
    #            20480, 24576, 28672, 32500, 49152, 65000]

	if short:
		allsteps = [256, 1024, 2048, 3072, 4096, 5120, 6144, 8192, 12288, 16384]
	else:
		allsteps = [256, 512, 1024, 1280, 1536, 1792, 2048, 2304, 2560, 2816,
		           3072, 3328, 3584, 3840, 4096, 5120, 6144, 7168, 8192,
		           12288, 14336, 16384]

	steps = []
	for step in allsteps:
		if step >= minSize and step <= maxSize: steps.append(step)

	return steps

def addScanningOptions(parser):
	parser.add_option("--maxSize", default=17000, action="store", type="int",
		               dest="maxSize",
		               help=("Maximum fragment size of a scan in bytes, "
		               	     "[default: %default]"))
	parser.add_option("--minSize", default=256, action="store", type="int",
		               dest="minSize",
		               help=("Minimum fragment size of a scan in bytes, "
		               	     "[default: %default]"))
	parser.add_option("--stepSize", default=256, action="store", type="int",
		               dest="stepSize",
		               help=("Size of each step [default: %default]"))
	parser.add_option("--short", default=False, action="store_true",
		               dest="short",
		               help=("Run a short scan with only a few points"))
	parser.add_option("--sizes", default='', action="store", type="string",
		               dest="sizes",
		               help=("Specify single sizes to be tested "
		               	     "(comma separated list)"))
	parser.add_option("--setEventSize", default=False, action="store_true",
		               dest="setEventSize",
		               help=("Scanning steps are event sizes, not "
		               	     "fragment sizes"))
	parser.add_option("--stopRestart", default=False, action="store_true",
		               dest="stopRestart",
		               help=("Stop XDAQ processes after each step and "
		               	     "restart instead of changing the size on the "
		               	     "fly. [default: %default]"))

def runScan(options, args):
	if options.useRate == 0: options.useRate = 'max'

	#####################################
	## Check input parameters
	if len(args) < 1:
		print ("Not enough arguments: need to specify at least a "
		       "configuration file.")
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
	sm = daq2SymbolMap(options.symbolMap)
	utils.stopXDAQs(sm, verbose=options.verbose, dry=options.dry)
	print separator

	#####################################
	## Set up daq2Control
	d2c = daq2Control(configfile, options)
	d2c.setup()

	#####################################
	## Get the scanning steps
	if not options.sizes:
		steps = getListOfSizes(options.maxSize, minSize=options.minSize,
		                       short=options.short,
		                       stepSize=options.stepSize)
	else:
		steps = [int(x) for x in options.sizes.split(',')]

	# Divide by number of RUs if we want to scan event sizes
	if options.setEventSize:
		steps = [step/len(d2c.config.RUs) for step in steps]
		print ' Will scan over the following event sizes:', steps
	else:
		print ' Will scan over the following fragment sizes:', steps

	#####################################
	## Check maxSize from table and merging case:
	mergingby = d2c.config.nStreams//len(d2c.config.RUs)
	if not utils.checkScanLimit(steps[-1], mergingby):
		message = """
WARNING: Your maximum size for scanning doesn't seem to
         make sense. Please consider!
 Is set to: %d. Expected to scan only until: %d
 		(i.e. use option --maxSize %d)
		""" % (steps[-1], SIZE_LIMIT_TABLE[mergingby][1],
			              SIZE_LIMIT_TABLE[mergingby][1])
		printWarningWithWait(message, waitfunc=sleep, waittime=2)

	#####################################
	## Start the system
	d2c.start(steps[0], float(options.relRMS)*options.minSize,
		      rate=options.useRate)

	#####################################
	## Test event building first
	retries = 0

	if not testBuilding(d2c, 10, options.testTime,
		                verbose=options.verbose,
		                dry=options.dry):
		while(retries < options.retries):
			if options.verbose > 0:
				printWarningWithWait(('Test failed, will stop everything '
									  'and try again.'),
				                     waittime=0, instance=d2c)
			utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose,
				            dry=options.dry)
			d2c.start(options.minSize,
				      float(options.relRMS)*options.minSize,
				      rate=options.useRate)

			## Check again
			if not testBuilding(d2c, 10, options.testTime,
				                verbose=options.verbose,
				                dry=options.dry):
				retries += 1
				continue
			else:
				break
		else:
			## Give up
			if options.verbose > 0:
				printError(('Test failed, built less than 1000 events! '
					        'Giving up.'), instance=d2c)
			utils.stopXDAQs(d2c.symbolMap,
				            verbose=options.verbose,
				            dry=options.dry)
			exit(0)
	## Everything ok
	if options.verbose > 0:
		print ('Test successful (built more than 1000 events in each BU), '
			   'continuing...')

	#####################################
	## Start the scanning
	for step in steps:
		d2c.reset() ## reset retry counter
		d2c.changeSize(step,
			           float(options.relRMS)*step,
			           rate=options.useRate)

		## Test whether the GTPe did start up properly (does not make sense
		## when changing size on the fly):
		if d2c.config.useGTPe and options.stopRestart:
			if not testBuilding(d2c, minevents=5000, waittime=5,
				                verbose=0, dry=options.dry):
				d2c.retry('GTPe does not seem to be running, will stop and '
					      'restart.')
		## Also do a test when running with EvB/inputemulator:
		if (d2c.config.useEvB and
			options.stopRestart):
			if not testBuilding(d2c, minevents=100, waittime=10,
				                verbose=0, dry=options.dry):
				d2c.retry('EvB does not seem to be running, will stop and '
					      'restart.')

		if options.verbose > 0:
			print separator
			print ("Building events at fragment size %d for %d seconds... "
				   "%s" % (step, options.duration,
				   	       d2c.config.configfile))
		if options.useIfstat:
			## NOT REALLY TESTED YET
			## Get throughput directly from RU using ifstat script
			d2c.getResultsFromIfstat(options.duration)
		elif d2c.config.useEvB:
			d2c.getResultsEvB(options.duration, interval=5)
		else:
			## Wait for the full duration and get results at the end
			sleep(options.duration, options.verbose, options.dry)
			## For eFEROLs, or when stopping and restarting after each step,
			## get results after each step
			if len(d2c.config.eFEROLs) > 0 or options.stopRestart:
				d2c.getResults()
		if options.verbose > 0: print "Done"

		# Dump FEROL infospace
		if options.storeInfoSpaces: d2c.saveFEROLInfoSpaces()

	## For FEROLs, and when changing the size on the fly,
	## get results at the very end
	if (len(d2c.config.FEROLs) > 0 and not
		         d2c.config.useEvB and not
		         options.stopRestart):
		d2c.getResults()

	#####################################
	## Pause GTPe and stop everything
	utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
	print separator
	print ' DONE '
	print separator
	return True

if __name__ == "__main__":
	from optparse import OptionParser
	from runDAQ2Test import addOptions, testBuilding
	usage = """
	%prog [options] config.xml relRMS

	Examples:
	%prog config.xml
	%prog --short --maxSize 8192 --duration 300 --useRate 100 config.xml 0.0
	"""
	parser = OptionParser(usage=usage)
	addOptions(parser)
	addScanningOptions(parser)

	(options, args) = parser.parse_args()

	if not runScan(options, args):
		parser.print_help()
		exit(-1)

	exit(0)
