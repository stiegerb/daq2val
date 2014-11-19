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

######################################################################
from daq2Configurator import daq2Configurator
class daq2ProdConfigurator(daq2Configurator):
	'''
---------------------------------------------------------------------
  class daq2ProdConfigurator

---------------------------------------------------------------------
'''
	def __init__(self, fragmentdir, hwInfo, verbose=5):
		super(daq2ProdConfigurator, self).__init__(fragmentdir,
			                                       verbose=verbose)

		self.hwInfo = hwInfo
		# self.symbMap = symbMap ## can get this info also from hwInfo?

		self.canonical = False

		## Counters
		self.ruindex = 0
		self.ferolindex = 0
		self.allRUs = []
		self.allFEROLs = []


	def makeFEROLConfig(self, ferol):
		self.makeSkeleton()
		## Not sure I need I2O protocol at all here
		self.addI2OProtocol(rus_to_add=[ferol.ruindex], bus_to_add=[])

		self.config.append(self.makeFerolController(ferol))
		self.addRUContextWithGEEndpoint(ferol.ruindex)
		outputname = 'FEROLCONTROLLER%d.xml' % ferol.index
		self.writeConfig(os.path.join(self.outPutDir,outputname))

	def makeEVMConfig(self, ru):
		self.makeSkeleton()
		ru_instances = [r.index for r in self.allRUs[1:]]
		self.addI2OProtocol(rus_to_add=ru_instances)

		## add the EVM
		self.config.append(self.makeRU(ru))
		for index in ru_instances:
			self.addRUContextWithIBEndpoint(index)
		for index in xrange(self.nbus):
			self.addBUContextWithIBEndpoint(index)

		outputname = 'EVM.xml'
		self.writeConfig(os.path.join(self.outPutDir,outputname))

	def makeRUConfig(self, ru):
		self.makeSkeleton()
		self.addI2OProtocol(rus_to_add=[ru.index])

		self.config.append(self.makeRU(ru))
		self.addRUContextWithIBEndpoint(0) ## EVM
		for index in xrange(self.nbus):
			self.addBUContextWithIBEndpoint(index)
		outputname = 'RU%d.xml' % ru.index
		self.writeConfig(os.path.join(self.outPutDir,outputname))

	def makeBUConfig(self, buindex):
		self.makeSkeleton()
		## no RU, only one BU
		self.addI2OProtocol(rus_to_add=[], bus_to_add=[buindex])
		self.config.append(self.makeBU(buindex))
		self.addRUContextWithIBEndpoint(0) ## EVM
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
			self.config.append(self.makeRU(ru))

		for index in xrange(self.nbus):
			self.config.append(self.makeBU(index))

		outputname = 'full.xml'
		self.writeConfig(os.path.join(self.outPutDir,outputname))


	def assignFEROLsToRUs(self, rus, ferols):
		ferols_rest = [f for f in ferols if f.nstreams == 0]
		rus_gen     = (r for r in rus)

		try:
			for n,f in enumerate(ferols):
				# print n,f
				if n%8==0: ru = rus_gen.next()
				f.ruindex = ru.index
				f.runame  = ru.hostname
				ru.addFRL(f)

		except StopIteration:
			print n,f
			printError('Running out of RUs for %s'%
				        self.hwInfo.ge_host_cabling[rus[0].hostname], self)

		if self.verbose>5:
			for f in ferols_rest:
				print 'leftover FEROL:', f
			for r in rus_gen:
				print 'leftover RU:', r
	def makeSplitConfigs(self, geswitches, dry=False):
		for switchname in geswitches:
			# get a list of frlpcs, ferols, and rus from the hwInfo
			frlpcs = self.hwInfo.getListOfFRLPCs(switchname,
				                                 canonical=self.canonical)
			runames = self.hwInfo.getAllRUs(switchname)

			## Number the RUs
			RUs_onswitch = []
			for runame in runames:
				runode = RUNode(self.ruindex, hostname=runame)
				self.allRUs.append(runode)
				RUs_onswitch.append(runode)
				self.ruindex += 1

			FEROLs_onswitch = []
			for frlpc in frlpcs:
				for ferol in self.hwInfo.getFEROLs(frlpc, haveFEDIDs=1):
					ferol.index = self.ferolindex
					self.allFEROLs.append(ferol)
					FEROLs_onswitch.append(ferol)
					self.ferolindex += 1


			## Assign FEROLs to RUs
			self.assignFEROLsToRUs(RUs_onswitch, FEROLs_onswitch)

			## Remove unused RUs
			for r in self.allRUs:
				if len(r.getFedIds()) == 0: self.allRUs.remove(r)

		if self.verbose>5:
			print 70*'-'
			for f in self.allFEROLs:
				print f

		if self.verbose>1:
			print 70*'-'
			for r in self.allRUs:
				print r, r.getFedIds()
			print 70*'-'


		if dry: return

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

		if self.verbose>0: print 70*'-'
		if self.verbose>0: print ' Wrote configs to %s' % self.outPutDir
		if self.verbose>0: print 70*'-'


