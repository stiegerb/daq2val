#! /usr/bin/env python
from makeDAQ2Symbolmap import getDAQ2Inventory
from daq2SymbolMap import daq2SymbolMap
from pprint import pprint


if __name__ == "__main__":
	from optparse import OptionParser
	usage = """"""
	parser = OptionParser(usage=usage)
	parser.add_option("-i", "--inventoryFile",
		               default="2014-04-16-infiniband-ports.csv",
		               action="store", type="string", dest="inventoryFile",
		               help=("Inventory file [default: %default]"))
	(opt, args) = parser.parse_args()

	_,_,_,host_cabling = getDAQ2Inventory(opt.inventoryFile)

	sm = daq2SymbolMap(args[0])
	for key in sorted(sm.keys()):
		if not 'SOAP_HOST_NAME' in key: continue
		tag = key.split('_',1)[0]
		print tag, sm(key), host_cabling[sm(key).strip('.cms')]


	exit(0)
