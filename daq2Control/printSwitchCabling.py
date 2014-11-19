#! /usr/bin/env python
from daq2HardwareInfo import daq2HardwareInfo
from daq2SymbolMap import daq2SymbolMap
from pprint import pprint

if __name__ == "__main__":
	from optparse import OptionParser
	usage = """"""
	parser = OptionParser(usage=usage)
	(opt, args) = parser.parse_args()

	hwInfo = daq2HardwareInfo()

	list_of_hosts = []

	sm = daq2SymbolMap(args[0])
	print 80*'-'
	for key in sorted(sm.keys()):
		if not 'SOAP_HOST_NAME' in key: continue
		if 'FEROLCONTROLLER' in key: continue ## exclude 40GE now
		tag = key.split('_',1)[0]
		switchname,port = hwInfo.ib_host_cabling[sm(key).strip('.cms')]
		list_of_hosts.append((port, tag, sm(key).strip('.cms')))

	for switch in hwInfo.ib_switch_cabling.keys():
		switch_hosts = [host for host,_ in
		                        hwInfo.ib_switch_cabling[switch].values()]
		print switch
		for port,tag,host in list_of_hosts:
			if host in switch_hosts:
				print '    %2d: %-17s %14s' % (port, tag, host)

	list_of_hosts = []
	print 80*'-'
	for key in sorted(sm.keys()):
		if not 'SOAP_HOST_NAME' in key: continue
		if 'BU' in key: continue ## exclude IB
		tag = key.split('_',1)[0]
		switchname = hwInfo.ge_host_cabling[sm(key).strip('.cms')]
		list_of_hosts.append((tag, sm(key).strip('.cms')))

	for switch in hwInfo.ge_switch_cabling.keys():
		switch_hosts = [host for host in
		                        hwInfo.ge_switch_cabling[switch]]
		print switch
		for tag,host in list_of_hosts:
			if host in switch_hosts:
				print '      : %-17s %14s' % (tag, host)
	print 80*'-'

	exit(0)
