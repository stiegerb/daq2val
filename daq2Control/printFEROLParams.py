#! /usr/bin/env python
import daq2Utils as utils
from daq2SymbolMap import daq2SymbolMap
from daq2Config import daq2Config

if __name__ == "__main__":
	from optparse import OptionParser
	parser = OptionParser()
	(options, args) = parser.parse_args()

	d2SM = daq2SymbolMap('/nfshome0/stiegerb/cmsosrad/trunk/daq/benchmark/test/daq2valSymbolMap-COL.txt')
	d2Cfg = daq2Config('/nfshome0/stiegerb/cmsosrad/trunk/daq/benchmark/test/cases/FEROLs/GTPe/EvB/eFED/16s8fx1x4/configuration.template.xml', verbose=1)
	d2Cfg.fillFromSymbolMap(d2SM)

	keys = [str(k) for k in args]

	for frl in d2Cfg.FEROLs:
		url = 'http://%s:%d/urn:xdaq-application:lid=109' % (frl.host, frl.port)
		items = utils.loadMonitoringItemsFromURL(url)
		values = [items[key] for key in keys]
		print frl.name, values
