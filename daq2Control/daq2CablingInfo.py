#! /usr/bin/env python
from itertools import cycle

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


######################################################################
class daq2CablingInfo(object):
	'''
---------------------------------------------------------------------
  class daq2CablingInfo

 - Reads and stores information about the network cabling in the
   40GE and IB Clos networks
 - Takes the information from two .csv files (provided by Andre Holzner)
---------------------------------------------------------------------
'''
	def __init__(self, gecabling="2014-10-13-ru-network.csv",
		         ibcabling="2014-10-15-infiniband-ports.csv",
		         geswitchmask="", ibswitchmask="",
		         verbose=0):
		super(daq2CablingInfo, self).__init__()
		self.verbose = verbose
		self.ibswitchmask = ibswitchmask
		self.geswitchmask = geswitchmask
		self.ge_switch_cabling = {} ## ge switch to list of conn. devices
		self.frlpc_cabling = {} ## frlpc to list of ferols
		self.ferol_cabling = {} ## ferol to corresponding frlpc

		self.switch_cabling = {} ## ib switch to port to list of conn. devices
		self.ru_inventory   = {} ## ib switch to list of RUs
		self.bu_inventory   = {} ## ib switch to list of BUs
		self.host_cabling   = {} ## hostname to ib switch, port

		self.missingFEROLS = [] ## ferols with unknown frlpc

		self.readFEDRUCabling(gecabling)
		self.readDAQ2Inventory(ibcabling)

	def readFEDRUCabling(self, csvFname="2014-10-13-ru-network.csv"):
		"""
		Fill dictionaries for:
		   ethswitch -> list of devices (rus, FEROLs)
		   frlpc -> list of FEROLs
		"""

		with open(csvFname, 'r') as infile:
			for line in infile:
				switch,device = line.strip().split(';')

				## Apply mask
				if len(self.geswitchmask):
					if not self.geswitchmask in switch:
						continue

				if not switch in self.ge_switch_cabling:
					self.ge_switch_cabling[switch] = []

				if not 'frlpc' in device and not device.startswith('ru'):
					self.missingFEROLS.append((switch, device))
					if self.verbose>0:
						print "Missing frlpc for:",switch, device
					continue

				spdevice = device.split(',')
				if len(spdevice) == 1 and device.startswith('ru-'):
					self.ge_switch_cabling[switch].append(device)
					continue
				elif len(spdevice) == 3: ## no frlpc?
					name, crate, ferolid = spdevice
				elif len(spdevice) == 4: ## no fedids
					name, crate, ferolid, frlpc = spdevice
				elif len(spdevice) == 5: ## one fedid
					name, crate, ferolid, fedid, frlpc = spdevice
				elif len(spdevice) == 6: ## two fedid
					name, crate, ferolid, fed1id, fed2id, frlpc = spdevice

				if not frlpc in self.ge_switch_cabling[switch]:
					self.ge_switch_cabling[switch].append(frlpc)
				if not frlpc in self.frlpc_cabling:
					self.frlpc_cabling[frlpc] = []
				self.frlpc_cabling[frlpc].append(device)
				self.ferol_cabling[device] = frlpc
		return True

	def readDAQ2Inventory(self, filename):
		"""
		Reads a file with lines formatted like:
		switch,port,peerDevice,peerPort,blacklist,comment
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

		with open(filename, 'r') as infile:
			for line in infile:
				if line.strip().startswith('#') or len(line.strip()) == 0:
					continue

				switch,port,device,dport,blisted,comment = [
				                 _.strip() for _ in line.split(',')]

				## mask switches
				if len(self.ibswitchmask):
					if not self.ibswitchmask in switch: continue

				if port is not '': port = int(port)
				if dport is not '': dport = int(dport)
				if blisted is not '': blisted = bool(int(blisted))
				# print switch,port,device,dport,blisted,comment

				if not switch in self.switch_cabling.keys():
					self.switch_cabling[switch] = {}
				self.switch_cabling[switch][port] = (device,dport)

				if device is None or blisted: continue
				if device.startswith('ru'):
					if not switch in self.ru_inventory.keys():
						self.ru_inventory[switch] = []
					self.ru_inventory[switch].append(device)

				if device.startswith('bu'):
					if not switch in self.bu_inventory.keys():
						self.bu_inventory[switch] = []
					self.bu_inventory[switch].append(device)

		## Get also the inverted dictionary, hostname to switch, port
		for switch, ports in self.switch_cabling.iteritems():
			for port, (hostname,_) in ports.iteritems():
				self.host_cabling[hostname] = (switch, port)

	def getFRLBunches(self, frlpc, bunchBy=4, canonical=False):
		"""
		Return a bunch of FRLs from one frlpc
		"""
		counter = 0
		bunch = []
		for frl in self.frlpc_cabling[frlpc]:
			# print frl
			bunch.append(frl)
			counter += 1
			if counter == bunchBy:
				yield bunch
				bunch = []
				counter = 0
		## Yield the remaining ferols before giving up
		if not canonical:
			if len(bunch) > 0:
				yield bunch
	def getRUs(self, switch):
		"""
		Return a RU on the same ETH switch as the frlpc, as long as there are any
		"""
		allrus = [ru for ru in self.ge_switch_cabling[switch]
		                            if ru.startswith('ru-')]
		for ru in cycle(allrus):
			yield ru
	def getBUs(self, ibswitch, bunchBy=4):
		"""
		Return a bunch of BUs on the same IB switch as the RU, as
		long as there are any
		"""
		counter = 0
		bunch = []
		for bu in cycle(self.bu_inventory[ibswitch]):
			# print bu
			bunch.append(bu)
			counter += 1
			if counter == bunchBy:
				yield bunch
				bunch = []
				counter = 0
	def getListOfFRLPCs(self, ethswitch, canonical=False):
		result = []
		for device in self.ge_switch_cabling[ethswitch]:
			if device.startswith('frlpc-'):
				if canonical and len(self.frlpc_cabling[device]) < 8:
					continue
				result.append(device)
		return result

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










