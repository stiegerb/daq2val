#! /usr/bin/env python
import daq2Utils as utils
from daq2Control import daq2Control
from runDAQ2Test import addOptions, testBuilding

if __name__ == "__main__":
	from optparse import OptionParser
	parser = OptionParser()
	addOptions(parser)

	parser.add_option("-n", "--numberOfRuns", default=10, type='int', action="store", dest="numberOfRuns", help="Number of runs")

	(options, args) = parser.parse_args()

	if options.useRate == 0: options.useRate = 'max'

	######################
	if len(args) < 2:
		print "Not enough arguments: need to specify at least config and a fragment size."
		exit(-1)

	configfile = args[0]
	fragSize = int(args[1])
	try:
		options.relRMS = float(args[-1])
		options.useLogNormal = True
	except ValueError:
		options.relRMS = None
		options.useLogNormal = False

	######################

	d2c = daq2Control(configfile, options)
	d2c.setup()
	utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)

	d2c.start(fragSize, options.relRMS*fragSize, rate=options.useRate)

	if not options.dropAtRU and not testBuilding(d2c, 1000, options.testTime, verbose=options.verbose, dry=options.dry):
		if options.verbose > 0: print 'Test failed, built less than 1000 events!'
		utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
		exit(-1)
	if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'


	for n in xrange(options.numberOfRuns):
		print 80*'#'
		print '## RUN',n
		print 80*'#'

		utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)
		d2c.start(fragSize, options.relRMS*fragSize, rate=options.useRate)

		if options.verbose > 0: print "Building events for %d seconds..." % options.duration
		if d2c.config.useEvB:
			## Get results ala testRubuilder script every 5 seconds
			d2c.getResultsEvB(options.duration, interval=5)
		else:
			## Wait for the full duration, then get all the results at once
			sleep(options.duration,options.verbose,options.dry)
			d2c.getResults()

		print 70*'-'

	utils.stopXDAQs(d2c.symbolMap, verbose=options.verbose, dry=options.dry)

	print 80*'#'
	print '## EVERYTHING DONE'
	print 80*'#'
	exit(0)
