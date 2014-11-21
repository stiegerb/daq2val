from daq2Utils import printError

######################################################################
FEDIDS    = [600 + n for n in range(96)]
FEDID0 = 600
MAXSTREAMS = 1024
def fedIdGenerator(maxstreams, startid=600):
	for fedid in xrange(startid, startid+maxstreams):
		yield fedid

def split_list(alist, wanted_parts=1):
	length = len(alist)
	step = length // wanted_parts
	return [ alist[i*step:(i+1)*step] for i in range(wanted_parts) ]

######################################################################
class FRLNode(object):
	## Static member for fedid generator:
	FEDIDGEN = fedIdGenerator(MAXSTREAMS, startid=FEDID0)

	def __init__(self, index, rack, nstreams=2):
		self.index = index
		self.rack = rack
		self.nstreams = nstreams

		self.sourceIp   = self.getSourceIp(index)
		self.slotNumber = self.getSlotNumber(index)
		self.fedIds     = self.getFedIds()

		self.ruindex = -1

	def __str__(self):
		string = "FRL%-3d: Slot: %2d RU: %d IP: %33s FEDs: %d"
		if self.nstreams == 2:
			string += ', %d'
			return string % (self.index, self.slotNumber, self.ruindex,
				             self.sourceIp, self.fedIds[0], self.fedIds[1])
		if self.nstreams == 1:
			return string % (self.index, self.slotNumber, self.ruindex,
				             self.sourceIp, self.fedIds[0])

	def getFedIds(self):
		try:
			fedid0 = FRLNode.FEDIDGEN.next()
			fedid1 = FRLNode.FEDIDGEN.next()
			fedids = (fedid0, fedid1) if self.nstreams == 2 else (fedid0,)
			return fedids
		except StopIteration:
			printError("Maximum number of streams exceeded!", instance=self)
			exit(-1)

	def getSlotNumber(self, index):
		return (index%16)+1

	def getSourceIp(self, index):
		rack_to_host = {1:19,2:28,3:37}
		if self.rack == 0:
			if index < 16:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[1], (index+1)))
			if index >= 16 and index < 32:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[2], (index-15)))
			if index >= 32:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[3], (index-31)))
		elif self.rack == 1:
			if index < 16:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[1], (index+1)))
			if index >= 16 and index < 32:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[2], (index-15)))
			if index >= 32:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[3], (index-31)))
		elif self.rack == 2:
			if index < 16:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[2], (index+1)))
			if index >= 16 and index < 32:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[3], (index-15)))
		elif self.rack == 13:
			if index < 16:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[1], (index+1)))
			if index >= 16 and index < 32:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[3], (index-15)))
		else:
			if index < 16:
				return ('dvferol-c2f32-%d-%02d.dvfbs2v0.cms' %
					                     (rack_to_host[self.rack], (index+1)))
		## TODO Automatize retrieving of basename and datanet name,
		## see ~pzejdl/src/ferol/dvfrlpc-C2F32-09-01/feroltest/getFerolIP.sh

######################################################################
class FRLProdNode(FRLNode):
	def __init__(self, index, rack, fedid1, fedid2):
		self.index = index
		self.frlpc = rack
		self.nstreams = len([x for x in [fedid1, fedid2] if x is not None])

		self.sourceIp   = 'dvferol-%s.dvfbs2v0.cms'%rack.lstrip('frlpc-')
		self.slotNumber = index
		self.fedIds     = (fedid1, fedid2)
		self.ruindex = -1
	def getSourceIp(self, index):
		return self.sourceIp
	def getSlotNumber(self, index):
		return self.slotNumber

######################################################################
class RUNode(object):
	def __init__(self, index, hostname=''):
		self.index = index
		self.hostname = hostname
		self.frls = []

	def addFRL(self, frl):
		self.frls.append(frl)

	def getFedIds(self):
		return [fed for frl in self.frls for fed in frl.fedIds if fed]

	def __str__(self):
		return "RU%-2d at %14s" % (self.index, self.hostname)

######################################################################
class daq2FEDConfiguration(object):
	"""Helper class to distribute FEDs to RUs"""
	def __init__(self, nstreams, nfrls, nrus, ferolRack, verbose=0):
		self.nstreams = nstreams
		self.nfrls = nfrls
		self.strpfrl = self.nstreams//self.nfrls
		self.nrus = nrus
		self.ferolRack = ferolRack

		self.verbose=verbose

		self.frls = []
		self.rus  = []

		self.frl_index_to_ru_index = {}

		self.makeFRLtoRUAssignments()
		self.makeFEDConfiguration()

		if verbose>0:
			print 70*'-'
			for frl in self.frls: print frl

	def assignFRLToRU(self, index, frl):
		try:
			ru = self.rus[self.frl_index_to_ru_index[index]]
		except KeyError:
			printError("Missing RU assignment: could not find RU for FRL "
				       "with index %d"%index, self)
		ru.addFRL(frl)
		frl.ruindex = ru.index

	def makeFEDConfiguration(self):
		## Add the RUs
		for index in range(self.nrus):
			ru = RUNode(index)
			self.rus.append(ru)

		## Add the ferols, assigning each to a RU
		for index in range(self.nfrls):
			frl = FRLNode(index=index,
				          rack=self.ferolRack,
				          nstreams=self.strpfrl)
			self.assignFRLToRU(index, frl)
			self.frls.append(frl)

		fedid0 = FEDID0
		## FED to eFED slot distribution:
		fed_to_efedslot = {}
		for n,fed in enumerate(self.getAllFedIds()):
			if fed >  fedid0+23: break
			if fed <  fedid0+8:
				fed_to_efedslot[fed] = 2*(n+1)
			if fed >= fedid0+8  and fed < fedid0+16:
				fed_to_efedslot[fed] = 2*(n+1)-16
			if fed >= fedid0+16 and fed < fedid0+24:
				fed_to_efedslot[fed] = 2*(n+1)-32

		## FED to eFED/FMM slice distribution
		allfedids = self.getAllFedIds()
		FEDs = []
		FEDs += [(fed, 0, fed_to_efedslot[fed]) for fed in allfedids
		                          if fed <  fedid0+8 ]
		FEDs += [(fed, 1, fed_to_efedslot[fed]) for fed in allfedids
		                          if fed >= fedid0+8  and fed < fedid0+16]
		FEDs += [(fed, 2, fed_to_efedslot[fed]) for fed in allfedids
		                          if fed >= fedid0+16 and fed < fedid0+24]

		if self.verbose>1: print 70*'-'
		if self.verbose>1:
			print ' FED | Slice | eFED slot'
			for fed,slice,efed_slot in FEDs:
				print ' %3d | %d     | %2d' %(fed,slice,efed_slot)
		self.FEDConfiguration = FEDs
		efeds = []
		efeds.append([(fed, slot) for fed,slice,slot in self.FEDConfiguration
		                                                      if slice == 0])
		efeds.append([(fed, slot) for fed,slice,slot in self.FEDConfiguration
		                                                      if slice == 1])
		efeds.append([(fed, slot) for fed,slice,slot in self.FEDConfiguration
		                                                      if slice == 2])
		self.eFEDs = [fed_group for fed_group in efeds if len(fed_group)>0]
		self.nSlices = len(self.eFEDs)

	def makeFRLtoRUAssignments(self):
		frl_bunching = split_list(range(self.nfrls), self.nrus)
		self.frl_index_to_ru_index = {}
		for ru_index,bunch in enumerate(frl_bunching):
			for frl_index in bunch:
				self.frl_index_to_ru_index[frl_index] = ru_index

	def getAllFedIds(self):
		return [fed for frl in self.frls for fed in frl.fedIds]

######################################################################
from daq2HardwareInfo import daq2HardwareInfo

class daq2ProdFEDConfiguration(daq2FEDConfiguration):
	"""Helper class to distribute FEDs to RUs"""
	def __init__(self, frlpc, hwInfo, nfrls=16, nrus=2, verbose=0):
		self.verbose=verbose
		self.nfrls = nfrls
		self.nrus = nrus
		self.frlpc = frlpc
		try:
			self.allFerols = hwInfo.frlpc_cabling[frlpc]
			self.allRUs = hwInfo.getAllRUs(hwInfo.ge_host_cabling[frlpc])
		except KeyError:
			printError('FRLPC %s not found' % frlpc, self)

		## try nfrls > allferols

		self.frls = []
		self.rus  = []

		self.frl_index_to_ru_index = {}

		self.makeFRLtoRUAssignments()
		self.makeFEDConfiguration()

		if verbose>0:
			print 70*'-'
			for frl in self.frls: print frl

	def assignFRLToRU(self, index, frl):
		try:
			ru = self.rus[self.frl_index_to_ru_index[index]]
		except KeyError:
			printError("Missing RU assignment: could not find RU for FRL "
				       "with index %d"%index, self)
		ru.addFRL(frl)
		frl.ruindex = ru.index

	def makeFEDConfiguration(self):
		## Add the RUs
		for index in range(self.nrus):
			ru = RUNode(index)
			ru.hostname = self.allRUs[index]
			self.rus.append(ru)

		## Add the ferols, assigning each to a RU
		for ferol in self.allFerols:
			frl = FRLProdNode(index=ferol.slotNumber,
			                  fedid1=ferol.fedIds[0],
			                  fedid2=ferol.fedIds[1],
				              rack=self.frlpc)
			self.assignFRLToRU(index, frl)
			self.frls.append(frl)

		# ## FED to eFED/FMM slice distribution
		# allfedids = self.getAllFedIds()
		# FEDs = []
		# FEDs += [(fed, 0, fed_to_efedslot[fed]) for fed in allfedids
		#                            if fed <  fedid0+8 ]
		# FEDs += [(fed, 1, fed_to_efedslot[fed]) for fed in allfedids
		#                            if fed >= fedid0+8  and fed < fedid0+16]
		# FEDs += [(fed, 2, fed_to_efedslot[fed]) for fed in allfedids
		#                            if fed >= fedid0+16 and fed < fedid0+24]

		# if self.verbose>1: print 70*'-'
		# if self.verbose>1:
		# 	print ' FED | Slice | eFED slot'
		# 	for fed,slice,efed_slot in FEDs:
		# 		print ' %3d | %d     | %2d' %(fed,slice,efed_slot)
		# self.FEDConfiguration = FEDs
		# efeds = []
		# efeds.append([(fed, slot) for fed,slice,slot in self.FEDConfiguration
		#                                                       if slice == 0])
		# efeds.append([(fed, slot) for fed,slice,slot in self.FEDConfiguration
		#                                                       if slice == 1])
		# efeds.append([(fed, slot) for fed,slice,slot in self.FEDConfiguration
		#                                                       if slice == 2])
		# self.eFEDs = [fed_group for fed_group in efeds if len(fed_group)>0]
		# self.nSlices = len(self.eFEDs)

