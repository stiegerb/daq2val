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

	switch_cabling,_,_,host_cabling = getDAQ2Inventory(opt.inventoryFile)

	# pprint(switch_cabling)

	list_of_hosts = []

	sm = daq2SymbolMap(args[0])
	for key in sorted(sm.keys()):
		if not 'SOAP_HOST_NAME' in key: continue
		tag = key.split('_',1)[0]
		switchname,port = host_cabling[sm(key).strip('.cms')]
		# print "%5s, %18s, %17s, %2d" % (tag,  sm(key), switchname, port)
		list_of_hosts.append((port, tag, sm(key).strip('.cms')))

	for switch in switch_cabling.keys():
		switch_hosts = [host for host,_ in switch_cabling[switch].values()]
		print switch
		for port,tag,host in list_of_hosts:
			if host in switch_hosts:
				print '    %2d: %5s %14s' % (port, tag, host)

	exit(0)
