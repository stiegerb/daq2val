from itertools import cycle
from pprint import pprint
from daq2Utils import printError

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
class FEROL(object):
	def __init__(self, frlpc, slot, fedIds, system, crate, switch):
		self.frlpc      = frlpc
		self.slotNumber = int(slot)
		self.fedIds = fedIds
		self.system = system
		self.crate  = crate
		self.switch = switch
		self.sourceIp = None
		self.nstreams = 0

		fed1, fed2 = fedIds
		if fed1: self.nstreams = 1
		if fed2: self.nstreams = 2
		self.ruindex = -1
		self.runame  = ''
		self.index = -1

	def __str__(self):
		fedstring = '          '
		if self.nstreams == 2:
			fedstring = '%4s, %4s' % (self.fedIds[0], self.fedIds[1])
		if self.nstreams == 1:
			fedstring = '%4s      ' % (self.fedIds[0])

		string = ("%3d %15s, Crate %-6s, %-17s, slot: %-2d, "
			      "FEDs: %s, assigned to RU%-2d %15s")
		return string % (self.index, self.system, self.crate, self.frlpc,
			             self.slotNumber, fedstring, self.ruindex,
			             self.runame)


######################################################################
class daq2HardwareInfo(object):
	'''
---------------------------------------------------------------------
  class daq2HardwareInfo

 - Reads and stores information about the network cabling in the
   40GE and IB Clos networks
 - Takes the information from two .csv files (provided by Andre Holzner)
---------------------------------------------------------------------
'''
	def __init__(self, gecabling="2014-11-03-ru-network.csv",
		         ibcabling="2014-10-15-infiniband-ports.csv",
		         geswitchmask=[], ibswitchmask=[],
		         fedwhitelist=[], ruwhitelist=[], buwhitelist=[],
		         verbose=0):
		super(daq2HardwareInfo, self).__init__()
		self.verbose = verbose
		self.ibswitchmask = ibswitchmask
		self.geswitchmask = geswitchmask
		self.ge_switch_cabling = {} ## ge switch to list of conn. devices
		self.frlpc_cabling     = {} ## frlpc to list of ferols
		self.ferol_cabling     = {} ## ferol to corresponding frlpc
		self.missingFEROLs     = [] ## ferols with unknown frlpc
		self.ge_host_cabling   = {} ## hostname to ge switch

		self.ib_switch_cabling = {} ## ib switch to port, list of conn. dev.
		self.ru_inventory      = {} ## ib switch to list of RUs
		self.bu_inventory      = {} ## ib switch to list of BUs
		self.ib_host_cabling   = {} ## hostname to ib switch, port

		self.FEROLs = []
		self.fedid_cabling = {} ## fedid to frlpc

		self.fedwhitelist = fedwhitelist
		self.ruwhitelist = ruwhitelist
		self.buwhitelist = buwhitelist

		self.read40GECabling(gecabling)
		self.readIBCabling(ibcabling)

	def read40GECabling(self, filename):
		"""
		Fill dictionaries for:
		   ethswitch -> list of devices (rus, FEROLs)
		   frlpc -> list of FEROLs
		"""

		with open(filename, 'r') as infile:
			for line in infile:
				if line.strip().startswith('#') or len(line.strip()) == 0:
					continue

				switch,device = line.strip().split(';')

				## Apply mask
				if self.geswitchmask and not switch in self.geswitchmask:
					continue

				if not switch in self.ge_switch_cabling:
					self.ge_switch_cabling[switch] = []

				if not 'frlpc' in device and not device.startswith('ru'):
					self.missingFEROLs.append((switch, device))
					if self.verbose>0:
						print "Missing frlpc for:",switch, device
					continue

				spdevice = device.split(',')
				if len(spdevice) == 1 and device.startswith('ru-'):
					## Apply ru mask:
					if (self.ruwhitelist and not device in self.ruwhitelist):
						continue

					self.ge_switch_cabling[switch].append(device)
					self.ge_host_cabling[device] = switch
					continue
				elif len(spdevice) == 4: ## no fedids
					name, crate, slop, frlpc = spdevice
					fedid1, fedid2 = None, None
				elif len(spdevice) == 5: ## one fedid
					name, crate, slop, fedid1, frlpc = spdevice
					fedid2 = None
				elif len(spdevice) == 6: ## two fedid
					name, crate, slop, fedid1, fedid2, frlpc = spdevice

				slot = slop.lstrip('FEROL ')
				crate = crate.lstrip('crate ')
				if fedid1:
					if fedid2:
						fedid1 = fedid1.lstrip('FEDs ')
					else:
						fedid1 = fedid1.lstrip('FED ')
				ferol = FEROL(frlpc, int(slot), (fedid1, fedid2),
					          name, crate, switch)

				## Apply fed mask:
				if (self.fedwhitelist and
					not fedid1 in self.fedwhitelist and
					not fedid2 in self.fedwhitelist):
					continue

				self.FEROLs.append(ferol)
				if fedid1:
					self.fedid_cabling[fedid1] = frlpc
				if fedid2:
					self.fedid_cabling[fedid2] = frlpc

				if not frlpc in self.ge_switch_cabling[switch]:
					self.ge_switch_cabling[switch].append(frlpc)
				if not frlpc in self.frlpc_cabling:
					self.frlpc_cabling[frlpc] = []
				self.ge_host_cabling[frlpc] = switch
				self.frlpc_cabling[frlpc].append(ferol)
				self.ferol_cabling[ferol] = frlpc
		return True
	def readIBCabling(self, filename):
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
				if self.ibswitchmask and not switch in self.ibswitchmask:
					continue

				## mask machines:
				if self.buwhitelist and not device in self.buwhitelist:
					if device.startswith('bu-'): continue
				if self.ruwhitelist and not device in self.ruwhitelist:
					if device.startswith('ru-'): continue

				if port is not '': port = int(port)
				if dport is not '': dport = int(dport)
				if blisted is not '': blisted = bool(int(blisted))
				# print switch,port,device,dport,blisted,comment

				if not switch in self.ib_switch_cabling.keys():
					self.ib_switch_cabling[switch] = {}
				self.ib_switch_cabling[switch][port] = (device,dport)

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
		for switch, ports in self.ib_switch_cabling.iteritems():
			for port, (hostname,_) in ports.iteritems():
				self.ib_host_cabling[hostname] = (switch, port)

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
	def getAllRUs(self, switch):
		return [ru for ru in self.ge_switch_cabling[switch]
		                            if ru.startswith('ru-')]
	def getRUs(self, switch):
		"""
		Return a RU on the same ETH switch as the frlpc, as long as there are any
		"""
		allrus = [ru for ru in self.ge_switch_cabling[switch]
		                            if ru.startswith('ru-')]
		for ru in cycle(allrus):
			yield ru
	def getAllBUs(self, switch=None):
		if not switch:
			return [bu for bulist in self.bu_inventory.values()
			           for bu in bulist]
		else:
			try:
				return [bu for bu in self.bu_inventory[switch]]
			except KeyError:
				printError('IB switch %s not found'% switch, self)
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
	def getFEROLs(self, frlpc, haveFEDIDs=0):
		allFEROLs = self.frlpc_cabling[frlpc]
		if haveFEDIDs==1:
			return [f for f in allFEROLs if f.fedIds[0]]
		elif haveFEDIDs==2:
			return [f for f in allFEROLs if f.fedIds[1]]
		else:
			return allFEROLs

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










