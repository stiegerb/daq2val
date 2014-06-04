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

def getLog2SizeAndUnit(size):
	size = float(size)
	if size < 1024:
		return "%d B" % int(size)
	if size >= 1024 and size < 1024**2:
		return "%d kB" % int(size/1024)
	if size >= 1024**2 and size < 1024**3:
		return "%d MB" % int(size/1024/1024)
	if size >= 1024**3:
		return "%d GB" % int(size/1024/1024/1024)


######################################################################
from daq2Configurator import daq2Configurator
class daq2MSIOConfigurator(daq2Configurator):
	'''
---------------------------------------------------------------------
  class daq2MSIOConfigurator

---------------------------------------------------------------------
'''
	def __init__(self, fragmentdir, verbose=5):
		super(daq2MSIOConfigurator, self).__init__(fragmentdir,
			                                       verbose=verbose)

		self.evbns          = 'msio' ## 'msio' or 'gevb2g'
		self.ptprot         = 'ibv' ## or 'ibv' or 'udapl'

		self.useGTPe        = False
		self.useEFEDs       = False

		self.clientSendPoolSize = None ## in MB
		self.clientSendQPSize = None
		self.clientComplQPSize = None
		self.serverRecvPoolSize = None ## in MB
		self.serverRecvQPSize = None
		self.serverComplQPSize = None
		self.setDynamicIBVConfig = False
		self.maxMessageSize = None

		self.RUIBVConfig = tuple([None]*5)
		self.BUIBVConfig = tuple([None]*5)
		self.EVMIBVConfig = tuple([None]*5)

		## These should be passed as arguments
		self.nclients = 1
		self.nservers = 1

	def addMSIOI2OProtocol(self):
		i2ons = "http://xdaq.web.cern.ch/xdaq/xsd/2004/I2OConfiguration-30"
		prot = Element(QN(i2ons, 'protocol').text)

		## Add Clients:
		for n in xrange(self.nclients):
			prot.append(Element(QN(i2ons, 'target').text,
				                  {'class':'Client',
				                   'instance':"%d"%n,
				                   'tid':'%d'%(RU_STARTING_TID+n)}))
		## Add Servers:
		for n in xrange(self.nservers):
			prot.append(Element(QN(i2ons, 'target').text,
				                  {'class':'Server',
				                   'instance':"%d"%n,
				                   'tid':'%d'%(BU_STARTING_TID+2*n)}))

		self.config.append(prot)
	def addInputEmulatorProtocol(self):
		i2ons = "http://xdaq.web.cern.ch/xdaq/xsd/2004/I2OConfiguration-30"
		prot = self.config.find(QN(i2ons, 'protocol').text)

		## Add Inputemulators
		starting_tid = BU_STARTING_TID + 200
		for n in range(self.nclients):
			prot.append(Element(QN(i2ons, 'target').text,
				                  {'class':'gevb2g::InputEmulator',
				                   'instance':"%d"%n,
				                   'tid':'%d'%(starting_tid+n)}))

	def configureIBV(self):
		if self.evbns == 'msio':
			RUFragmentPath = os.path.join(self.fragmentdir,
                                 'msio/client_ibv_application.xml')
			BUFragmentPath = os.path.join(self.fragmentdir,
                                 'msio/server_ibv_application.xml')
		elif self.evbns == 'gevb2g':
			RUFragmentPath = os.path.join(self.fragmentdir,
                               'RU/gevb2g/msio/RU_ibv_application_msio.xml')
			BUFragmentPath = os.path.join(self.fragmentdir,
                               'BU/gevb2g/msio/BU_ibv_application_msio.xml')
			EVMFragmentPath = os.path.join(self.fragmentdir,
                               'EVM/msio/EVM_ibv_application_msio.xml')
			EVMIBVApp = elementFromFile(filename=EVMFragmentPath)


		RUIBVApp = elementFromFile(filename=RUFragmentPath)
		BUIBVApp = elementFromFile(filename=BUFragmentPath)

		BUApp = elementFromFile(filename=os.path.join(self.fragmentdir,
				                  'BU/gevb2g/msio/BU_application_msio.xml'))
		maxResources = int(self.readPropertyFromApp(
		                        application=BUApp,
		                        prop_name="maxResources"))

		RUMaxMSize = int(self.readPropertyFromApp(
			                        application=RUIBVApp,
			                        prop_name="maxMessageSize"))

		BUMaxMSize = int(self.readPropertyFromApp(
			                        application=BUIBVApp,
			                        prop_name="maxMessageSize"))
		self.maxMessageSize = RUMaxMSize if RUMaxMSize == BUMaxMSize else None

		# RU/Client:
		if self.evbns == 'msio':
			if self.clientSendQPSize is not None:
				sendQPSize = self.clientSendQPSize
			else:
				sendQPSize = int(self.readPropertyFromApp(
			                              application=RUIBVApp,
			                              prop_name="sendQueuePairSize"))

			if self.clientSendPoolSize is not None:
				sendPoolSize = 1024*1024*self.clientSendPoolSize
			else:
				sendPoolSize = (sendQPSize/16)*RUMaxMSize*self.nclients

			if self.clientComplQPSize is not None:
				complQPSize = self.clientComplQPSize
			else:
				complQPSize = (sendQPSize/16)*self.nclients

			recvPoolSize = 0x800000
			recvQPSize = 1
		elif self.evbns == 'gevb2g':
			print maxResources
			if self.clientSendQPSize is not None:
				sendQPSize = self.clientSendQPSize
			else:
				sendQPSize = maxResources*self.nservers

			if self.clientSendPoolSize is not None:
				sendPoolSize = 1024*1024*self.clientSendPoolSize
			else:
				sendPoolSize = sendQPSize*RUMaxMSize

			if self.clientComplQPSize is not None:
				complQPSize = self.clientComplQPSize
			else:
				complQPSize = 8192

			recvPoolSize = 0x2000000
			recvQPSize = 64

		self.RUIBVConfig = (sendPoolSize, recvPoolSize,
			                complQPSize, sendQPSize, recvQPSize)

		# BU/Server:
		if self.evbns == 'msio':
			if self.serverRecvPoolSize is not None:
				recvPoolSize = 1024*1024*self.serverRecvPoolSize
			else:
				recvPoolSize = (recvQPSize*2)*self.nclients*BUMaxMSize


			if self.serverRecvQPSize is not None:
				recvQPSize = self.serverRecvQPSize
			else:
				recvQPSize = int(self.RUIBVConfig[0]*2/self.nclients/BUMaxMSize)

			if self.serverComplQPSize is not None:
				complQPSize = self.serverComplQPSize
			else:
				complQPSize = recvQPSize*self.nclients

			sendPoolSize = 0x800000
			sendQPSize = 1
		elif self.evbns == 'gevb2g':
			if self.serverRecvQPSize is not None:
				recvQPSize = self.serverRecvQPSize
			else:
				recvQPSize = int(self.RUIBVConfig[0]*2/self.nclients/BUMaxMSize)

			if self.serverRecvPoolSize is not None:
				recvPoolSize = 1024*1024*self.serverRecvPoolSize
			else:
				recvPoolSize = int((recvQPSize+maxResources)*self.nclients*BUMaxMSize)
				# recvPoolSize = int(recvQPSize*self.nclients*BUMaxMSize*1.4)

			if self.serverComplQPSize is not None:
				complQPSize = self.serverComplQPSize
			else:
				complQPSize = recvQPSize*self.nclients

			sendPoolSize = 0x2000000
			sendQPSize = 64


		self.BUIBVConfig = (sendPoolSize, recvPoolSize,
			                complQPSize, sendQPSize, recvQPSize)

		# EVM:
		if self.evbns == 'gevb2g':
			sendPoolSize = maxResources*256*1024*self.nservers*2
			recvPoolSize = maxResources*256*1024*self.nservers*2
			recvQPSize = maxResources*2
			sendQPSize = maxResources
			complQPSize = maxResources*2*self.nservers


			self.EVMIBVConfig = (sendPoolSize, recvPoolSize,
				                complQPSize, sendQPSize, recvQPSize)

	def readIBVConfig(self):
		if self.evbns == 'msio':
			RUFragmentPath = os.path.join(self.fragmentdir,
                                 'msio/client_ibv_application.xml')
			BUFragmentPath = os.path.join(self.fragmentdir,
                                 'msio/server_ibv_application.xml')
		elif self.evbns == 'gevb2g':
			RUFragmentPath = os.path.join(self.fragmentdir,
                               'RU/gevb2g/msio/RU_ibv_application_msio.xml')
			BUFragmentPath = os.path.join(self.fragmentdir,
                               'BU/gevb2g/msio/BU_ibv_application_msio.xml')
			EVMFragmentPath = os.path.join(self.fragmentdir,
                               'EVM/msio/EVM_ibv_application_msio.xml')
			EVMIBVApp = elementFromFile(filename=EVMFragmentPath)


		RUIBVApp = elementFromFile(filename=RUFragmentPath)
		BUIBVApp = elementFromFile(filename=BUFragmentPath)

		BUApp = elementFromFile(filename=os.path.join(self.fragmentdir,
				                  'BU/gevb2g/msio/BU_application_msio.xml'))
		maxResources = int(self.readPropertyFromApp(
		                        application=BUApp,
		                        prop_name="maxResources"))

		RUMaxMSize = int(self.readPropertyFromApp(
			                        application=RUIBVApp,
			                        prop_name="maxMessageSize"))

		BUMaxMSize = int(self.readPropertyFromApp(
			                        application=BUIBVApp,
			                        prop_name="maxMessageSize"))
		self.maxMessageSize = RUMaxMSize if RUMaxMSize == BUMaxMSize else None


		sendPoolSize = int(self.readPropertyFromApp(RUIBVApp,
			                                    'senderPoolSize'),16)
		recvPoolSize = int(self.readPropertyFromApp(RUIBVApp,
			                                    'receiverPoolSize'),16)
		complQPSize  = int(self.readPropertyFromApp(RUIBVApp,
			                                    'completionQueueSize'))
		sendQPSize   = int(self.readPropertyFromApp(RUIBVApp,
			                                    'sendQueuePairSize'))
		recvQPSize   = int(self.readPropertyFromApp(RUIBVApp,
			                                    'recvQueuePairSize'))
		self.RUIBVConfig = (sendPoolSize, recvPoolSize,
			                complQPSize, sendQPSize, recvQPSize)


		sendPoolSize = int(self.readPropertyFromApp(BUIBVApp,
			                                    'senderPoolSize'),16)
		recvPoolSize = int(self.readPropertyFromApp(BUIBVApp,
			                                    'receiverPoolSize'),16)
		complQPSize  = int(self.readPropertyFromApp(BUIBVApp,
			                                    'completionQueueSize'))
		sendQPSize   = int(self.readPropertyFromApp(BUIBVApp,
			                                    'sendQueuePairSize'))
		recvQPSize   = int(self.readPropertyFromApp(BUIBVApp,
			                                    'recvQueuePairSize'))
		self.BUIBVConfig = (sendPoolSize, recvPoolSize,
			                complQPSize, sendQPSize, recvQPSize)

		# EVM:
		if self.evbns == 'gevb2g':
			sendPoolSize = int(self.readPropertyFromApp(EVMIBVApp,
				                                    'senderPoolSize'),16)
			recvPoolSize = int(self.readPropertyFromApp(EVMIBVApp,
				                                    'receiverPoolSize'),16)
			complQPSize  = int(self.readPropertyFromApp(EVMIBVApp,
				                                    'completionQueueSize'))
			sendQPSize   = int(self.readPropertyFromApp(EVMIBVApp,
				                                    'sendQueuePairSize'))
			recvQPSize   = int(self.readPropertyFromApp(EVMIBVApp,
				                                    'recvQueuePairSize'))
			self.EVMIBVConfig = (sendPoolSize, recvPoolSize,
				                complQPSize, sendQPSize, recvQPSize)
	def printIBVConfig(self):
		print 70*'-'
		if not None in self.RUIBVConfig:
			sPoolSize, rPoolSize, cQPSize, sQPSize,rQPSize = self.RUIBVConfig
			print (" Buffers circulating per destination: %d" %
				            int(sPoolSize/self.maxMessageSize/self.nclients))
			print "  RU/client IBV config:"
			print "    sendPoolSize: %s (%s)" % (
				               hex(sPoolSize), getLog2SizeAndUnit(sPoolSize))
			print "    recvPoolSize: %s (%s)" % (
				               hex(rPoolSize), getLog2SizeAndUnit(rPoolSize))
			print "    complQPSize", cQPSize
			print "    sendQPSize", sQPSize
			print "    recvQPSize", rQPSize

		if not None in self.BUIBVConfig:
			sPoolSize, rPoolSize, cQPSize, sQPSize,rQPSize = self.BUIBVConfig
			print "  BU/server IBV config:"
			print "    sendPoolSize: %s (%s)" % (
				               hex(sPoolSize), getLog2SizeAndUnit(sPoolSize))
			print "    recvPoolSize: %s (%s)" % (
				               hex(rPoolSize), getLog2SizeAndUnit(rPoolSize))
			print "    complQPSize", cQPSize
			print "    sendQPSize", sQPSize
			print "    recvQPSize", rQPSize

		# EVM:
		if not None in self.EVMIBVConfig:
			sPoolSize, rPoolSize, cQPSize,sQPSize,rQPSize = self.EVMIBVConfig
			print "  EVM IBV config:"
			print "    sendPoolSize: %s (%s)" % (
				               hex(sPoolSize), getLog2SizeAndUnit(sPoolSize))
			print "    recvPoolSize: %s (%s)" % (
				               hex(rPoolSize), getLog2SizeAndUnit(rPoolSize))
			print "    complQPSize", cQPSize
			print "    sendQPSize", sQPSize
			print "    recvQPSize", rQPSize

	## MStreamIO
	def makeClient(self, index):
		fragmentname = 'msio/client_context.xml'
		context = elementFromFile(os.path.join(self.fragmentdir,
			                                      fragmentname))

		## Add policy
		addFragmentFromFile(target=context, filename=
			                os.path.join(self.fragmentdir,
			                	'msio/client_policy_%s.xml'% self.ptprot),
			                index=0)
		polns = "http://xdaq.web.cern.ch/xdaq/xsd/2013/XDAQPolicy-10"
		for element in context.findall(QN(polns,"policy").text+'/'+
			                              QN(polns,"element").text):
			if 'RU%d' in element.get('pattern'):
				element.set('pattern',element.get('pattern').replace(
					                         'RU%d', 'RU%d'%(index)))
		## Add pt application
		addFragmentFromFile(target=context, filename=
			                os.path.join(self.fragmentdir,
		                    'msio/client_%s_application.xml'% self.ptprot),
		                    index=2) ## add after policy and endpoint

		## Configure IBV application:
		if self.setDynamicIBVConfig:
			self.configureIBVApplication(context, self.RUIBVConfig)

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		context.insert(3,module)

		## Client application
		ru_app = elementFromFile(filename=os.path.join(self.fragmentdir,
			                     'msio/client_application.xml'))
		context.insert(4,ru_app)
		ru_app.set('instance',str(index))

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		if self.evbns == 'msio':
			module.text = "$XDAQ_ROOT/lib/libmstreamio2g.so"
		context.insert(5,module)

		## Set instance and url
		for app in context.findall(QN(self.xdaqns, 'Endpoint').text):
			if 'RU%d' in app.attrib['hostname']:
				app.set('hostname', app.get('hostname')%index)
			if 'RU%d' in app.attrib['port']:
				app.set('port', app.get('port')%index)
		context.set('url', context.get('url')%(index, index))

		return context
	def makeServer(self, index):
		fragmentname = 'msio/server_context.xml'
		context = elementFromFile(os.path.join(self.fragmentdir,
			                                      fragmentname))

		## Add policy
		addFragmentFromFile(target=context,
			                filename=os.path.join(self.fragmentdir,
			                	     'msio/server_policy_%s.xml'%(
			                	      self.ptprot)),
			                index=0)
		## Add pt application
		addFragmentFromFile(target=context,
		                    filename=os.path.join(self.fragmentdir,
		                             'msio/server_%s_application.xml'%(
		                             self.ptprot)),
		                    index=2) ## add after the two endpoints

		## Configure IBV application:
		if self.setDynamicIBVConfig:
			self.configureIBVApplication(context, self.BUIBVConfig)

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		context.insert(3,module)

		## Server application
		bu_app = elementFromFile(filename=os.path.join(self.fragmentdir,
			                     'msio/server_application.xml'))
		context.insert(4,bu_app)
		bu_app.set('instance',str(index))

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		if self.evbns == 'msio':
			module.text = "$XDAQ_ROOT/lib/libmstreamio2g.so"
		context.insert(5,module)

		## Set instance and url
		for app in context.findall(QN(self.xdaqns, 'Endpoint').text):
			if 'BU%d' in app.attrib['hostname']:
				app.set('hostname', app.get('hostname')%index)
			if 'BU%d' in app.attrib['port']:
				app.set('port', app.get('port')%index)
		context.set('url', context.get('url')%(index, index))

		## Set instance and url
		for app in context.findall(QN(self.xdaqns, 'Application').text):
			if app.attrib['class'] != "%s::BU"%self.evbns: continue
			app.set('instance', str(index))
			break

		return context

	## Gevb2g
	def makeRU(self, ruindex):
		fragmentname = 'RU/gevb2g/msio/RU_context_msio.xml'
		context = elementFromFile(self.fragmentdir+fragmentname)

		## Add policy
		addFragmentFromFile(target=context,
			                filename=os.path.join(self.fragmentdir,
			                'RU/gevb2g/msio/RU_policy_%s_msio.xml'%
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
		                    'RU/gevb2g/msio/RU_%s_application_msio.xml'%
		                    self.ptprot),
		                    index=2) ## add after the two endpoints

		## Configure IBV application:
		if self.setDynamicIBVConfig:
			self.configureIBVApplication(context, self.RUIBVConfig)

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		context.insert(3,module)

		## Add Inputemulator application
		inputemu_app = elementFromFile(filename=os.path.join(
			                    self.fragmentdir,
		                       'RU/gevb2g/msio/RU_inputemulator.xml'))
		inputemu_app.set('instance',str(ruindex))
		context.insert(4,inputemu_app)

		## RU application
		ru_app = elementFromFile(filename=os.path.join(self.fragmentdir,
			                     'RU/gevb2g/msio/RU_application_msio.xml'))
		context.insert(5,ru_app)
		ru_app.set('instance',str(ruindex))

		## Set instance and url
		for app in context.findall(QN(self.xdaqns, 'Endpoint').text):
			if 'RU%d' in app.attrib['hostname']:
				app.set('hostname', app.get('hostname')%ruindex)
			if 'RU%d' in app.attrib['port']:
				app.set('port', app.get('port')%ruindex)
		context.set('url', context.get('url')%(ruindex, ruindex))

		self.setPropertyInAppInContext(context, 'gevb2g::InputEmulator',
			                  'destinationClassInstance', str(ruindex),
			                  instance=ruindex)

		return context
	def makeEVM(self):
		index = 0
		fragmentname = 'EVM/EVM_context.xml'
		context = elementFromFile(os.path.join(self.fragmentdir,
			                                       fragmentname))

		## Add policy
		addFragmentFromFile(target=context,
			                filename=os.path.join(self.fragmentdir,
			                         'EVM/msio/EVM_policy_msio_%s.xml'%(
			                         self.ptprot)),
			                index=0)
		## Add builder network endpoint
		context.insert(3,Element(QN(self.xdaqns, 'Endpoint').text, {
			               'protocol':'%s'%self.ptprot ,
			               'service':"i2o",
			               'hostname':'EVM%d_I2O_HOST_NAME'%(index),
			               'port':'EVM%d_I2O_PORT'%(index),
			               'network':'infini'}))
		## Add builder network pt application
		addFragmentFromFile(target=context,
		                    filename=os.path.join(self.fragmentdir,
		                        'EVM/msio/EVM_%s_application_msio.xml'%(
		                        	                           self.ptprot)),
		                    index=4) ## add after the two endpoints

		## Configure IBV application:
		if self.setDynamicIBVConfig:
			self.configureIBVApplication(context, self.EVMIBVConfig)

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		context.insert(5,module)

		## Set instance and url
		for app in context.findall(QN(self.xdaqns, 'Application').text):
			if app.attrib['class'] != "%s::EVM"%self.evbns: continue
			app.set('instance', str(index))
			break
		context.set('url', context.get('url')%(index, index))

		## Change poolName in EVM application:
		self.setPropertyInAppInContext(context, 'gevb2g::EVM',
			                  'poolName', 'sibv')

		return context
	def makeBU(self, index):
		fragmentname = 'BU/BU_context.xml'
		context = elementFromFile(os.path.join(self.fragmentdir,
			                                      fragmentname))

		## Add policy
		addFragmentFromFile(target=context,
			                filename=os.path.join(self.fragmentdir,
			                	'BU/gevb2g/msio/BU_policy_%s_msio.xml'%(
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
		                        'BU/gevb2g/msio/BU_%s_application_msio.xml'%(
		                        self.ptprot)),
		                    index=2) ## add after the two endpoints

		## Configure IBV application:
		if self.setDynamicIBVConfig:
			self.configureIBVApplication(context, self.BUIBVConfig)

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		context.insert(3,module)

		## BU application
		bu_app = elementFromFile(filename=os.path.join(self.fragmentdir,
			                     'BU/gevb2g/msio/BU_application_msio.xml'))
		context.insert(4,bu_app)
		bu_app.set('instance',str(index))

		## Set instance and url
		for app in context.findall(QN(self.xdaqns, 'Application').text):
			if app.attrib['class'] != "%s::BU"%self.evbns: continue
			app.set('instance', str(index))
			break
		context.set('url', context.get('url')%(index, index))

		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libgevb2g.so"
		context.insert(5,module)

		return context

	def makeMSIOConfig(self, nclients=1, nservers=1,
		               destination='configuration.template.xml'):
		self.nclients = nclients
		self.nrus = nclients
		self.nservers = nservers
		self.nbus = nservers

		##
		self.makeSkeleton()

		if "ibv" in self.ptprot and self.setDynamicIBVConfig:
			self.configureIBV()
		else:
			self.readIBVConfig()

		if self.verbose > 1:
			self.printIBVConfig()


		## mstreamio
		if self.evbns == 'msio':
			self.addMSIOI2OProtocol()
			for index in xrange(self.nclients):
				self.config.append(self.makeClient(index))

			for index in xrange(self.nservers):
				self.config.append(self.makeServer(index))

		## gevb2g with input emulator
		if self.evbns == 'gevb2g':
			self.addI2OProtocol()
			self.addInputEmulatorProtocol()
			self.config.append(self.makeEVM())
			for index in xrange(self.nclients):
				self.config.append(self.makeRU(index))
			for index in xrange(self.nservers):
				self.config.append(self.makeBU(index))

		self.writeConfig(destination)
		if self.verbose>0: print 70*'-'


