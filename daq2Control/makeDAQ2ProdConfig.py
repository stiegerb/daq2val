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
	addConfiguratorOptions(parser)
	parser.add_option("--nBUs", default=42, action="store", type="int",
		               dest="nBUs",
		               help=("Number of BUs [default: %default]"))
	parser.add_option("--ibInventoryFile",
		               default="2014-10-15-infiniband-ports.csv",
		               action="store", type="string", dest="ibInventoryFile",
		               help=("IB inventory file [default: %default]"))
	parser.add_option("--geInventoryFile",
		               default="2014-11-03-ru-network.csv",
		               action="store", type="string", dest="geInventoryFile",
		               help=("40 GE inventory file [default: %default]"))
	parser.add_option("--maskGESwitch", default="",
		               action="store", type="string", dest="maskGE",
		               help=("Use only machines from these 40GE switches "
		               	     "[default: use all]"))
	parser.add_option("--maskIBSwitch", default="",
		               action="store", type="string", dest="maskIB",
		               help=("Use only machines from these IB switches "
		               	     "(comma separated list) [default: use all]"))
	parser.add_option("--maskFEDs", default="",
		               action="store", type="string", dest="maskFEDs",
		               help=("Use only these FEDs (comma separated list) "
		               	     "[default: use all]"))
	parser.add_option("--maskRUs", default="",
		               action="store", type="string", dest="maskRUs",
		               help=("Use only these RUs (comma separated list) "
		               	     "[default: use all]"))
	parser.add_option("--maskBUs", default="",
		               action="store", type="string", dest="maskBUs",
		               help=("Use only these BUs (comma separated list) "
		               	     "[default: use all]"))
	parser.add_option("-c", "--canonical", default=False,
		               action="store_true", dest="canonical",
		               help=("Only use exact numbers of FRLs"))
	parser.add_option("-d", "--dry", default=False,
		               action="store_true", dest="dry",
		               help=("Just print the assignments without writing out anything"))
	(opt, args) = parser.parse_args()

	geswitchmask=opt.maskGE.split(',') if len(opt.maskGE) else []
	ibswitchmask=opt.maskIB.split(',') if len(opt.maskIB) else []

	fedwhitelist=[]
	if len(opt.maskFEDs):
		for fragment in opt.maskFEDs.split(','):
			if not '-' in fragment:
				fedwhitelist.append(fragment)
			else:
				start,end = fragment.split('-')
				fedwhitelist += [str(x) for x in range(int(start),int(end))]



	ruwhitelist=opt.maskRUs.split(',') if len(opt.maskRUs) else []
	buwhitelist=opt.maskBUs.split(',') if len(opt.maskBUs) else []
	if buwhitelist:
		opt.nBUs = len(buwhitelist)


	daq2HWInfo = daq2HardwareInfo(gecabling=opt.geInventoryFile,
		                          ibcabling=opt.ibInventoryFile,
                                  geswitchmask=geswitchmask,
                                  ibswitchmask=ibswitchmask,
                                  fedwhitelist=fedwhitelist,
                                  ruwhitelist=ruwhitelist,
                                  buwhitelist=buwhitelist,
                                  canonical=opt.canonical,
		                          verbose=opt.verbose)

	######################################
	## First make the configs
	configurator = daq2ProdConfigurator(opt.fragmentDir, daq2HWInfo,
		                                canonical=opt.canonical,
		                                dry=opt.dry, verbose=opt.verbose)

	os.system('mkdir -p %s' % opt.output)
	configurator.outPutDir = opt.output
	configurator.enablePauseFrame  = opt.enablePauseFrame
	configurator.disablePauseFrame = opt.disablePauseFrame
	configurator.setCorrelatedSeed = opt.setCorrelatedSeed
	configurator.nbus = opt.nBUs
	configurator.evbns = ('gevb2g' if opt.useGevb2g and not
			                          opt.useEvB else 'evb')
	configurator.ptprot = ('udapl' if opt.useUDAPL  and not
			                          opt.useIBV else 'ibv')

	fedbuilders = daq2HWInfo.ge_switch_cabling.keys()
	configurator.makeConfigs(fedbuilders)

	######################################
	## Now make the symbolmap
	if opt.dry: exit(0)
	outputFileName = os.path.join(opt.output, 'daq2Symbolmap.txt')
	with open(outputFileName, 'w') as outfile:
		outfile.write(HEADER)
		outfile.write('\n\n')

		for n,frl in enumerate(configurator.allFEROLs):
			writeEntry(outfile, 'FEROLCONTROLLER', frl.frlpc, n)
		outfile.write('\n')

		for ru in configurator.allRUs:
			writeEntry(outfile, 'RU', ru.hostname, ru.index, addFRLHN=True)
		outfile.write('\n')

		allbus = daq2HWInfo.getAllBUs()
		if opt.nBUs > len(allbus):
			raise RuntimeError("Not enough BUs in inventory")
		for n,bu in enumerate(allbus):
			if n == opt.nBUs: break
			writeEntry(outfile, 'BU', bu, n)
		outfile.write('\n')
		outfile.write('\n\n')

	print "Wrote symbolmap to %s" % (outputFileName)
	print  70*'-'

	exit(0)




