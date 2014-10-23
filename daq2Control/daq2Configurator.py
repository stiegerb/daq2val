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
from daq2FEDConfiguration import daq2FEDConfiguration, FRLNode, RUNode


FEROL_OPERATION_MODES = {
      'ferol_emulator'  :('FEROL_MODE',
      	                  'FRL_AUTO_TRIGGER_MODE',
      	                  'GENERATOR_SOURCE'),
      'frl_autotrigger' :('FRL_MODE',
      	                  'FRL_AUTO_TRIGGER_MODE',
      	                  'GENERATOR_SOURCE'),
      'frl_gtpe_trigger':('FRL_MODE',
      	                  'FRL_GTPE_TRIGGER_MODE',
      	                  'GENERATOR_SOURCE'),
      'efed_slink_gtpe' :('SLINK_MODE',
      	                  'FRL_GTPE_TRIGGER_MODE',
      	                  '???')}
## New modes: FRL_MODE, FEDKIT_MODE, FEROL_MODE?

RU_STARTING_TID = 10
BU_STARTING_TID = 200

######################################################################
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
def elementFromFile(filename):
	"""
	Parses a .xml file and returns a xml.etree.ElementTree.Element object.
	Raises a RuntimeError if the parsing failed.
	"""
	element = None
	with open(filename, 'r') as file:
		text = file.read()
		try:
			element = ElementTree.XML(text)
		except ExpatError as e:
			printError('Error parsing xml file %s:\n%s' % (filename, str(e)) )
			raise RuntimeError('Error parsing xml file %s' % filename)
		file.close()
	return element
def addFragmentFromFile(target, filename, index=-1):
	element = elementFromFile(filename)
	if index<0: target.append(element)
	else:       target.insert(index, element)
	return element
def split_list(alist, wanted_parts=1):
	length = len(alist)
	return [ alist[i*length // wanted_parts: (i+1)*length // wanted_parts]
	         for i in range(wanted_parts) ]


######################################################################
def propertyInApp(application, prop_name, prop_value=None):
	try:
		## Assume here that there is only one element, which
		## is the properties
		properties = application[0]
		if not 'properties' in properties.tag:
			raise RuntimeError(
				  'Could not identify properties of %s application'
				  'in %s context.'%(application.attrib['class'],
				                 context.attrib['url']))
		## Extract namespace
		appns = re.match(r'\{(.*?)\}properties',
		                 properties.tag).group(1)
	except IndexError: ## i.e. app[0] didn't work
		raise RuntimeError(
			  'Application %s in context %s does not have'
			  'properties.'%(application.attrib['class'],
			  	             context.attrib['url']))

	prop = application.find(QN(appns,'properties').text+'/'+
		            QN(appns,prop_name).text)
	try:
		if prop_value is not None: # if value is given, set it
			prop.text = str(prop_value)
			return True
		else: # if not, return the existing value
			return prop.text
	except AttributeError:
		raise KeyError('Property %s of application %s '
			           'not found.'%(prop_name,
			           	             application.attrib['class']))


######################################################################
class daq2Configurator(object):
	'''
---------------------------------------------------------------------
  class daq2Configurator

---------------------------------------------------------------------
'''
	def __init__(self, fragmentdir, verbose=5):
		self.verbose     = verbose
		self.fragmentdir = (fragmentdir if fragmentdir.endswith('/') else
				            fragmentdir+'/')
		self.soapencns      = "http://schemas.xmlsoap.org/soap/encoding/"
		self.xsins          = "http://www.w3.org/2001/XMLSchema-instance"
		self.xdaqappns      = "urn:xdaq-application:%s"

		self.RUSendPoolSize = None ## in MB
		self.RUSendQPSize = None
		self.RUComplQPSize = None
		self.BURecvPoolSize = None ## in MB
		self.BURecvQPSize = None
		self.BUComplQPSize = None

		self.RUIBVConfig = tuple([None]*5)
		self.BUIBVConfig = tuple([None]*5)
		self.EVMIBVConfig = tuple([None]*5)

		self.setDynamicIBVConfig = False
		self.maxMessageSize = None


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

	def configureIBV(self):
		pass

	def readIBVConfig(self):
		## This currently only works for the MSIO configurator
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

		elif self.evbns == 'evb': ## TODO: Fix this
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
				            int(sPoolSize/self.maxMessageSize/self.nrus))
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

	def makeSkeleton(self):
		fragmentname = 'skeleton.xml'
		self.config = elementFromFile(self.fragmentdir+fragmentname)
		 ## Extract namespace
		self.xdaqns = re.match(r'\{(.*?)\}Partition',
		                       self.config.tag).group(1)
	def propertyInAppInContext(self, context, classname,
		                       prop_name, prop_value=None,
		                       instance=0):
		for app in context.findall(QN(self.xdaqns, 'Application').text):
			## find correct application
			if not app.attrib['class'] == classname: continue
			if not app.attrib['instance'] == str(instance): continue

			return propertyInApp(app, prop_name, prop_value)

		else:
			raise RuntimeError('Application %s not found in context %s.'%
				               (classname, context.attrib['url']))

	def setPropertyInAppInContext(self, context, classname,
		                          prop_name, prop_value,
		                          instance=0):
		self.propertyInAppInContext(context, classname,
			                        prop_name, prop_value,
			                        instance)
	def readPropertyFromAppInContext(self, context, classname,
		                             prop_name, instance=0):
		return self.propertyInAppInContext(context, classname,
			                               prop_name, None, instance)

	def setPropertyInApp(self, application, prop_name, prop_value):
		return propertyInApp(application, prop_name, prop_value)
	def readPropertyFromApp(self, application, prop_name):
		return propertyInApp(application, prop_name, None)

	def removePropertyInApp(self, application, prop_name):
		try:
			## Assume here that there is only one element, which
			## is the properties
			properties = application[0]
			if not 'properties' in properties.tag:
				raise RuntimeError(
					      'Could not identify properties of %s'
					      'application in %s context.'% (
					           application.attrib['class'],
					      	   context.attrib['url']))
			## Extract namespace
			appns = re.match(r'\{(.*?)\}properties',
				             properties.tag).group(1)
		except IndexError: ## i.e. application[0] didn't work
			raise RuntimeError(
				      'Application %s in context %s does not have'
				      'properties.'%(application.attrib['class'],
				      	             context.attrib['url']))

		prop = application.find(QN(appns,'properties').text+'/'+
			            QN(appns,prop_name).text)
		try:
			properties.remove(prop)
		except AssertionError:
			printError('Property %s of application %s not found.'%
				       (prop_name, application.attrib['class']),
				       instance=self)
			return
		except Exception, e:
			raise e
	def removePropertyInAppInContext(self, context, classname, prop_name):
		for app in context.findall(QN(self.xdaqns, 'Application').text):
			## find correct application
			if not app.attrib['class'] == classname: continue
			self.removePropertyInApp(app, prop_name)
		else:
			raise RuntimeError('Application %s not found in context %s.'%
				               (classname, context.attrib['url']))

	def configureIBVApplication(self, context, ibvConfig):
		sPoolSize, rPoolSize, cQPSize, sQPSize, rQPSize = ibvConfig
		try:
			self.setPropertyInAppInContext(context,
				                  classname='pt::ibv::Application',
				                  prop_name='senderPoolSize',
				                  prop_value=hex(sPoolSize))
			self.setPropertyInAppInContext(context,
				                  classname='pt::ibv::Application',
				                  prop_name='receiverPoolSize',
				                  prop_value=hex(rPoolSize))
			self.setPropertyInAppInContext(context,
				                  classname='pt::ibv::Application',
				                  prop_name='completionQueueSize',
				                  prop_value=str(cQPSize))
			self.setPropertyInAppInContext(context,
				                  classname='pt::ibv::Application',
				                  prop_name='sendQueuePairSize',
				                  prop_value=str(sQPSize))
			self.setPropertyInAppInContext(context,
				                  classname='pt::ibv::Application',
				                  prop_name='recvQueuePairSize',
				                  prop_value=str(rQPSize))
		except RuntimeError, e:
			if "not found in context" in e.strerror: pass
			else: raise e

	def addI2OProtocol(self):
		i2ons = "http://xdaq.web.cern.ch/xdaq/xsd/2004/I2OConfiguration-30"
		prot = Element(QN(i2ons, 'protocol').text)

		## Add EVM:
		prot.append(Element(QN(i2ons, 'target').text,
			                      {'class':'%s::EVM'%self.evbns ,
			                       'instance':"0", "tid":"1"}))
		## Add RUs:
		ru_instances_to_add = [n for n in range(self.nrus)]
		if self.evbns == 'evb': ru_instances_to_add.remove(0)
		for n in ru_instances_to_add:
			prot.append(Element(QN(i2ons, 'target').text,
				                  {'class':'%s::RU'%self.evbns ,
				                   'instance':"%d"%n,
				                   'tid':'%d'%(RU_STARTING_TID+n)}))
		## Add BUs:
		for n in xrange(self.nbus):
			prot.append(Element(QN(i2ons, 'target').text,
				                  {'class':'%s::BU'%self.evbns ,
				                   'instance':"%d"%n,
				                   'tid':'%d'%(BU_STARTING_TID+n)}))

		self.config.append(prot)
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

	def makeEFED(self, feds):
		startid = 50
		fragmentname = 'eFED_context.xml'
		eFED_context = elementFromFile(self.fragmentdir+fragmentname)

		efedns = self.xdaqappns%"d2s::FEDEmulator"
		eFED_app_fragment = elementFromFile(self.fragmentdir+
			                                'eFED_application.xml')
		for n,(fedid,slot) in enumerate(feds):
			eFED_app = deepcopy(eFED_app_fragment)
			eFED_app.set('id', str(50+n))
			eFED_app.set('instance', str(self.eFED_app_instance))
			eFED_app.find(QN(efedns, 'properties').text+'/'+
				          QN(efedns, 'slot').text).text = str(slot)
			eFED_app.find(QN(efedns, 'properties').text+'/'+
				          QN(efedns, 'FedSourceId').text).text = str(fedid)

			eFED_context.append(eFED_app)
			self.eFED_app_instance  += 1

		eFED_context.set('url', eFED_context.get('url')%(
			              self.eFED_crate_counter, self.eFED_crate_counter))

		self.eFED_crate_counter += 1
		return eFED_context
	def addEFEDs(self):
		for fed_group in self.FEDConfig.eFEDs:
			if len(fed_group) == 0: continue
			self.config.append(self.makeEFED(fed_group))

	def addGTPe(self):
		bitmask = '0b'
		if self.useEFEDs:
			bitmask += self.FEDConfig.nSlices*'1'
			partitionId = 3
		elif self.useFMMForDAQ2:
			bitmask += '1'
			partitionId = 0
		else:
			bitmask += '1000'
			partitionId = 0

		## convert '0b1000' into '0x8' etc.
		enableMask = str(hex(int(bitmask,2)))
		index = 0
		fragmentname = 'GTPe.xml'
		GTPE = elementFromFile(self.fragmentdir+fragmentname)

		gtpens = self.xdaqappns%'d2s::GTPeController'
		prop = GTPE.find(QN(self.xdaqns, 'Application').text+'/'+
			             QN(gtpens, 'properties').text)
		prop.find(QN(gtpens, 'daqPartitionId').text).text = str(partitionId)
		prop.find(QN(gtpens, 'detPartitionEnableMask').text).text = (
			                                                str(enableMask))
		prop.find(QN(gtpens, 'triggerRate').text).text            = str(100.)
		if self.verbose>0: print 70*'-'
		if self.verbose>0:
			print ('GTPe partitionId %d, enableMask %s (%s)'%
					   (partitionId,enableMask,bitmask))

		self.config.append(GTPE)
	def addFMM(self, cards):
		fragmentname = 'FMM_context.xml'
		FMM_context = elementFromFile(self.fragmentdir+fragmentname)

		fmmns = self.xdaqappns%"tts::FMMController"
		fmm_config = FMM_context.find(
			             QN(self.xdaqns,'Application').text +'/'+
			             QN(fmmns,'properties').text +'/'+
			             QN(fmmns,'config').text)
		fmm_config.attrib[QN(self.soapencns, 'arrayType').text] = (
			                            "xsd:ur-type[%d]"%(len(cards)))

		fmm_card_fragment = elementFromFile(self.fragmentdir+
			                                'FMM_card_eFED.xml')
		for n,(geoslot, inputmask, inputlabels,
			   outputlabels, label) in enumerate(cards):
			cmm_card = deepcopy(fmm_card_fragment)
			cmm_card.attrib[QN(self.soapencns, 'position').text] = '[%d]'%n
			cmm_card.find(QN(fmmns,'geoslot').text).text = (
				                            str(geoslot))
			cmm_card.find(QN(fmmns,'inputEnableMask').text).text = (
				                            str(inputmask))
			cmm_card.find(QN(fmmns,'inputLabels').text).text = (
				                            str(inputlabels))
			cmm_card.find(QN(fmmns,'outputLabels').text).text = (
				                            str(outputlabels))
			cmm_card.find(QN(fmmns,'label').text).text = (
				                            str(label))
			fmm_config.append(cmm_card)
		self.config.append(FMM_context)
	def createFMMCards(self):
		if self.verbose>0: print 70*'-'
		inputlabel_template = (("N/C;"+9*"%s;N/C;"+"%s") if
				                self.streams_per_ferol == 1 else
				               ("N/C;"+19*"%s;")[:-1])
		geoslots = [5,7,9]
		labels   = ['CSC_EFED', 'ECAL_EFED', 'TRACKER_EFED']

		cards = []
		for n,fed_group in enumerate(self.FEDConfig.eFEDs):
			## Construct input label and mask
			feds = [fed for fed,_ in fed_group]
			filler = (tuple((10-len(feds))*['N/C']) if
				      self.streams_per_ferol == 1 else
				      tuple((19-len(feds))*['N/C']))
			inputlabel = inputlabel_template%(tuple(
				            [str(fed) for fed in feds]) + filler)
			# print inputlabel
			bitmask = '0b'
			for item in reversed(inputlabel.split(';')):
				if item == 'N/C': bitmask += '0'
				else            : bitmask += '1'

			## convert '0b00000000000010101010' into '0xaa'
			inputmask = str(hex(int(bitmask,2)))

			outputlabel = "GTPe:%d;N/C;N/C;N/C" % n
			geoslot     = geoslots[n]
			label       = labels[n]
			cards.append([geoslot, inputmask, inputlabel,
				          outputlabel, label])
			if self.verbose>0:
				print (' %d %-14s %-4s (%s)  %s   %s' %
				        (geoslot, label, inputmask, bitmask,
				         inputlabel, outputlabel))

		return cards
	def createEmptyFMMCard(self):
		geoslot     = 5
		inputmask   = "0x400"
		inputlabel  = ("N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;950;"
				       "N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C")
		outputlabel = "GTPe:3;N/C;N/C;N/C"
		label       = "CSC_EFED"

		if self.useFMMForDAQ2:
			geoslot     = 5
			inputmask   = "0x1" ## for crate 32
			inputlabel  = ("N/C;1005;1006;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;"
					       "N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C")
			outputlabel = "GTPe:3;N/C;N/C;N/C"
			label       = "BPIX_GTPE"

		return [[geoslot, inputmask, inputlabel, outputlabel, label]]

	def makeRU(self, ru):
		fragmentname = 'RU/%s/RU_context.xml'%self.evbns
		ru_context = elementFromFile(self.fragmentdir+fragmentname)

		## Add policy
		addFragmentFromFile(target=ru_context, filename=self.fragmentdir+
			                '/RU/%s/RU_policy_%s.xml'%
			                (self.evbns,self.ptprot), index=0)
		polns = "http://xdaq.web.cern.ch/xdaq/xsd/2013/XDAQPolicy-10"
		for element in ru_context.findall(QN(polns,"policy").text+'/'+
			                              QN(polns,"element").text):
			if 'RU%d' in element.get('pattern'):
				element.set('pattern',element.get('pattern').replace(
					                         'RU%d', 'RU%d'%(ru.index)))
		## Add builder network endpoint
		ru_context.insert(3,Element(QN(self.xdaqns, 'Endpoint').text,
			              {'protocol':'%s'%self.ptprot ,
			               'service':"i2o",
			               'hostname':'RU%d_I2O_HOST_NAME'%(ru.index),
			               'port':'RU%d_I2O_PORT'%(ru.index),
			               'network':"infini"}))
		## Add builder network pt application
		addFragmentFromFile(target=ru_context,
		                    filename=self.fragmentdir+
		                    '/RU/%s/RU_%s_application.xml'%
		                    (self.evbns,self.ptprot),
		                    index=4) ## add after the two endpoints
		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		ru_context.insert(5,module)

		## Add frl routing
		feds_to_add = ru.getFedIds()
		pt_frl_ns = self.xdaqappns%"pt::frl::Application"
		frl_routing_element = ru_context.find(
			    QN(self.xdaqns,'Application').text +'/'+
			    QN(pt_frl_ns,'properties').text +'/'+
			    QN(pt_frl_ns,'frlRouting').text)
		frl_routing_element.attrib[QN(self.soapencns, 'arrayType').text] = (
			    "xsd:ur-type[%d]"%(len(feds_to_add)))
		item_element = elementFromFile(self.fragmentdir+
			                           '/RU/RU_frl_routing.xml')
		classname_to_add = ("%s::EVM"%self.evbns if
			                ru.index == 0 and self.evbns == 'evb' else
			                "%s::RU"%self.evbns)
		item_element.find(QN(pt_frl_ns,'className').text).text = (
			                                             classname_to_add)
		item_element.find(QN(pt_frl_ns,'instance').text).text = (
			                                             "%d"%ru.index)

		for n,fed in enumerate(feds_to_add):
			item_to_add = deepcopy(item_element)
			item_to_add.attrib[QN(self.soapencns, 'position').text] = (
				                                                '[%d]'%n)
			item_to_add.find(QN(pt_frl_ns,'fedid').text).text = str(fed)
			frl_routing_element.append(item_to_add)

		## RU application
		ru_app = elementFromFile(filename=self.fragmentdir+
			                     '/RU/%s/RU_application.xml'%self.evbns)
		## make the first one an EVM in case of EvB
		if self.evbns == 'evb' and ru.index == 0:
			ru_app = elementFromFile(filename=self.fragmentdir+
				                     '/RU/evb/RU_application_EVM.xml')
		ru_context.insert(7,ru_app)
		ru_app.set('instance',str(ru.index))

		## In case of EvB, add expected fedids
		if self.evbns == 'evb':
			ruevbappns = (self.xdaqappns%'evb::RU' if
				          ru.index>0 else self.xdaqappns%'evb::EVM')
			fedSourceIds = ru_app.find(QN(ruevbappns, 'properties').text+'/'+
				                       QN(ruevbappns, 'fedSourceIds').text)
			fedSourceIds.attrib[QN(self.soapencns, 'arrayType').text] = (
				                       "xsd:ur-type[%d]"%(len(feds_to_add)))
			item_element = fedSourceIds.find(QN(ruevbappns,'item').text)
			fedSourceIds.remove(item_element)
			for n,fed in enumerate(feds_to_add):
				item_to_add = deepcopy(item_element)
				item_to_add.attrib[QN(self.soapencns, 'position').text] = (
					                                                '[%d]'%n)
				item_to_add.text = str(fed)
				fedSourceIds.append(item_to_add)

		## Add libdat2 module in case of udapl
		if self.ptprot == 'udapl':
			module = Element(QN(self.xdaqns, 'Module').text)
			module.text = "/usr/lib64/libdat2.so"
			ru_context.insert(8,module)

		## Set instance and url
		for app in ru_context.findall(QN(self.xdaqns, 'Endpoint').text):
			if 'RU%d' in app.attrib['hostname']:
				app.set('hostname', app.get('hostname')%ru.index)
			if 'RU%d' in app.attrib['port']:
				app.set('port', app.get('port')%ru.index)
		ru_context.set('url', ru_context.get('url')%(ru.index, ru.index))

		return ru_context
	def addRUs(self, nrus):
		for ru in self.FEDConfig.rus:
			self.config.append(self.makeRU(ru))
	def makeEVM(self):
		index = 0
		fragmentname = 'EVM/EVM_context.xml'
		evm_context = elementFromFile(self.fragmentdir+fragmentname)

		## Add policy
		addFragmentFromFile(target=evm_context,
			                filename=self.fragmentdir+
			                         '/EVM/EVM_policy_%s.xml'%(self.ptprot),
			                index=0)
		## Add builder network endpoint
		evm_context.insert(3,Element(QN(self.xdaqns, 'Endpoint').text, {
			               'protocol':'%s'%self.ptprot ,
			               'service':"i2o",
			               'hostname':'EVM%d_I2O_HOST_NAME'%(index),
			               'port':'EVM%d_I2O_PORT'%(index),
			               'network':'infini'}))
		## Add builder network pt application
		addFragmentFromFile(target=evm_context,
		                    filename=self.fragmentdir+
		                        '/EVM/EVM_%s_application.xml'%(self.ptprot),
		                    index=4) ## add after the two endpoints
		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		evm_context.insert(5,module)

		## Add libdat2 module in case of udapl
		if self.ptprot == 'udapl':
			module = Element(QN(self.xdaqns, 'Module').text)
			module.text = "/usr/lib64/libdat2.so"
			evm_context.insert(9,module)

		## Set instance and url
		for app in evm_context.findall(QN(self.xdaqns, 'Application').text):
			if app.attrib['class'] != "%s::EVM"%self.evbns: continue
			app.set('instance', str(index))
			break

		evm_context.set('url', evm_context.get('url')%(index, index))

		return evm_context
	def addEVM(self):
		self.config.append(self.makeEVM())

	def makeBU(self, index):
		fragmentname = 'BU/BU_context.xml'
		bu_context = elementFromFile(self.fragmentdir+fragmentname)

		## Add policy
		addFragmentFromFile(target=bu_context,
			                filename=self.fragmentdir+(
			                	     '/BU/%s/BU_policy_%s.xml'%(
			                	      self.evbns,self.ptprot)),
			                index=0)
		## Add builder network endpoint
		bu_context.insert(3,Element(QN(self.xdaqns, 'Endpoint').text, {
			                        'protocol':'%s'%self.ptprot ,
			                        'service':'i2o',
			                        'hostname':'BU%d_I2O_HOST_NAME'%(index),
			                        'port':'BU%d_I2O_PORT'%(index),
			                        'network':'infini'}))
		## Add builder network pt application
		addFragmentFromFile(target=bu_context,
		                    filename=self.fragmentdir+(
		                             '/BU/BU_%s_application.xml'%(
		                             self.ptprot)),
		                    index=4) ## add after the two endpoints
		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		bu_context.insert(5,module)

		## BU application
		bu_app = elementFromFile(filename=self.fragmentdir+(
			                     '/BU/%s/BU_application.xml'%self.evbns))
		bu_context.insert(7,bu_app)
		bu_app.set('instance',str(index))

		## Set instance and url
		for app in bu_context.findall(QN(self.xdaqns, 'Application').text):
			if app.attrib['class'] != "%s::BU"%self.evbns: continue
			app.set('instance', str(index))
			break
		bu_context.set('url', bu_context.get('url')%(index, index))

		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = ("$XDAQ_ROOT/lib/libevb.so" if
			           self.evbns == 'evb' else
			           "$XDAQ_ROOT/lib/libgevb2g.so")
		bu_context.insert(8,module)

		## Add libdat2 module in case of udapl
		if self.ptprot == 'udapl':
			module = Element(QN(self.xdaqns, 'Module').text)
			module.text = "/usr/lib64/libdat2.so"
			bu_context.insert(9,module)

		return bu_context
	def addBUs(self, nbus):
		for n in xrange(nbus):
			self.config.append(self.makeBU(n))

	def writeConfig(self, destination):
		with open(destination, 'w') as file:
			file.write(ElementTree.tostring(self.config))
			file.close()
		## pass through xmllint for formatting
		subprocess.call(['xmllint', '--format', '--nsclean', destination,
		                 '-o', destination])
		with open(destination, 'r') as oldfile:
			lines = oldfile.readlines()
			lines.remove('<?xml version="1.0"?>\n')
			with open(destination+'temp', 'w') as newfile:
				for line in lines:
					newfile.write(line)
		subprocess.call(['mv', '-f', destination+'temp', destination])
		if self.verbose>0: print 70*'-'
		if self.verbose>0: print ' Wrote config to %s' % destination

	def makeConfig(self, nferols=8, streams_per_ferol=2, nrus=1, nbus=2,
		           destination='configuration.template.xml'):
		self.nrus              = nrus
		self.nbus              = nbus
		self.nferols           = nferols
		self.streams_per_ferol = streams_per_ferol

		self.FEDConfig = daq2FEDConfiguration(
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

		self.writeConfig(destination)
		if self.verbose>0: print 70*'-'


