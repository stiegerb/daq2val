#! /usr/bin/env python
from daq2Control import separator
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import stopXDAQs

if __name__ == "__main__":
	from optparse import OptionParser
	usage="""
	%prog [options]
	"""
	parser = OptionParser(usage=usage)
	parser.add_option("-v", "--verbose", default=0,     action="store", type='int', dest="verbose", help="Set the verbose level, [default: %default (quiet)]")
	parser.add_option("--dry",           default=False, action="store_true",        dest="dry",     help="Just print the command without sending anything")
	parser.add_option("-m", "--symbolMap", default='', action="store",
					  type="string", dest="symbolMap",
					  help="Use a symbolmap different from the one set in\
					        the environment")
	(options, args) = parser.parse_args()

	d2SM  = daq2SymbolMap(options.symbolMap)
	stopXDAQs(d2SM, verbose=options.verbose, dry=options.dry)
	print separator
	exit(0)
