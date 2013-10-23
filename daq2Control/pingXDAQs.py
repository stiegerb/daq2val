#! /usr/bin/env python
import daq2Utils as utils
from daq2SymbolMap import daq2SymbolMap

if __name__ == "__main__":
	from optparse import OptionParser
	parser = OptionParser()
	(options, args) = parser.parse_args()

	d2SM = daq2SymbolMap()

	for h in d2SM.allHosts:
		utils.tryWebPing(h.host, h.port, verbose=1)
