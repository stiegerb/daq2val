import os
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

from daq2Utils import printError
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

	def makeFEROLConfig(self, ferol):
		self.makeSkeleton()
		## Not sure I need I2O protocol at all here
		self.addI2OProtocol(rus_to_add=[ferol.ruindex], bus_to_add=[])

		self.config.append(self.makeFerolController(ferol))
		self.addRUContextWithGEEndpoint(ferol.ruindex)
		outputname = 'FEROLCONTROLLER%d.xml' % ferol.index
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
				              self.hwInfo.ge_host_cabling[rus[0].hostname])

		if self.verbose>5:
			for f in ferols_rest:
				print 'leftover FEROL:', f
			for r in rus_gen:
				print 'leftover RU:', r
	def makeSplitConfigs(self, geswitches):
		ruindex,ferolindex = 0,0
		allRUs = []
		allFEROLs = []
		for switchname in geswitches:
			# get a list of frlpcs, ferols, and rus
			frlpcs = self.hwInfo.getListOfFRLPCs(switchname,
				                                 canonical=self.canonical)
			runames = self.hwInfo.getAllRUs(switchname)

			## Number the RUs
			RUs_onswitch = []
			for runame in runames:
				runode = RUNode(ruindex, hostname=runame)
				allRUs.append(runode)
				RUs_onswitch.append(runode)
				ruindex += 1

			FEROLs_onswitch = []
			for frlpc in frlpcs:
				for ferol in self.hwInfo.getFEROLs(frlpc, haveFEDIDs=1):
					ferol.index = ferolindex
					allFEROLs.append(ferol)
					FEROLs_onswitch.append(ferol)
					ferolindex += 1


			## Assign FEROLs to RUs
			self.assignFEROLsToRUs(RUs_onswitch, FEROLs_onswitch)

			## Remove unused RUs
			for r in allRUs:
				if len(r.getFedIds()) == 0: allRUs.remove(r)

		if self.verbose>5:
			for f in allFEROLs:
				print f

		if self.verbose>1:
			for r in allRUs:
				print r, r.getFedIds()


		for ferol in allFEROLs:
			self.makeFEROLConfig(ferol)

		for ru in allRUs:
			self.makeRUConfig(ru)

		for n in xrange(self.nbus):
			self.makeBUConfig(n)
		exit(0)

	def makeConfig(self, nferols=8, streams_per_ferol=2, nrus=1, nbus=2,
		           destination='configuration.template.xml'):
		self.nrus              = nrus
		self.nbus              = nbus
		self.nferols           = nferols
		self.streams_per_ferol = streams_per_ferol

		self.FEDConfig = daq2ProdFEDConfiguration(
			                 nstreams=nferols*streams_per_ferol,
			                 nfrls=nferols, nrus=nrus,
			                 ferolRack=self.ferolRack, verbose=self.verbose)

		##
		self.makeSkeleton()
		self.addI2OProtocol()

		##
		if self.useGTPe:
			if self.useEFEDs:
				self.addGTPe()
				self.addEFEDs()
				self.addFMM(cards=self.createFMMCards())
			else:
				self.addGTPe()
				self.addFMM(cards=self.createEmptyFMMCard())

		##
		self.addFerolControllers(nferols=nferols,
			                     streams_per_ferol=streams_per_ferol)
		self.addRUs(nrus=nrus)
		if self.evbns == 'gevb2g': self.addEVM()
		self.addBUs(nbus=nbus)

		if self.verbose>0: print 70*'-'
		self.writeConfig(destination)
		if self.verbose>0: print ' Wrote config to %s' % destination
		if self.verbose>0: print 70*'-'


