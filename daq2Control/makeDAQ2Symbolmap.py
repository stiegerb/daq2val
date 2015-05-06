#! /usr/bin/env python
from pprint import pprint
from daq2HardwareInfo import daq2HardwareInfo, addDictionaries
from daq2HardwareInfo import getMachines, getMachinesShuffled

HEADER = ("LAUNCHER_BASE_PORT 17777\n"
          "SOAP_BASE_PORT 2000\n"
          "I2O_BASE_PORT 54320\n"
          "FRL_BASE_PORT 55320\n")

def writeEntry(filehandle, classifier, hostname, index, addFRLHN=False):
	filehandle.write('%s%d_SOAP_HOST_NAME %s.cms\n' %
		                  (classifier, index, hostname))
	filehandle.write('%s%d_I2O_HOST_NAME %s.ebs0v0.cms\n' %
		                  (classifier, index, hostname))
	if addFRLHN:
		filehandle.write('%s%d_FRL_HOST_NAME %s.fbs0v0.cms\n' %
			                  (classifier, index, hostname))

if __name__ == "__main__":
	from optparse import OptionParser
	usage = """"""
	parser = OptionParser(usage=usage)
	parser.add_option("-i", "--inventoryFile",
		               default="2015-05-05-infiniband-ports.csv",
		               action="store", type="string", dest="inventoryFile",
		               help=("Inventory file [default: %default]"))
	parser.add_option("-o", "--outFile", default="customSymbolmap.txt",
		               action="store", type="string", dest="outFile",
		               help=("Output file [default: %default]"))
	parser.add_option("--splitBy", default=-1,
		               action="store", type="int", dest="splitBy",
		               help=("Take only N machines from a switch before "
		               	     "moving to the next switch. [default: %default "
		               	     "(no splitting)]"))
	parser.add_option("-s", "--switch", default="",
		               action="store", type="string", dest="switch",
		               help=("Use only machines from this switch "
		               	     "[default: use all]"))
	parser.add_option("--nRUs", default=4,
		               action="store", type="int", dest="nRUs",
		               help=("Number of RUs [default: %default]"))
	parser.add_option("--nBUs", default=4,
		               action="store", type="int", dest="nBUs",
		               help=("Number of BUs [default: %default]"))
	parser.add_option("--addEVM", default=False,
		               action="store_true", dest="addEVM",
		               help=("Add an EVM machine"))
	parser.add_option("--useOnlyRUs", default=False,
		               action="store_true", dest="useOnlyRUs",
		               help=("Only consider RU machines"))
	parser.add_option("--shuffle", default=False,
		               action="store_true", dest="shuffle",
		               help=("Shuffle machines between switches"))
	parser.add_option("-v", "--verbose", default=False,
		               action="store_true", dest="verbose",
		               help=("Verbose mode"))
	(opt, args) = parser.parse_args()

	switchmask = []
	if len(opt.switch):
		switchmask = opt.switch.split(',')
	hwInfo = daq2HardwareInfo(ibcabling=opt.inventoryFile,
		                      ibswitchmask=switchmask,
		                      verbose=opt.verbose)

	# switch_cabling, ru_inventory, bu_inventory, _ = getDAQ2Inventory(
	# 	                                              opt.inventoryFile,
	# 	                                              onlySwitch=opt.switch)

	# pprint(ru_inventory)
	# pprint(bu_inventory)

	## Which hosts to choose from:
	# full_inventory = ru_inventory
	# if not opt.useOnlyRUs:
	# 	full_inventory = addDictionaries(ru_inventory, bu_inventory)

	with open(opt.outFile, 'w') as outfile:
		outfile.write(HEADER)
		outfile.write('\n\n')

		## How to select the hosts:
		# allMachines = getMachines(full_inventory,
		# 	                      splitBy=opt.splitBy,
		# 	                      verbose=opt.verbose)
		RUs = getMachines(hwInfo.ru_inventory)
		BUs = getMachines(hwInfo.bu_inventory)
		if opt.shuffle:
			# allMachines = getMachinesShuffled(full_inventory)
			RUs = getMachinesShuffled(hwInfo.ru_inventory)
			BUs = getMachinesShuffled(hwInfo.bu_inventory)

		## Write the symbolmap
		ru_counter, bu_counter = 0,0

		## RUs:
		try:
			for n in range(opt.nRUs):
				writeEntry(outfile, 'RU', RUs.next(), n)
				# writeEntry(outfile, 'RU', allMachines.next(), n)
				ru_counter += 1
			outfile.write('\n')
		except StopIteration:
			print ("Less than %d available RU's in inventory, found "
			       "only %d." %(opt.nRUs, ru_counter))

		## BUs:
		try:
			for n in range(opt.nBUs):
				writeEntry(outfile, 'BU', BUs.next(), n)
				# writeEntry(outfile, 'BU', allMachines.next(), n)
				bu_counter += 1
			outfile.write('\n')
		except StopIteration:
			print ("Less than %d available BU's in inventory, found "
			       "only %d." %(opt.nBUs, bu_counter))

		## EVMs:
		if opt.addEVM:
			try:
				writeEntry(outfile, 'EVM', RUs.next(), 0)
				# writeEntry(outfile, 'EVM', allMachines.next(), 0)
				outfile.write('\n')
			except StopIteration:
				print ("No machine left for an EVM! Have %d RU's "
					   "and %d BU's already." % (ru_counter, bu_counter))



		outfile.write('\n\n')
	print "Wrote symbolmap to", opt.outFile

	exit(0)
