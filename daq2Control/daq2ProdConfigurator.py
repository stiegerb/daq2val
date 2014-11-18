import os
import subprocess
import re
import time
from copy import deepcopy

from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import QName as QN
from xml.parsers.expat import ExpatError

from daq2Utils import printError
from daq2FEDConfiguration import daq2ProdFEDConfiguration, FRLNode, RUNode
from daq2Configurator import elementFromFile, addFragmentFromFile
from daq2Configurator import RU_STARTING_TID, BU_STARTING_TID

######################################################################
from daq2Configurator import daq2Configurator
class daq2ProdConfigurator(daq2Configurator):
	'''
---------------------------------------------------------------------
  class daq2ProdConfigurator

---------------------------------------------------------------------
'''
	def __init__(self, fragmentdir, verbose=5):
		super(daq2ProdConfigurator, self).__init__(fragmentdir,
			                                       verbose=verbose)

		## These should be passed as options
		self.enablePauseFrame  = True
		self.disablePauseFrame = False
		self.setCWND = -1
		self.evbns          = 'gevb2g' ## 'gevb2g' or 'evb'
		self.ptprot         = 'ibv' ## or 'ibv' or 'udapl'
		self.operation_mode = 'ferol_emulator'

		## 0,1,2,3,13 corresponding to dvfrlpc-c2f32-[09,11,13]-01.cms
		## (0 is all three, 13 is first 1 then 3)
		self.ferolRack      = 1

		self.useGTPe        = False
		self.useFMMForDAQ2  = False
		self.useEFEDs       = False

		## These should be passed as arguments
		self.nrus              = 1
		self.nbus              = 2
		self.nferols           = 8
		self.streams_per_ferol = 2

		## Counters
		self.eFED_crate_counter = 0
		self.eFED_app_instance  = 0

	def makeFerolController(self, frl):
		fragmentname = 'FerolController.xml'
		ferol = elementFromFile(self.fragmentdir+fragmentname)
		classname = 'ferol::FerolController'

		fedids   = frl.fedIds
		physSlot = frl.slotNumber
		sourceIp = frl.sourceIp

		self.setPropertyInAppInContext(ferol, classname,
			                           'slotNumber', physSlot)
		self.setPropertyInAppInContext(ferol, classname,
			                           'expectedFedId_0', fedids[0])
		try:
			self.setPropertyInAppInContext(ferol, classname,
				                           'expectedFedId_1', fedids[1])
		except IndexError:
			pass

		#### This is 'auto' now
		# self.setPropertyInAppInContext(ferol, classname,
		# 	                           'SourceIP', sourceIp)

		# if frl.nstreams == 1:
		# 	self.setPropertyInAppInContext(ferol, classname,
		# 	                               'TCP_CWND_FED0', 135000)
		# 	self.setPropertyInAppInContext(ferol, classname,
		# 	                               'TCP_CWND_FED1', 135000)
		# if frl.nstreams == 2:
		# 	self.setPropertyInAppInContext(ferol, classname,
		# 	                               'TCP_CWND_FED0', 62500)
		# 	self.setPropertyInAppInContext(ferol, classname,
		# 	                               'TCP_CWND_FED1', 62500)

		if frl.nstreams == 1:
			self.setPropertyInAppInContext(ferol, classname,
				                           'enableStream0', 'true')
			self.setPropertyInAppInContext(ferol, classname,
				                           'enableStream1', 'false')
		if frl.nstreams == 2:
			self.setPropertyInAppInContext(ferol, classname,
				                           'enableStream0', 'true')
			self.setPropertyInAppInContext(ferol, classname,
				                           'enableStream1', 'true')

		if self.setCorrelatedSeed:
			self.setPropertyInAppInContext(ferol, classname,
				                           'Seed_FED0', 12345)
			self.setPropertyInAppInContext(ferol, classname,
				                           'Seed_FED1', 23456)
		else:
			seed = int(time.time()*10000)%100000
			self.setPropertyInAppInContext(ferol, classname,
				                           'Seed_FED0', seed)
			self.setPropertyInAppInContext(ferol, classname,
				                           'Seed_FED1', seed+1)


		if self.disablePauseFrame:
			self.setPropertyInAppInContext(ferol, classname,
			                              'ENA_PAUSE_FRAME', 'false')
		if self.enablePauseFrame:
			self.setPropertyInAppInContext(ferol, classname,
			                               'ENA_PAUSE_FRAME', 'true')
		if self.setCWND >= 0:
			self.setPropertyInAppInContext(ferol, classname,
			                               'TCP_CWND_FED0', self.setCWND)
		if self.setCWND >= 0:
			self.setPropertyInAppInContext(ferol, classname,
			                               'TCP_CWND_FED1', self.setCWND)

		self.setPropertyInAppInContext(ferol, classname, 'DestinationIP',
			                  'RU%d_FRL_HOST_NAME'%frl.ruindex)
		self.setPropertyInAppInContext(ferol, classname,
			                  'TCP_DESTINATION_PORT_FED0',
			                  'RU%d_FRL_PORT'%frl.ruindex)
		self.setPropertyInAppInContext(ferol, classname,
			                  'TCP_DESTINATION_PORT_FED1',
			                  '60600')
		## route every second one to port 60600 if there is only one
		## stream per RU
		if self.streams_per_ferol==1 and (frl.index+1)%2==0:
			self.setPropertyInAppInContext(ferol, classname,
				                  'TCP_DESTINATION_PORT_FED0', '60600')
		try:
			self.setPropertyInAppInContext(ferol, classname,
				     'OperationMode',
				     FEROL_OPERATION_MODES[self.operation_mode][0])
			if FEROL_OPERATION_MODES[self.operation_mode][1] is not None:
				self.setPropertyInAppInContext(ferol, classname,
					 'FrlTriggerMode',
					 FEROL_OPERATION_MODES[self.operation_mode][1])
			else:
				self.removePropertyInAppInContext(ferol, classname,
					                              'FrlTriggerMode')
			self.setPropertyInAppInContext(ferol, classname,
				     'DataSource',
				     FEROL_OPERATION_MODES[self.operation_mode][2])

		except KeyError as e:
			printError('Unknown ferol operation mode "%s"'%
				        self.operation_mode, instance=self)
			raise RuntimeError('Unknown ferol operation mode')


		ferol.set('url', ferol.get('url')%(frl.index, frl.index))

		return ferol
	def addFerolControllers(self, nferols, streams_per_ferol=1):
		for frl in self.FEDConfig.frls:
			self.config.append(self.makeFerolController(frl))

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


