#! /usr/bin/env python
from daq2HardwareInfo import daq2HardwareInfo
from makeDAQ2Config import addConfiguratorOptions
from daq2ProdConfigurator import daq2ProdConfigurator

from makeDAQ2Symbolmap import writeEntry
import os


HEADER = ("LAUNCHER_BASE_PORT 17777\n"
          "SOAP_BASE_PORT 2000\n"
          "I2O_BASE_PORT 54320\n"
          "FRL_BASE_PORT 55320\n")

if __name__ == "__main__":
	from optparse import OptionParser
	usage = """[prog] """
	parser = OptionParser(usage=usage)
	# parser.add_option("-o", "--outDir", default="daq2FRLRUBUMaps/",
	# 	               action="store", type="string", dest="outDir",
	# 	               help=("Output directory [default: %default]"))
	parser.add_option("--nBUs", default=42, action="store", type="int",
		               dest="nBUs",
		               help=("Number of BUs [default: %default]"))
	# # parser.add_option("--nRUs", default=1, action="store", type="int",
	# # 	               dest="nRUs",
	# # 	               help=("Number of RUs [default: %default]"))
	# parser.add_option("--nFRLs", default=4, action="store", type="int",
	# 	               dest="nFRLs",
	# 	               help=("Number of FRLs [default: %default]"))
	addConfiguratorOptions(parser)
	parser.add_option("--ibInventoryFile",
		               default="2014-10-15-infiniband-ports.csv",
		               action="store", type="string", dest="ibInventoryFile",
		               help=("IB inventory file [default: %default]"))
	parser.add_option("--geInventoryFile",
		               default="2014-10-13-ru-network.csv",
		               action="store", type="string", dest="geInventoryFile",
		               help=("40 GE inventory file [default: %default]"))
	parser.add_option("--whiteListGESwitch", default="",
		               action="store", type="string", dest="whiteListGE",
		               help=("Use only machines from these 40GE switches "
		               	     "[default: use all]"))
	parser.add_option("--whiteListIBSwitch", default="",
		               action="store", type="string", dest="whiteListIB",
		               help=("Use only machines from these IB switches "
		               	     "[default: use all]"))
	parser.add_option("-c", "--canonical", default=False,
		               action="store_true", dest="canonical",
		               help=("Only use exact numbers of FRLs"))
	(opt, args) = parser.parse_args()

	daq2HWInfo = daq2HardwareInfo(gecabling=opt.geInventoryFile,
		                          ibcabling=opt.ibInventoryFile,
                                  geswitchmask=opt.whiteListGE,
                                  ibswitchmask=opt.whiteListIB,
		                          verbose=0)

	## Print out what we have
	# print  50*'-'
	# if opt.verbose:
	# 	for switch in daq2HWInfo.ge_switch_cabling.keys():
	# 		print switch
	# 		for frlpc in daq2HWInfo.getListOfFRLPCs(switch,
	# 			                                    canonical=opt.canonical):
	# 			print "%s with %2d FEROLs" % (frlpc,
	# 				                 len(daq2HWInfo.frlpc_cabling[frlpc]))
	# 		for ru in [ru for ru in daq2HWInfo.ge_switch_cabling[switch]
	# 		                              if ru.startswith('ru-')]:
	# 			print ru
	# 		print 50*'-'

	configurator = daq2ProdConfigurator(opt.fragmentDir,
		                                daq2HWInfo, opt.verbose)

	os.system('mkdir -p %s' % opt.output)
	configurator.outPutDir = opt.output
	configurator.enablePauseFrame = opt.enablePauseFrame
	configurator.disablePauseFrame = opt.disablePauseFrame
	configurator.setCorrelatedSeed = opt.setCorrelatedSeed
	configurator.nbus = opt.nBUs
	configurator.evbns = ('gevb2g' if opt.useGevb2g and not
			                          opt.useEvB else 'evb')
	configurator.ptprot = ('udapl' if opt.useUDAPL  and not
			                          opt.useIBV else 'ibv')

	configurator.makeSplitConfigs(daq2HWInfo.ge_switch_cabling.keys())
	# configurator.makeSplitConfigs(['sw-eth-c2e23-20-01', 'sw-eth-c2e24-38-01'])
	# configurator.makeSplitConfigs(['sw-eth-c2e23-20-01'])

	exit(0)



	# symbolMaps = []

	# ## Generate the FRL - RU - BU links
	# bus = dict((ibsw,daq2HWInfo.getBUs(ibsw, bunchBy=opt.nBUs))
	# 	                  for ibsw in daq2HWInfo.ib_switch_cabling.keys())
	# rus = dict((ethsw,daq2HWInfo.getRUs(ethsw))
	# 	                  for ethsw in daq2HWInfo.ge_switch_cabling.keys())
	# frls = dict((frlpc,daq2HWInfo.getFRLBunches(frlpc, bunchBy=opt.nFRLs,
	# 	         canonical=opt.canonical))
	# 	                  for ethsw in daq2HWInfo.ge_switch_cabling.keys()
	# 	                  for frlpc in daq2HWInfo.getListOfFRLPCs(ethsw,
	# 	                  	                    canonical=opt.canonical))

	# ## loop on eth switches:
	# for switch in daq2HWInfo.ge_switch_cabling.keys():
	# 	for frlpc in daq2HWInfo.getListOfFRLPCs(switch,
	# 		                                    canonical=opt.canonical):
	# 		totalfrls = len(daq2HWInfo.frlpc_cabling[frlpc])
	# 		while(True):
	# 			try:
	# 				frlbunch = frls[frlpc].next()
	# 				if opt.canonical and len(frlbunch) != opt.nFRLs:
	# 					print "Mooooooep"
	# 				try:
	# 					ru = rus[switch].next()

	# 					try:
	# 						bubunch = bus[daq2HWInfo.ib_host_cabling[ru][0]].next()
	# 					except StopIteration:
	# 						if opt.verbose:
	# 							print ("   Missing %2d FEROLs of %s "
	# 								   "(out of BUs):" % (totalfrls, frlpc))
	# 						break

	# 				except StopIteration:
	# 					if opt.verbose:
	# 						print ("   Missing %2d FEROLs of %s: "
	# 							   "(out of RUs)" % (totalfrls, frlpc))
	# 					break

	# 			except StopIteration:
	# 				## We covered all the FEROLs
	# 				break

	# 			symbolMaps.append((frlbunch, ru, bubunch))
	# 			totalfrls-=4

	# if opt.verbose:
	# 	print "Generated %d symbolmaps" % len(symbolMaps)
	# 	print "Covered %d FEROLs total" % len([x for m in symbolMaps
	# 		                                          for x in m[0]])
	# 	print "Missing frlpc for %d FEROLs" % len(daq2HWInfo.missingFEROLs)
	# 	print 50*'-'

	# ## Now write the symbolmaps:
	# # create output dir:
	# os.system('mkdir -p %s' % opt.outDir)

	# usedRUs, usedBUs = [], []
	# nMaps = 0
	# for frls, ru, bus in symbolMaps:
	# 	if opt.uniqueOnly:
	# 		if ru in usedRUs or len(set(usedBUs).intersection(bus)) > 0:
	# 			continue
	# 		usedRUs.append(ru)
	# 		usedBUs += bus
	# 	nMaps += 1

	# 	outtag = "%s_%s" % (frls[0].crate.lower(), ru[3:-3])
	# 	outputFile = '%s/daq2Symbolmap_%s.txt' % (opt.outDir, outtag)
	# 	with open(outputFile, 'w') as outfile:
	# 		outfile.write(HEADER)
	# 		outfile.write('\n\n')

	# 		for n,frl in enumerate(frls):
	# 			writeEntry(outfile, 'FEROLCONTROLLER', frl.frlpc, n)
	# 		outfile.write('\n')

	# 		writeEntry(outfile, 'RU', ru, 0, addFRLHN=True)
	# 		outfile.write('\n')

	# 		for n,bu in enumerate(bus):
	# 			writeEntry(outfile, 'BU', bu, n)
	# 		outfile.write('\n')
	# 		outfile.write('\n\n')

	# if opt.uniqueOnly:
	# 	print "Wrote %d unique symbolmaps to %s" % (nMaps, opt.outDir)
	# else:
	# 	print "Wrote %d symbolmaps to %s" % (nMaps, opt.outDir)
	# print  50*'-'

	# exit(0)




