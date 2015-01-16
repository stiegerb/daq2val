#! /usr/bin/env python

import daq2Utils as utils
from daq2Control import daq2Control
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import sleep, printError, printWarningWithWait
from daq2Utils import testBuilding, SIZE_LIMIT_TABLE

separator = 70*'-'

## Run a single test
def runTest(configfile, fragSize, options, relRMS=0.0):
	d2c = daq2Control(configfile, options)
	d2c.setup()

	utils.stopXDAQs(d2c.symbolMap,
		            verbose=options.verbose,
	                dry=options.dry)
	d2c.start(fragSize, relRMS*fragSize, rate=options.useRate)

	if not testBuilding(d2c, 1000, options.testTime,
		                verbose=options.verbose,
		                dry=options.dry):
		if options.verbose > 0:
			print 'Test failed, built less than 1000 events!'
		utils.stopXDAQs(d2c.symbolMap,
			            verbose=options.verbose,
		                dry=options.dry)
		exit(-1)
	if options.verbose > 0:
		print ('Test successful (built more than 1000 events '
			   'in each BU), continuing...')

	if options.verbose > 0:
		print "Building events for %d seconds..." % options.duration
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
	if options.storeInfoSpaces: d2c.saveFEROLInfoSpaces()
	if options.waitBeforeStop: raw_input("Press Enter to stop the XDAQs...")

	utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
	print separator
	print ' DONE '
	print separator


######################################################################
## main
def addOptions(parser):
	## Common options:
	parser.add_option("-d", "--duration", default=120, action="store",
	                  type="int", dest="duration",
	                  help="Duration of a single step in seconds,\
	                        [default: %default s]")
	parser.add_option("--useRate", default=0, action="store",
	                  type="float", dest="useRate",
	                  help="Event rate in kHz, [default is maximum rate]")
	parser.add_option("--testTime", default=10, action="store",
	                  type="int", dest="testTime",
	                  help="Time for which event building is tested before\
	                        starting, [default is %default]")
	# parser.add_option("--dropAtRU", default=False, action="store_true",
	# 	              dest="dropAtRU",
	# 	              help="Run with dropping the fragments at the RU\
	# 	                    without building. (Use with --useIfstat to get\
	# 	                    throughput)")
	parser.add_option("--useIfstat", default=False, action="store_true",
		              dest="useIfstat",
		              help="Instead of getting the number of\
		                    built events from the BU, use ifstat \
		                    script on the RU to determine throughput.\
		                    This uses ssh, so be sure to have a\
		                    kerberos token (kinit).")
	parser.add_option("--retries", default=10, action="store", type="int",
		              dest="retries",
		              help="Number of retries when things go wrong.")

	parser.add_option("--sizeFile", default='fedFragmentSizes.csv',
		              action="store", type='string', dest="sizeFile",
		              help=("File from which to take individual sizes. Only "
		                    "relevant with --sizeFromFile option."))
	parser.add_option("--sizeProfile", default='flat',action="store",
					  type='string', dest="sizeProfile",
		              help=("Use different sizes for different streams, can"
		                    "be either 'flat', 'spike', 'sawtooth', "
		                    "'doublespike', or 'file'. In case of 'file' the"
		                    " sizes are taken from a file that is a comma-"
		                    "separated list of fedID,size,sigma,... The "
		                    "filename is taken from the --sizeFile option. "
		                    "Note that the individual sizes are scaled to "
		                    "be the given fragment size on average."))
	parser.add_option("--profilePerFRL", default=False, action="store_true",
		              dest="profilePerFRL",
		              help="Apply the chosen size profile per FEROL instead\
		                    of over all FEROLs")

	parser.add_option("-m", "--symbolMap", default='', action="store",
					  type="string", dest="symbolMap",
					  help="Use a symbolmap different from the one set in\
					        the environment")
	parser.add_option("-o", "--outputDir", default='', action="store",
					  type="string", dest="outputDir",
					  help="Where to store the output. Default is in\
					        test/cases/[e]FEROLs/EvB[gevb2g]/casename")
	parser.add_option("-t", "--outputTag", default='', action="store",
		              type="string", dest="outputTag",
		              help="Attach a tag after the standard output dir")

	## Debugging options:
	parser.add_option("--dry", default=False,
		              action="store_true", dest="dry",
		              help=("Just print the commands without "
		              	    "sending anything"))
	parser.add_option("--storeInfoSpaces", default=False,
		              action="store_true",
		              dest="storeInfoSpaces",
		              help="Dump the FEROL infospaces.")
	parser.add_option("-w", "--waitBeforeStop", default=False,
		              action="store_true", dest="waitBeforeStop",
		              help=("Wait for key press before stopping the "
		              	    "event building"))
	parser.add_option("-v", "--verbose", default=1, action="store",
		              type='int', dest="verbose",
		              help=("Set the verbose level, "
		              	    "[default: %default (semi-quiet)]"))

	parser.add_option("--maskHost", default=None, action="store",
					  type="string", dest="maskHost",
					  help=("Don't start xdaq application on this host. "
					        "I.e. will do it manually there to debug."))

	parser.add_option("--setCWND", default=-1, action="store", type='int',
		              dest="setCWND",
		              help=("Set the TCP_CWND_FEDX parameter in the FEROL "
		              	    "config, overriding the configuration file "
		              	    "[default: %default]"))
	parser.add_option("--disablePauseFrame", default=False,
		              action="store_true", dest="disablePauseFrame",
		              help=("Set the ENA_PAUSE_FRAME parameter in the FEROL "
		              	    "config to 'false', overriding the "
		              	    "configuration file"))
	parser.add_option("--enablePauseFrame", default=False,
		              action="store_true", dest="enablePauseFrame",
		              help=("Set the ENA_PAUSE_FRAME parameter in the FEROL "
		              	"config to 'true', overriding the "
		              	"configuration file"))

def setCurrentSizeFromArgs(d2c, args, options):
	if len(args) > 1: ## if given, set also fragsize and relRMS
		fragSize = int(args[1])
		if len(args) > 2:
			relRMS = float(args[2])
			options.useLogNormal = True
			options.relRMS = relRMS
		else:
			relRMS = 0
			options.useLogNormal = False
			options.relRMS = None

		d2c.currentFragSize    = fragSize
		d2c.currentFragSizeRMS = int(relRMS*fragSize)
		d2c.currentRate        = options.useRate
	return


if __name__ == "__main__":
	from optparse import OptionParser
	usage = """
	%prog [options] --start config.xml fragsize
	%prog [options] --start config.xml fragsize --sizeProfile file
	%prog [options] --changeSize config.xml newfragsize
	%prog [options] --changeSize config.xml newfragsize relRMS

	%prog [options] --runTest config.xml fragsize
	%prog [options] --runTest config.xml fragsize fragsizerms

	%prog [options] --start configdir/ fragsize fragsizerms

	Examples:
	%prog [options] --runTest --duration 30 config.xml 1024
	%prog [options] --start --useRate 100 config.xml 1024 0.5
	"""
	parser = OptionParser()
	parser.usage = usage
	addOptions(parser)
	parser.add_option("--runTest", default=False, action="store_true",
		               dest="runTest",
		               help=("Run a test setup, needs two arguments: "
		               	     "config and fragment size"))
	parser.add_option("--start", default=False, action="store_true",
		               dest="start",
		               help=("Read a config, set up and start running. Needs"
		               	     " config, size, optionally rms as arguments."))
	parser.add_option("--changeSize", default=False, action="store_true",
		               dest="changeSize",
		               help=("Halt, change size and resume. Needs config "
		               	     "and new size as arguments."))
	parser.add_option("--kill", default=False, action="store_true",
		               dest="kill",
		               help=("Kill all the XDAQ processes and exit"))
	parser.add_option("--stop", default=False, action="store_true",
		               dest="stop",
		               help=("Stop all applications, should reach "
		               	     "'Configured' state."))
	parser.add_option("--test", default=False, action="store_true",
		               dest="test",
		               help=("Test event building. Use --testTime option "
		               	     "to set duration."))
	parser.add_option("--configure", default=False, action="store_true",
		               dest="configure",
		               help=("Configure"))
	parser.add_option("--enable", default=False, action="store_true",
		               dest="enable",
		               help=("Enable"))
	parser.add_option("--prepare", default=False, action="store_true",
		               dest="prepare",
		               help=("Start XDAQ processes, send configuration "
		               	     "files, set size and run number, but don't "
		               	     "configure and enable"))
	(options, args) = parser.parse_args()

	if options.useRate == 0: options.useRate = 'max'

	######################
	## --test
	if options.test and len(args)>0:
		d2c = daq2Control(args[0], options)
		testBuilding(d2c, 1000, options.testTime,
			         verbose=options.verbose,
			         dry=options.dry)
		exit(0)

	######################
	## --kill
	if options.kill:
		d2SM  = daq2SymbolMap(options.symbolMap)
		utils.stopXDAQs(d2SM, verbose=options.verbose,
			                  dry=options.dry)
		exit(0)

	######################
	## --stop
	if options.stop and len(args) > 1:
		d2c = daq2Control(args[0], options)
		d2c.stop()
		exit(0)

	######################
	## --prepare
	if options.prepare and len(args) > 1:
		d2c = daq2Control(args[0], options)
		fragSize = int(args[1])
		if len(args) > 2:
			relRMS = float(args[2])
			options.useLogNormal = True
			options.relRMS = relRMS
		else:
			relRMS = 0
			options.useLogNormal = False
			options.relRMS = None

		d2c.currentFragSize    = fragSize
		d2c.currentFragSizeRMS = int(relRMS*fragSize)
		d2c.currentRate        = options.useRate

		## Stop previously running things
		utils.stopXDAQs(d2c.symbolMap,
			            verbose=options.verbose,
			            dry=options.dry)

		d2c.setup()
		d2c.start(fragSize, relRMS*fragSize,
			      rate=options.useRate,
			      onlyPrepare=True)
		exit(0)

	######################
	## --configure
	if options.configure and len(args) > 0:
		d2c = daq2Control(args[0], options)
		setCurrentSizeFromArgs(d2c, args, options)
		d2c.configure()
		exit(0)

	######################
	## --enable
	if options.enable and len(args) > 0:
		d2c = daq2Control(args[0], options)
		setCurrentSizeFromArgs(d2c, args, options)
		d2c.enable()
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
		utils.stopXDAQs(d2c.symbolMap,
			            verbose=options.verbose,
			            dry=options.dry)

		d2c.setup()
		d2c.start(fragSize, relRMS*fragSize,
			      rate=options.useRate)

		if not testBuilding(d2c, 1000, options.testTime,
			                verbose=options.verbose,
			                dry=options.dry):
			if options.verbose > 0:
				print 'Test failed, built less than 1000 events!'
			exit(-1)
		if options.verbose > 0:
			print ('Test successful (built more than 1000 '
				   'events in each BU), continuing...')
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
		d2c.changeSize(fragSize, relRMS*fragSize,
			           rate=options.useRate)
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

	parser.print_help()
	exit(-1)

