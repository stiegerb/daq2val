#! /usr/bin/env python
import daq2Utils as utils
from daq2Config import daq2Config
from daq2Control import separator
from daq2SymbolMap import daq2SymbolMap
from sys import stdout

if __name__ == "__main__":
	usage = """

	%prog [options] [config_file]

Reset counters of ferol controllers. Either provide a configuration file
as argument and reset those, or run without arguments and reset everything
in the symbolmap.
	"""
	from optparse import OptionParser
	parser = OptionParser(usage=usage)
	# parser.add_option("-v", "--verbose", default=0,     action="store", type='int', dest="verbose", help="Set the verbose level, [default: %default (quiet)]")
	parser.add_option("--dry",           default=False, action="store_true",        dest="dry",     help="Just print the command without sending anything")
	(options, args) = parser.parse_args()

	d2SM  = daq2SymbolMap()
	print separator

	try:
		## A config was provided, so let's just consider those
		d2Cfg = daq2Config(args[0], verbose=0)
		d2Cfg.fillFromSymbolMap(d2SM)

		for frl in d2Cfg.FEROLs:
			for app,inst in frl.applications:
				stdout.write("%s:%-5d - " % (frl.host, frl.port))
				utils.writeItem(frl.host, frl.port, app, inst, 'RESET_COUNTERS', 1, verbose=0, dry=options.dry)
				if options.dry: stdout.write('\n')

		exit(0)

	except IndexError:
		## Nothing given, so let's reset everything we find in the symbol map

		## Count how many FEROLCONTROLLER's we have in the symbolmap
		ferols = [frl for frl in d2SM.keys() if frl.startswith('FEROLCONTROLLER') and frl.endswith('SOAP_HOST_NAME')]

		for n,frl in enumerate(ferols):
			try:
				frl = d2SM('FEROLCONTROLLER%d'%n)
				stdout.write("%s:%-5d - " % (frl.host, frl.port))
				utils.writeItem(frl.host, frl.port, 'ferol::FerolController', 0, 'RESET_COUNTERS', 1, verbose=0, dry=options.dry)
				if options.dry: stdout.write('\n')
			except KeyError, e:
				print "Something went wrong? FEROLCONTROLLER%d not defined in symbolmap!"%n
				raise e

		exit(0)

	parser.print_help()
	exit(-1)
