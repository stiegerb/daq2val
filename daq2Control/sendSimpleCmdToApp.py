#! /usr/bin/env python
from daq2Control import separator
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import sendSimpleCmdToApp, printError

if __name__ == "__main__":
	from optparse import OptionParser
	usage="""
	%prog [options] hostname application instance command

	where hostname is defined in symbolmap
	"""
	parser = OptionParser(usage=usage)
	parser.add_option("-v", "--verbose", default=0,     action="store", type='int', dest="verbose", help="Set the verbose level, [default: %default (quiet)]")
	parser.add_option("--dry",           default=False, action="store_true",        dest="dry",     help="Just print the command without sending anything")
	parser.add_option("-m", "--symbolMap", default='', action="store", type='str', dest="symbolMap", help="Use a custom symbolmap")
	(options, args) = parser.parse_args()

	try:
		if len(options.symbolMap)>0:
			d2SM = daq2SymbolMap(options.symbolMap)
		else:
			d2SM = daq2SymbolMap()

		host = d2SM(args[0])
		classname, instance, command = args[1], int(args[2]), args[3]

		sendSimpleCmdToApp(host.host, host.port, classname, instance, command, verbose=options.verbose, dry=options.dry)
		exit(0)
	except KeyError:
		printError('Host %s not defined in symbolmap!'%args[0])
		exit(-1)
	except IndexError:
		parser.print_help()
		exit(-1)

	parser.print_help()
	exit(-1)

