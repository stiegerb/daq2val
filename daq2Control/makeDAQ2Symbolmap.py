#! /usr/bin/env python
from pprint import pprint

HEADER = ("LAUNCHER_BASE_PORT 17777\n"
          "SOAP_BASE_PORT 2000\n"
          "I2O_BASE_PORT 54320\n"
          "FRL_BASE_PORT 55320\n")

def getMachines(inventory,splitBy=-1,verbose=False):
	"""
	First take all machines from one switch, then move to the next
	"""
	counter = 0
	for switch in inventory.keys():
		if verbose: print switch
		for device in inventory[switch]:
			if counter == splitBy:
				if verbose: print 'next switch'
				counter = 0
				break
			if verbose: print '   taking', device
			yield device
			counter += 1
		counter = 0
def getMachinesShuffled(inventory):
	"""
	Take one machine from first switch, second from second,
	third from third, etc.
	"""
	maxlength = max([len(_) for _ in inventory.values()])

	for index in xrange(maxlength):
		for switch in inventory.keys():
			try:
				yield inventory[switch][index]
			except IndexError:
				continue

def writeEntry(filehandle, classifier, hostname, index):
	filehandle.write('%s%d_SOAP_HOST_NAME %s.cms\n' %
		                  (classifier, index, hostname))
	filehandle.write('%s%d_I2O_HOST_NAME %s.ebs0v0.cms\n' %
		                  (classifier, index, hostname))

def addDictionaries(original, to_be_added):
	"""
	Adds two dictionaries of key -> list such that
	key -> list1 + list2.
	"""
	newdict = {}
	for key,original_list in original.iteritems():
		try:
			newdict[key] = sorted(list(set(original_list + to_be_added[key])))
		except KeyError:
			print "Could not find key", key, "in second dict"
	return newdict

def getDAQ2Inventory(filename):
	"""
	Reads a file with lines formatted like:
	switch,port,peerDevice,peerPort
	or
	switch,port,peerDevice
	or
	switch,port

	And returns dictionaries formatted like:
	switch : {port: (peerDevice, peerPort)},
	...

	hostname : {(switch, port)}

	Also return two dictionaries for RU's and BU's formatted like:
	switch : [list of connected RU/BU machines]
	"""
	switch_cabling = {} ## switch to port to list of connected devices
	ru_inventory = {} ## switch to list of RUs
	bu_inventory = {} ## switch to list of BUs

	with open(filename, 'r') as infile:
		for line in infile:
			if line.strip().startswith('#') or len(line.strip()) == 0:
				continue

			switch,port,device,dport = ([_.strip() for _ in line.split(',')]
				                                      + [None]*4)[:4]
			if port is not None: port = int(port)
			if dport is not None: dport = int(dport)
			# print switch,port,device,dport

			if not switch in switch_cabling.keys():
				switch_cabling[switch] = {}
			switch_cabling[switch][port] = (device,dport)

			if device is None: continue
			if device.startswith('ru'):
				if not switch in ru_inventory.keys():
					ru_inventory[switch] = []
				ru_inventory[switch].append(device)

			if device.startswith('bu'):
				if not switch in bu_inventory.keys():
					bu_inventory[switch] = []
				bu_inventory[switch].append(device)

	## Get also the inverted dictionary, hostname to switch, port
	host_cabling = {}
	for switch, ports in switch_cabling.iteritems():
		for port, (hostname,_) in ports.iteritems():
			host_cabling[hostname] = (switch, port)


	return switch_cabling, ru_inventory, bu_inventory, host_cabling


if __name__ == "__main__":
	from optparse import OptionParser
	usage = """"""
	parser = OptionParser(usage=usage)
	parser.add_option("-i", "--inventoryFile",
		               default="2014-04-16-infiniband-ports.csv",
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

	switch_cabling, ru_inventory, bu_inventory, _ = getDAQ2Inventory(
		                                              opt.inventoryFile)

	# pprint(ru_inventory)
	# pprint(bu_inventory)

	## Which hosts to choose from:
	full_inventory = ru_inventory
	if not opt.useOnlyRUs:
		full_inventory = addDictionaries(ru_inventory, bu_inventory)

	with open(opt.outFile, 'w') as outfile:
		outfile.write(HEADER)
		outfile.write('\n\n')

		## How to select the hosts:
		allMachines = getMachines(full_inventory,
			                      splitBy=opt.splitBy,
			                      verbose=opt.verbose)
		# RUs = getMachines(ru_inventory)
		# BUs = getMachines(bu_inventory)
		if opt.shuffle:
			allMachines = getMachinesShuffled(full_inventory)
			# RUs = getMachinesShuffled(ru_inventory)
			# BUs = getMachinesShuffled(bu_inventory)

		## Write the symbolmap
		ru_counter, bu_counter = 0,0

		## RUs:
		try:
			for n in range(opt.nRUs):
				writeEntry(outfile, 'RU', allMachines.next(), n)
				ru_counter += 1
			outfile.write('\n')
		except StopIteration:
			print ("Less than %d available RU's in inventory, found "
			       "only %d." %(opt.nRUs, ru_counter))

		## BUs:
		try:
			for n in range(opt.nBUs):
				writeEntry(outfile, 'BU', allMachines.next(), n)
				bu_counter += 1
			outfile.write('\n')
		except StopIteration:
			print ("Less than %d available BU's in inventory, found "
			       "only %d." %(opt.nBUs, bu_counter))

		## EVMs:
		if opt.addEVM:
			try:
				writeEntry(outfile, 'EVM', allMachines.next(), 0)
				outfile.write('\n')
			except StopIteration:
				print ("No machine left for an EVM! Have %d RU's "
					   "and %d BU's already." % (ru_counter, bu_counter))



		outfile.write('\n\n')

	exit(0)




