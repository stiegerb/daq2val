#! /usr/bin/env python
from pprint import pprint
from itertools import cycle
from makeDAQ2Symbolmap import getDAQ2Inventory, addDictionaries, writeEntry
import os


HEADER = ("LAUNCHER_BASE_PORT 17777\n"
          "SOAP_BASE_PORT 2000\n"
          "I2O_BASE_PORT 54320\n"
          "FRL_BASE_PORT 55320\n")

ETHSW2DEVICES = {}
FRLPC2FEROLS = {}
FEROL2FRLPC = {}
IBHOSTCABLING = {}
SW2BUS = {}

def getFRLBunches(frlpc,bunchBy=4,verbose=False):
	"""
	Return a bunch of FRLs from one frlpc
	"""
	counter = 0
	bunch = []
	for frl in FRLPC2FEROLS[frlpc]:
		# print frl
		bunch.append(frl)
		counter += 1
		if counter == bunchBy:
			yield bunch
			bunch = []
			counter = 0
	## Yield the remaining ferols before giving up
	if len(bunch) > 0:
		yield bunch

def getRUs(switch,verbose=False):
	"""
	Return a RU on the same ETH switch as the frlpc, as long as there are any
	"""
	for ru in cycle(ETHSW2DEVICES[switch]):
		if not ru.startswith('ru-'): continue
		yield ru

def getBUs(ibswitch,bunchBy=4,verbose=False):
	"""
	Return a bunch of BUs on the same IB switch as the RU, as long as there are any
	"""
	counter = 0
	bunch = []
	for bu in cycle(SW2BUS[ibswitch]):
		# print bu
		bunch.append(bu)
		counter += 1
		if counter == bunchBy:
			yield bunch
			bunch = []
			counter = 0

def readFEDRUCabling(csvFname="2014-10-13-ru-network.csv",verbose=0):
	"""
	Fill dictionaries for:
	   ethswitch -> list of devices (rus, FEROLs)
	   frlpc -> list of FEROLs
	"""
	missingFEROLS = []
	with open(csvFname, 'r') as infile:
		for line in infile:
			switch,device = line.strip().split(';')
			if not switch in ETHSW2DEVICES:
				ETHSW2DEVICES[switch] = []

			# sw-eth-c2e24-38-01 - TK TEC+,crate S1C07c,FEROL 4,FEDs 287,321,frlpc-s1d06-24-01
			if not 'frlpc' in device and not device.startswith('ru'):
				missingFEROLS.append((switch, device))
				if verbose>0:
					print "Missing frlpc for:",switch, device
				continue

			spdevice = device.split(',')
			if len(spdevice) == 1 and device.startswith('ru-'):
				ETHSW2DEVICES[switch].append(device)
				continue
			elif len(spdevice) == 3: ## no frlpc?
				name, crate, ferolid = spdevice
			elif len(spdevice) == 4: ## no fedids
				name, crate, ferolid, frlpc = spdevice
			elif len(spdevice) == 5: ## one fedid
				name, crate, ferolid, fedid, frlpc = spdevice
			elif len(spdevice) == 6: ## two fedid
				name, crate, ferolid, fed1id, fed2id, frlpc = spdevice

			if not frlpc in ETHSW2DEVICES[switch]:
				ETHSW2DEVICES[switch].append(frlpc)
			if not frlpc in FRLPC2FEROLS:
				FRLPC2FEROLS[frlpc] = []
			FRLPC2FEROLS[frlpc].append(device)
			FEROL2FRLPC[device] = frlpc
	return missingFEROLS

def getListOfFRLPCs(ethswitch):
	result = []
	for device in ETHSW2DEVICES[ethswitch]:
		if device.startswith('frlpc-'):
			result.append(device)
	return result

if __name__ == "__main__":
	from optparse import OptionParser
	usage = """[prog] """
	parser = OptionParser(usage=usage)
	parser.add_option("-i", "--inventoryFile",
		               default="2014-10-15-infiniband-ports.csv",
		               action="store", type="string", dest="inventoryFile",
		               help=("Inventory file [default: %default]"))
	parser.add_option("-o", "--outDir", default="daq2FRLRUBUMaps/",
		               action="store", type="string", dest="outDir",
		               help=("Output directory [default: %default]"))
	parser.add_option("--nBUs", default=2, action="store", type="int",
		               dest="nBUs",
		               help=("Number of BUs [default: %default]"))
	# parser.add_option("--nRUs", default=1, action="store", type="int",
	# 	               dest="nRUs",
	# 	               help=("Number of RUs [default: %default]"))
	parser.add_option("--nFRLs", default=4, action="store", type="int",
		               dest="nFRLs",
		               help=("Number of FRLs [default: %default]"))
	parser.add_option("-v", "--verbose", default=False,
		               action="store_true", dest="verbose",
		               help=("Verbose mode"))
	parser.add_option("-u", "--uniqueOnly", default=False,
		               action="store_true", dest="uniqueOnly",
		               help=("Only write symbolmaps with unique hosts"))
	(opt, args) = parser.parse_args()

	switch_cabling, sw2rus, SW2BUS, IBHOSTCABLING = getDAQ2Inventory(
		                                              opt.inventoryFile)
	missingFEROLs = readFEDRUCabling(verbose=0)

	## Print out what we have
	print  50*'-'
	if opt.verbose:
		for switch in ETHSW2DEVICES.keys():
			print switch
			for frlpc in getListOfFRLPCs(switch):
				print "%s with %2d FEROLs" % (frlpc, len(FRLPC2FEROLS[frlpc]))
			for ru in [ru for ru in ETHSW2DEVICES[switch] if ru.startswith('ru-')]:
				print ru
			print 50*'-'

	symbolMaps = []

	## Generate the FRL - RU - BU links
	bus = dict((ibsw,getBUs(ibsw, bunchBy=opt.nBUs))
		                  for ibsw in switch_cabling.keys())
	rus = dict((ethsw,getRUs(ethsw))
		                  for ethsw in ETHSW2DEVICES.keys())
	frls = dict((frlpc,getFRLBunches(frlpc, bunchBy=opt.nFRLs))
		                  for ethsw in ETHSW2DEVICES.keys()
		                  for frlpc in getListOfFRLPCs(ethsw))

	## loop on eth switches:
	for switch in ETHSW2DEVICES.keys():
		for frlpc in getListOfFRLPCs(switch):
			totalfrls = len(FRLPC2FEROLS[frlpc])
			while(True):
				try:
					frlbunch = frls[frlpc].next()

					try:
						ru = rus[switch].next()

						try:
							bubunch = bus[IBHOSTCABLING[ru][0]].next()
						except StopIteration:
							if opt.verbose:
								print "   Missing %2d FEROLs of %s (out of BUs):" % (totalfrls, frlpc)
							break

					except StopIteration:
						if opt.verbose:
							print "   Missing %2d FEROLs of %s: (out of RUs)" % (totalfrls, frlpc)
						break

				except StopIteration:
					## We covered all the FEROLs
					break

				symbolMaps.append((frlbunch, ru, bubunch))
				totalfrls-=4

	if opt.verbose:
		print "Generated %d symbolmaps" % len(symbolMaps)
		print "Covered %d FEROLs total" % len([x for m in symbolMaps for x in m[0]])
		print "Missing frlpc for %d FEROLs" % len(missingFEROLs)
		print 50*'-'

	## Now write the symbolmaps:
	# create output dir:
	os.system('mkdir -p %s' % opt.outDir)

	usedRUs, usedBUs = [], []
	nMaps = 0
	for frls, ru, bus in symbolMaps:
		if opt.uniqueOnly:
			if ru in usedRUs or len(set(usedBUs).intersection(bus)) > 0:
				continue
			usedRUs.append(ru)
			usedBUs += bus
		nMaps += 1

		outtag = "%s_%s" % (FEROL2FRLPC[frls[0]][6:-3], ru[3:-3])
		outputFile = '%s/daq2Symbolmap_%s.txt' % (opt.outDir, outtag)
		with open(outputFile, 'w') as outfile:
			outfile.write(HEADER)
			outfile.write('\n\n')

			for n,frl in enumerate(frls):
				writeEntry(outfile, 'FEROLCONTROLLER', FEROL2FRLPC[frl], n)
			outfile.write('\n')

			writeEntry(outfile, 'RU', ru, 0, addFRLHN=True)
			outfile.write('\n')

			for n,bu in enumerate(bus):
				writeEntry(outfile, 'BU', bu, n)
			outfile.write('\n')
			outfile.write('\n\n')

	if opt.uniqueOnly:
		print "Wrote %d unique symbolmaps to %s" % (nMaps, opt.outDir)
	else:
		print "Wrote %d symbolmaps to %s" % (nMaps, opt.outDir)
	print  50*'-'

	exit(0)




