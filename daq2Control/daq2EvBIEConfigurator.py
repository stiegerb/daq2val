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

from daq2Utils import printError, printWarningWithWait
from daq2Configurator import elementFromFile, addFragmentFromFile
from daq2Configurator import RU_STARTING_TID, BU_STARTING_TID


######################################################################
from daq2Configurator import daq2Configurator
class daq2EvBIEConfigurator(daq2Configurator):
	'''
---------------------------------------------------------------------
  class daq2EvBIEConfigurator

---------------------------------------------------------------------
'''
	def __init__(self, fragmentdir, verbose=5):
		super(daq2EvBIEConfigurator, self).__init__(fragmentdir,
			                                       verbose=verbose)
		self.evbns          = 'evb'
		self.ptprot         = 'ibv' ## 'ibv' or 'udapl'

		self.maxEvtsUnderConstruction = None
		self.numberOfBuilders = None
		self.setRate = 0
		self.outPutDir = None

	def configureIBVforEvBIE(self):
		## TODO: Update!
		RUFragmentPath = os.path.join(self.fragmentdir,
                           'RU/evb/RU_ibv_application.xml')
		BUFragmentPath = os.path.join(self.fragmentdir,
                           'BU/BU_ibv_application.xml')

		RUIBVApp = elementFromFile(filename=RUFragmentPath)
		BUIBVApp = elementFromFile(filename=BUFragmentPath)

		BUApp = elementFromFile(filename=os.path.join(self.fragmentdir,
				                  'BU/evb/BU_application.xml'))
		maxResources = int(self.readPropertyFromApp(
		                        application=BUApp,
		                        prop_name="maxEvtsUnderConstruction")) #??

		if not self.maxMessageSize:
			RUMaxMSize = int(self.readPropertyFromApp(
				                        application=RUIBVApp,
				                        prop_name="maxMessageSize"))

			BUMaxMSize = int(self.readPropertyFromApp(
				                        application=BUIBVApp,
				                        prop_name="maxMessageSize"))

			if not RUMaxMSize == BUMaxMSize:
				printWarningWithWait('Differing maxMessageSize on RU and BU',
					                 waittime=2)
			else:
				self.maxMessageSize = RUMaxMSize

		# RU:
		if self.RUSendQPSize is not None:
			sendQPSize = self.RUSendQPSize
		else:
			sendQPSize = 256

		if self.RUSendPoolSize is not None:
			sendPoolSize = 1024*1024*self.RUSendPoolSize
		else:
			sendPoolSize = 2*1024**3

		if self.RUComplQPSize is not None:
			complQPSize = self.RUComplQPSize
		else:
			complQPSize = 12800

		recvPoolSize = 1*1024**3
		recvQPSize = 2048

		self.RUIBVConfig = (sendPoolSize, recvPoolSize,
			                complQPSize, sendQPSize, recvQPSize)

		# BU:
		if self.BURecvQPSize is not None:
			recvQPSize = self.BURecvQPSize
		else:
			recvQPSize = 256

		if self.BURecvPoolSize is not None:
			recvPoolSize = 1024*1024*self.BURecvPoolSize
		else:
			recvPoolSize = 3584*1024**2

		if self.BUComplQPSize is not None:
			complQPSize = self.BUComplQPSize
		else:
			complQPSize = 25600

		sendPoolSize = 1536*1024**2
		sendQPSize = 128

		self.BUIBVConfig = (sendPoolSize, recvPoolSize,
			                complQPSize, sendQPSize, recvQPSize)

		# EVM
		sendPoolSize = 10*1024**3
		recvPoolSize = 4*1024**3
		recvQPSize   = 256
		sendQPSize   = 1024
		complQPSize  = 64*1024

		self.EVMIBVConfig = (sendPoolSize, recvPoolSize,
			                complQPSize, sendQPSize, recvQPSize)

	def makeRU(self, ruindex):
		fragmentname = 'RU/evb/RU_context_bare.xml'
		context = elementFromFile(os.path.join(self.fragmentdir,fragmentname))

		## Add policy
		addFragmentFromFile(target=context,
			                filename=os.path.join(self.fragmentdir,
			                'RU/evb/RU_policy_%s.xml'%
			                self.ptprot),
			                index=0)
		polns = "http://xdaq.web.cern.ch/xdaq/xsd/2013/XDAQPolicy-10"
		for element in context.findall(QN(polns,"policy").text+'/'+
			                              QN(polns,"element").text):
			if 'RU%d' in element.get('pattern'):
				element.set('pattern',element.get('pattern').replace(
					                         'RU%d', 'RU%d'%(ruindex)))
		## Add builder network endpoint
		context.insert(1,Element(QN(self.xdaqns, 'Endpoint').text,
			              {'protocol':'%s'%self.ptprot ,
			               'service':"i2o",
			               'hostname':'RU%d_I2O_HOST_NAME'%(ruindex),
			               'port':'RU%d_I2O_PORT'%(ruindex),
			               'network':"infini"}))
		## Add builder network pt application
		addFragmentFromFile(target=context,
		                    filename=os.path.join(self.fragmentdir,
		                    'RU/evb/RU_%s_application.xml'%
		                    self.ptprot),
		                    index=2) ## add after the two endpoints

		## Configure IBV application:
		if self.setDynamicIBVConfig:
			if ruindex == 0:
				self.configureIBVApplication(context, self.EVMIBVConfig,
					                         maxMessageSize=self.maxMessageSize)
			else:
				self.configureIBVApplication(context, self.RUIBVConfig,
					                         maxMessageSize=self.maxMessageSize)

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		context.insert(3,module)

		## RU application
		ru_app_filename = os.path.join(self.fragmentdir,
			                  'RU/evb/RU_application.xml')
		if ruindex == 0:
			ru_app_filename = os.path.join(self.fragmentdir,
				              'RU/evb/RU_application_EVM.xml')

		ru_app = elementFromFile(filename=ru_app_filename)

		## Remove numberOfResponders, fragmentFIFOCapacity:
		self.removePropertyInApp(ru_app, 'numberOfResponders')
		self.removePropertyInApp(ru_app, 'fragmentFIFOCapacity')

		## Set inputSource to Local:
		self.setPropertyInApp(ru_app, 'inputSource', 'Local')

		## Set blockSize
		if self.maxMessageSize:
			newBlockSize = self.maxMessageSize/2**10*1000
			self.setPropertyInApp(ru_app, 'blockSize', str(newBlockSize))

		## Set maxTriggerRate (in Hz, 0 is unlimited):
		if not self.setRate == 0:
			self.setPropertyInApp(ru_app, 'maxTriggerRate', self.setRate)

		## fedSourceIds are created automatically, remove them
		# self.removePropertyInApp(ru_app, 'fedSourceIds')

		## Put one fedSourceId
		ruevbappns = (self.xdaqappns%'evb::RU' if
			          ruindex>0 else self.xdaqappns%'evb::EVM')
		fedSourceIds = ru_app.find(QN(ruevbappns, 'properties').text+'/'+
			                       QN(ruevbappns, 'fedSourceIds').text)
		fedSourceIds.attrib[QN(self.soapencns, 'arrayType').text] = (
			                       "xsd:ur-type[1]")
		item_element = fedSourceIds.find(QN(ruevbappns,'item').text)
		item_element.text = str(ruindex)

		# ## In case of EvB, add expected fedids
		# if self.evbns == 'evb':
		# 	ruevbappns = (self.xdaqappns%'evb::RU' if
		# 		          ru.index>0 else self.xdaqappns%'evb::EVM')
		# 	fedSourceIds = ru_app.find(QN(ruevbappns, 'properties').text+'/'+
		# 		                       QN(ruevbappns, 'fedSourceIds').text)
		# 	fedSourceIds.attrib[QN(self.soapencns, 'arrayType').text] = (
		# 		                       "xsd:ur-type[%d]"%(len(feds_to_add)))
		# 	item_element = fedSourceIds.find(QN(ruevbappns,'item').text)
		# 	fedSourceIds.remove(item_element)
		# 	for n,fed in enumerate(feds_to_add):
		# 		item_to_add = deepcopy(item_element)
		# 		item_to_add.attrib[QN(self.soapencns, 'position').text] = (
		# 			                                                '[%d]'%n)
		# 		item_to_add.text = str(fed)
		# 		fedSourceIds.append(item_to_add)

		context.insert(5,ru_app)
		ru_app.set('instance',str(ruindex))


		## Set instance and url
		for app in context.findall(QN(self.xdaqns, 'Endpoint').text):
			if 'RU%d' in app.attrib['hostname']:
				app.set('hostname', app.get('hostname')%ruindex)
			if 'RU%d' in app.attrib['port']:
				app.set('port', app.get('port')%ruindex)
		context.set('url', context.get('url')%(ruindex, ruindex))

		return context
	def makeBU(self, index):
		fragmentname = 'BU/BU_context.xml'
		context = elementFromFile(os.path.join(self.fragmentdir,
			                                      fragmentname))

		## Add policy
		addFragmentFromFile(target=context,
			                filename=os.path.join(self.fragmentdir,
			                	'BU/evb/BU_policy_%s.xml'%(
			                	self.ptprot)),
			                index=0)
		## Add builder network endpoint
		context.insert(1,Element(QN(self.xdaqns, 'Endpoint').text, {
			                        'protocol':'%s'%self.ptprot ,
			                        'service':'i2o',
			                        'hostname':'BU%d_I2O_HOST_NAME'%(index),
			                        'port':'BU%d_I2O_PORT'%(index),
			                        'network':'infini'}))
		## Add builder network pt application
		addFragmentFromFile(target=context,
		                    filename=os.path.join(self.fragmentdir,
		                        'BU/BU_%s_application.xml'%(
		                        self.ptprot)),
		                    index=2) ## add after the two endpoints

		## Configure IBV application:
		if self.setDynamicIBVConfig:
			self.configureIBVApplication(context, self.BUIBVConfig,
				                         maxMessageSize=self.maxMessageSize)

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		context.insert(3,module)

		## BU application
		bu_app = elementFromFile(filename=os.path.join(self.fragmentdir,
			                     'BU/evb/BU_application.xml'))
		# self.removePropertyInApp(bu_app, 'maxEvtsUnderConstruction')
		# self.removePropertyInApp(bu_app, 'eventsPerRequest')
		if self.maxEvtsUnderConstruction is not None:
			self.setPropertyInApp(bu_app, 'maxEvtsUnderConstruction',
				                  self.maxEvtsUnderConstruction)
		if self.numberOfBuilders is not None:
			self.setPropertyInApp(bu_app, 'numberOfBuilders',
				                  self.numberOfBuilders)

		context.insert(4,bu_app)
		bu_app.set('instance',str(index))

		## Set instance and url
		for app in context.findall(QN(self.xdaqns, 'Application').text):
			if app.attrib['class'] != "%s::BU"%self.evbns: continue
			app.set('instance', str(index))
			break
		context.set('url', context.get('url')%(index, index))

		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libevb.so"
		context.insert(5,module)

		return context

	def makeEVMConfig(self):
		self.makeSkeleton()
		## Everything
		self.addI2OProtocol()
		self.config.append(self.makeRU(0))
		outputname = 'EVM.xml'
		for index in xrange(1,self.nrus):
			self.addRUContextWithIBEndpoint(index)
		for index in xrange(self.nbus):
			self.addBUContextWithIBEndpoint(index)
		self.writeConfig(os.path.join(self.outPutDir,outputname))

	def makeRUConfig(self, ruindex):
		self.makeSkeleton()
		## only one RU, all the BUs
		self.addI2OProtocol(rus_to_add=[ruindex])
		self.config.append(self.makeRU(ruindex))
		self.addRUContextWithIBEndpoint(0) ## EVM
		for index in xrange(self.nbus):
			self.addBUContextWithIBEndpoint(index)
		outputname = 'RU%d.xml' % ruindex
		self.writeConfig(os.path.join(self.outPutDir,outputname))


	def makeBUConfig(self, buindex):
		self.makeSkeleton()
		## no RU, only one BU
		self.addI2OProtocol(rus_to_add=[], bus_to_add=[buindex])
		self.config.append(self.makeBU(buindex))
		self.addRUContextWithIBEndpoint(0)
		outputname = 'BU%d.xml' % buindex
		self.writeConfig(os.path.join(self.outPutDir,outputname))


	def makeSplitEvBIEConfig(self, nrus=1, nbus=1):
		self.nrus = nrus
		self.nbus = nbus
		# self.outPutDir = destination

		if "ibv" in self.ptprot and self.setDynamicIBVConfig:
			self.configureIBVforEvBIE()
		else:
			self.readIBVConfig()

		if self.verbose > 1:
			self.printIBVConfig()

		self.makeEVMConfig()
		for index in xrange(1,self.nrus):
			self.makeRUConfig(index)
		for index in xrange(self.nbus):
			self.makeBUConfig(index)


		if self.verbose>0: print 70*'-'
		if self.verbose>0: print ' Wrote configs to %s' % self.outPutDir
		if self.verbose>0: print 70*'-'

	def makeEvBIEConfig(self, nrus=1, nbus=1,
		               destination='configuration.template.xml'):
		self.nrus = nrus
		self.nbus = nbus

		##
		self.makeSkeleton()

		if "ibv" in self.ptprot and self.setDynamicIBVConfig:
			self.configureIBVforEvBIE()
		else:
			self.readIBVConfig()

		if self.verbose > 1:
			self.printIBVConfig()

		self.addI2OProtocol()
		for index in xrange(self.nrus):
			self.config.append(self.makeRU(index))
		for index in xrange(self.nbus):
			self.config.append(self.makeBU(index))


		if self.verbose>0: print 70*'-'
		self.writeConfig(destination)
		if self.verbose>0: print ' Wrote config to %s' % destination
		if self.verbose>0: print 70*'-'


