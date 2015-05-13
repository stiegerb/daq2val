
import os
import sys
import subprocess
import re
import time
from copy import deepcopy
from pprint import pprint

from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import QName as QN
from xml.parsers.expat import ExpatError

from daq2Utils import printError, printProgress
from daq2FEDConfiguration import daq2ProdFEDConfiguration, FRLNode, RUNode
from daq2Configurator import elementFromFile, addFragmentFromFile
from daq2Configurator import RU_STARTING_TID, BU_STARTING_TID
from daq2Configurator import FEROL_OPERATION_MODES

def truncate(mylist, multiple=8):
	delim = len(mylist)-len(mylist)%multiple
	return mylist[:delim]

######################################################################
from daq2Configurator import daq2Configurator
class daq2ProdConfigurator(daq2Configurator):
	'''
---------------------------------------------------------------------
  class daq2ProdConfigurator

---------------------------------------------------------------------
'''
	def __init__(self, fragmentdir, hwInfo, canonical=0,
		         dry=False, verbose=5):
		super(daq2ProdConfigurator, self).__init__(fragmentdir,
			                                       verbose=verbose)

		self.hwInfo = hwInfo
		# self.symbMap = symbMap ## can get this info also from hwInfo?

		self.canonical = canonical
		self.dry = dry

		self.dropAtRU = False

		## Counters
		self.haveEVM = False
		self.ruindex = 1
		self.ferolindex = 1
		self.allRUs = []
		self.allFEROLs = []


	def makeFEROLConfig(self, ferol):
		self.makeSkeleton()
		self.config.append(self.makeFerolController(ferol))
		isevm = (ferol.ruindex==self.allRUs[0].index)
		self.addRUContextWithGEEndpoint(ferol.ruindex, isEVM=isevm)
		outputname = 'FEROLCONTROLLER%d.xml' % ferol.index
		self.writeConfig(os.path.join(self.outPutDir,outputname))
	def makeEVMConfig(self, ru):
		self.makeSkeleton()
		ru_instances = [r.index for r in self.allRUs[1:]]
		self.addI2OProtocol(rus_to_add=ru_instances,
			                evminst=self.allRUs[0].index)

		## add the EVM
		self.config.append(self.makeRU(ru, dropAtRU=self.dropAtRU,
			                               isEVM=True))
		for index in ru_instances:
			self.addRUContextWithIBEndpoint(index)
		for index in xrange(self.nbus):
			self.addBUContextWithIBEndpoint(index)

		outputname = 'RU%d.xml' % ru.index
		self.writeConfig(os.path.join(self.outPutDir,outputname))
	def makeRUConfig(self, ru):
		self.makeSkeleton()
		self.addI2OProtocol(rus_to_add=[ru.index],
			                evminst=self.allRUs[0].index)

		self.config.append(self.makeRU(ru, dropAtRU=self.dropAtRU))
		self.addRUContextWithIBEndpoint(self.allRUs[0].index, isEVM=True)
		for index in xrange(self.nbus):
			self.addBUContextWithIBEndpoint(index)
		outputname = 'RU%d.xml' % ru.index
		self.writeConfig(os.path.join(self.outPutDir,outputname))
	def makeBUConfig(self, buindex):
		self.makeSkeleton()
		## no RU, only one BU
		self.addI2OProtocol(rus_to_add=[], bus_to_add=[buindex],
			                evminst=self.allRUs[0].index)
		self.config.append(self.makeBU(buindex))
		self.addRUContextWithIBEndpoint(self.allRUs[0].index, isEVM=True)
		outputname = 'BU%d.xml' % buindex
		self.writeConfig(os.path.join(self.outPutDir,outputname))
	def makeFullConfig(self):
		self.makeSkeleton()
		ru_instances = [r.index for r in self.allRUs[1:]]
		self.addI2OProtocol(rus_to_add=ru_instances)

		for ferol in self.allFEROLs:
			self.config.append(self.makeFerolController(ferol))

		## add the EVM
		for ru in self.allRUs:
			isevm = False
			if ru.index == 0: isevm = True
			self.config.append(self.makeRU(ru, isEVM=isevm))

		for index in xrange(self.nbus):
			self.config.append(self.makeBU(index))

		outputname = 'full.xml'
		self.writeConfig(os.path.join(self.outPutDir,outputname))

	def assignFEROLsToRUs(self, rus_gen, ferols, nRUs):
		ferols_to_use = [f for f in ferols if f.nstreams > 0]
		ferols_rest = [f for f in ferols if f.nstreams == 0]

		ferolsPerRU = 8
		if not self.canonical and nRUs * ferolsPerRU < len(ferols_to_use):
			ferolsPerRU = len(ferols_to_use)/nRUs + 1
		try:
			for n,f in enumerate(ferols_to_use):
				if n%ferolsPerRU==0: ru = rus_gen.next()
				f.ruindex = ru.index
				f.runame  = ru.hostname
				ru.addFRL(f)

		except StopIteration:
			print f
			printError('Running out of RUs for %s'%
				        self.hwInfo.ge_host_cabling[f.frlpc], self)

		if self.verbose>5:
			for f in ferols_rest:
				print 'unused FEROL:', f
			for r in rus_gen:
				print 'unused RU:', r
	def assignEVM(self, rus_gen, frlpcs):
		if self.haveEVM: return True
		for frlpc in frlpcs:
			for ferol in self.hwInfo.getFEROLs(frlpc, haveFEDIDs=1):
				ferol.index = 0
				self.allFEROLs.append(ferol)

				evm = rus_gen.next()
				evm.index = 0
				ferol.ruindex = evm.index
				ferol.runame = evm.hostname
				ferol.nstreams = 1
				ferol.fedIds = (ferol.fedIds[0], None)
				evm.addFRL(ferol)
				print "Found EVM. (You should only ever see this line once)"
				return True
		return False


	def makeConfigs(self, geswitches):
		if self.canonical == 1:
			minFRLs = 8
			minFEDIDs = 8
		elif self.canonical > 1:
			minFRLs = 16
			minFEDIDs = 8
		else:
			minFRLs = 2
			minFEDIDs = 1
		for switchname in geswitches:
			# get a list of frlpcs, ferols, and rus from the hwInfo
			allfrlpcs = self.hwInfo.getListOfFRLPCs(switchname)
			frlpcs = self.hwInfo.getListOfFRLPCs(switchname,
				                             minFRLs=minFRLs,
				                             minFEDIDs=minFEDIDs)

			## Number the RUs
			runames = self.hwInfo.getAllRUs(switchname)
			RUs_onswitch = []
			for runame in runames:
				runode = RUNode(self.ruindex, hostname=runame)
				self.allRUs.append(runode)
				RUs_onswitch.append(runode)
				self.ruindex += 1
			if len(RUs_onswitch) == 0: continue
			RU_gen = (r for r in RUs_onswitch)

			## Find an EVM:
			if not self.haveEVM:
				if self.canonical:
					## Take one of the remaining
					frlpcs_evm = list(set(allfrlpcs).difference(set(frlpcs)))
					self.haveEVM = self.assignEVM(RU_gen, frlpcs_evm)
				else:
					## Just take the first one of
					## the one with the fewest FEROLs
					try:
						frlpcs_evm = sorted(frlpcs,
							                key=lambda f:
							                len(self.hwInfo.getFEROLs(f)))
						self.haveEVM = self.assignEVM(RU_gen, frlpcs_evm)
						if self.haveEVM:
							frlpcs.remove(frlpcs_evm[0])
					except IndexError:
						pass ## try next time


			FEROLs_onswitch = []
			for frlpc in frlpcs:
				if self.canonical > 1:
					haveFEDIDs = 2
				else:
					haveFEDIDs = 1
				ferols = self.hwInfo.getFEROLs(frlpc, haveFEDIDs=haveFEDIDs)
				## Apply canonicity
				if self.canonical:
					if self.canonical and len(ferols) < haveFEDIDs*8: continue
					ferols = truncate(ferols,multiple=haveFEDIDs*8)
				for ferol in ferols:
					ferol.index = self.ferolindex
					if self.canonical in [1,3]:
						ferol.fedIds = (ferol.fedIds[0], None)
						ferol.nstreams = 1
					self.allFEROLs.append(ferol)
					FEROLs_onswitch.append(ferol)
					self.ferolindex += 1
			if len(FEROLs_onswitch) == 0: continue

			## Assign FEROLs to RUs
			self.assignFEROLsToRUs(RU_gen, FEROLs_onswitch,
				                   nRUs=len(RUs_onswitch))

		if not self.haveEVM:
			printError("Failed to add EVM!", self)
			raise RuntimeError("No EVM!")

		## Remove unused RUs
		usedRUs = []
		for r in self.allRUs:
			if len(r.getFedIds()) != 0:
				if r.index == 0:
					usedRUs.insert(0,r)
				else:
					usedRUs.append(r)
		self.allRUs = usedRUs

		## Remove unused FEROLs
		usedFEROLs = []
		for f in self.allFEROLs:
			if f.ruindex >= 0:
				usedFEROLs.append(f)
		self.allFEROLs = usedFEROLs

		if self.verbose>5:
			print 70*'-'
			for f in self.allFEROLs:
				print f

		if self.verbose>1:
			print 70*'-'
			for r in self.allRUs:
				print r, r.getFedIds()
			print 70*'-'


		if self.dry: return

		for n,ferol in enumerate(self.allFEROLs):
			printProgress(n,len(self.allFEROLs),customstr='FEROLs: ')
			self.makeFEROLConfig(ferol)
		print ''

		self.makeEVMConfig(self.allRUs[0])

		for n,ru in enumerate(self.allRUs[1:]):
			printProgress(n,len(self.allRUs)-1,customstr='RUs: ')
			self.makeRUConfig(ru)
		print ''

		for n in xrange(self.nbus):
			printProgress(n,self.nbus,customstr='BUs: ')
			self.makeBUConfig(n)
		print ''

		self.makeFullConfig()

		if self.verbose>0:
			print 70*'-'
			print ' Wrote configs to %s' % self.outPutDir
			print 70*'-'

	def printSetup(self, filename):
		with open(filename, 'w') as outfile:
			outfile.write(115*'-'+'\n')
			nfeds = len([i for r in self.allRUs for i in r.getFedIds()])
			outfile.write("%d FEDs, %d FEROLs, %d RUs, %d BUs" % (
				           nfeds, len(self.allFEROLs),
				           len(self.allRUs), self.nbus))
			outfile.write('\n')
			outfile.write(115*'-'+'\n')
			for r in self.allRUs:
				outfile.write("%-22s"%str(r))
				outfile.write("%2d FEROLs, "%len(r.frls))
				outfile.write("%2d FEDs: "%len(r.getFedIds()))
				fedstr = '%4d '*len(r.getFedIds())
				fedstr = fedstr % tuple([int(i) for i in r.getFedIds()])
				outfile.write(fedstr)
				outfile.write('\n')
			outfile.write(115*'-'+'\n')
			for f in self.allFEROLs:
				outfile.write(str(f))
				outfile.write('\n')
			outfile.write(115*'-'+'\n')

			outfile.write('\n\n')
			outfile.close()
