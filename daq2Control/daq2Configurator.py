import subprocess, re
from copy import deepcopy

from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import QName as QN
from xml.parsers.expat import ExpatError

from daq2Utils import printError

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
	return [ alist[i*length // wanted_parts: (i+1)*length // wanted_parts] for i in range(wanted_parts) ]

######################################################################
FEDIDS    = [900 + n for n in range(96)]
FEROL_OPERATION_MODES = {'ferol_emulator'  :('FEROL_EMULATOR_MODE', None),
                         'frl_autotrigger' :('FRL_EMULATOR_MODE',  'FRL_AUTO_TRIGGER_MODE'),
                         'frl_gtpe_trigger':('FRL_EMULATOR_MODE',  'FRL_GTPE_TRIGGER_MODE'),
                         'efed_slink_gtpe' :('SLINK_MODE',         'FRL_GTPE_TRIGGER_MODE')}

######################################################################
class daq2Configurator(object):
	'''
---------------------------------------------------------------------
  class daq2Configurator

---------------------------------------------------------------------
'''
	def __init__(self, fragmentdir, verbose=5):
		self.verbose     = verbose
		self.fragmentdir = fragmentdir if fragmentdir.endswith('/') else fragmentdir+'/'
		self.soapencns      = "http://schemas.xmlsoap.org/soap/encoding/"
		self.xsins          = "http://www.w3.org/2001/XMLSchema-instance"
		self.xdaqappns      = "urn:xdaq-application:%s"

		## These should be passed as options
		self.enablePauseFrame  = True
		self.disablePauseFrame = False
		self.setCWND = -1
		self.evbns          = 'gevb2g' ## 'gevb2g' or 'evb'
		self.ptprot         = 'ibv' ## or 'ibv' or 'udapl'
		self.operation_mode = 'ferol_emulator'
		self.ferolRack      = 1 ## 0,1,2,3, corresponding to dvfrlpc-c2f32-[09,11,13]-01.cms (0 is all three)

		self.useGTPe        = False
		self.useEFEDs       = False

		## These should be passed as arguments
		self.nrus              = 1
		self.nbus              = 2
		self.nferols           = 8
		self.streams_per_ferol = 2

		## Counters
		self.eFED_crate_counter = 0
		self.eFED_app_instance  = 0

	## Ferol to RU distribution
	def fedIdsForRUIndex(self, index):
		"""Returns the fed ids mapped to a given RU"""
		ferolindices = split_list(range(self.nferols), self.nrus)[index]
		fedids = [fed for pair in map(self.fedIdsForFEROLIndex, ferolindices) for fed in pair] ## all fedids for this RU
		if self.streams_per_ferol == 2: ## take all fedids
			return fedids
		if self.streams_per_ferol == 1: ## take only every second fedid
			return fedids[::2]
	def fedIdsForFEROLIndex(self, index):
		"""Returns the fed ids mapped to a given FEROL"""
		return FEDIDS[2*index], FEDIDS[2*index+1]
	def getAllFedIds(self):
		fedrange = [FEDIDS[n] for n in range(2*self.nferols)]
		allfedids = fedrange if self.streams_per_ferol==2 else fedrange[::2]
		return allfedids
		# return reduce(lambda x,y:x+y, [self.fedIdsForRUIndex(n) for n in range(self.nrus)])

	## FED/slice distribution:
	def makeFEDConfiguration(self):
		fedid0 = FEDIDS[0]
		## FED to eFED slot distribution:
		fed_to_efedslot = {}
		for n,fed in enumerate(FEDIDS):
			if fed >  fedid0+23: break
			if fed <  fedid0+8:                      fed_to_efedslot[fed] = 2*(n+1)
			if fed >= fedid0+8  and fed < fedid0+16: fed_to_efedslot[fed] = 2*(n+1)-16
			if fed >= fedid0+16 and fed < fedid0+24: fed_to_efedslot[fed] = 2*(n+1)-32

		## FED to eFED/FMM slice distribution
		allfedids = self.getAllFedIds()
		FEDs = []
		FEDs += [(fed, 0, fed_to_efedslot[fed]) for fed in allfedids if fed <  fedid0+8 ]
		FEDs += [(fed, 1, fed_to_efedslot[fed]) for fed in allfedids if fed >= fedid0+8  and fed < fedid0+16]
		FEDs += [(fed, 2, fed_to_efedslot[fed]) for fed in allfedids if fed >= fedid0+16 and fed < fedid0+24]

		if self.verbose>1: print 70*'-'
		if self.verbose>1:
			print ' FED | Slice | eFED slot'
			for fed,slice,efed_slot in FEDs:
				print ' %3d | %d     | %2d' %(fed,slice,efed_slot)
		self.FEDConfiguration = FEDs
		efeds = []
		efeds.append([(fed, slot) for fed,slice,slot in self.FEDConfiguration if slice == 0])
		efeds.append([(fed, slot) for fed,slice,slot in self.FEDConfiguration if slice == 1])
		efeds.append([(fed, slot) for fed,slice,slot in self.FEDConfiguration if slice == 2])
		self.eFEDs = [fed_group for fed_group in efeds if len(fed_group)>0]
		self.nSlices = len(self.eFEDs)

	def makeSkeleton(self):
		fragmentname = 'skeleton.xml'
		self.config = elementFromFile(self.fragmentdir+fragmentname)
		self.xdaqns = re.match(r'\{(.*?)\}Partition', self.config.tag).group(1) ## Extract namespace
	def setPropertyInApp(self, context, classname, prop_name, prop_value):
		for app in context.findall(QN(self.xdaqns, 'Application').text):
			if not app.attrib['class'] == classname: continue ## find correct application
			try:
				properties = app[0] ## Assume here that there is only one element, which is the properties
				if not 'properties' in properties.tag:
					raise RuntimeError('Could not identify properties of %s application in %s context.'%(app.attrib['class'], context.attrib['url']))
				appns = re.match(r'\{(.*?)\}properties', properties.tag).group(1) ## Extract namespace
			except IndexError: ## i.e. app[0] didn't work
				raise RuntimeError('Application %s in context %s does not have properties.'%(app.attrib['class'], context.attrib['url']))

			prop = app.find(QN(appns,'properties').text+'/'+QN(appns,prop_name).text)
			try:
				prop.text = str(prop_value)
			except AttributeError:
				raise KeyError('Property %s of application %s in context %s not found.'%(prop_name, app.attrib['class'], context.attrib['url']))
			break

		else:
			raise RuntimeError('Application %s not found in context %s.'%(classname, context.attrib['url']))
	def removePropertyInApp(self, context, classname, prop_name):
		for app in context.findall(QN(self.xdaqns, 'Application').text):
			if not app.attrib['class'] == classname: continue ## find correct application
			try:
				properties = app[0] ## Assume here that there is only one element, which is the properties
				if not 'properties' in properties.tag:
					raise RuntimeError('Could not identify properties of %s application in %s context.'%(app.attrib['class'], context.attrib['url']))
				appns = re.match(r'\{(.*?)\}properties', properties.tag).group(1) ## Extract namespace
			except IndexError: ## i.e. app[0] didn't work
				raise RuntimeError('Application %s in context %s does not have properties.'%(app.attrib['class'], context.attrib['url']))

			prop = app.find(QN(appns,'properties').text+'/'+QN(appns,prop_name).text)
			try:
				properties.remove(prop)
			except AttributeError:
				raise KeyError('Property %s of application %s in context %s not found.'%(prop_name, app.attrib['class'], context.attrib['url']))
			break

		else:
			raise RuntimeError('Application %s not found in context %s.'%(classname, context.attrib['url']))

	def getFerolSourceIp(self, index):
		rack_to_host = {1:19,2:28,3:37}
		if self.ferolRack == 0:
			if index < 16:
				return 'dvferol-c2f32-%d-%02d.dvfbs2v0.cms' % (rack_to_host[1], (index+1))
			if index >= 16 and index < 32:
				return 'dvferol-c2f32-%d-%02d.dvfbs2v0.cms' % (rack_to_host[2], (index-15))
			if index >= 32:
				return 'dvferol-c2f32-%d-%02d.dvfbs2v0.cms' % (rack_to_host[3], (index-31))
		elif self.ferolRack == 1:
			if index < 16:
				return 'dvferol-c2f32-%d-%02d.dvfbs2v0.cms' % (rack_to_host[1], (index+1))
			if index >= 16 and index < 32:
				return 'dvferol-c2f32-%d-%02d.dvfbs2v0.cms' % (rack_to_host[2], (index-15))
			if index >= 32:
				return 'dvferol-c2f32-%d-%02d.dvfbs2v0.cms' % (rack_to_host[3], (index-31))
		elif self.ferolRack == 2:
			if index < 16:
				return 'dvferol-c2f32-%d-%02d.dvfbs2v0.cms' % (rack_to_host[2], (index+1))
			if index >= 16 and index < 32:
				return 'dvferol-c2f32-%d-%02d.dvfbs2v0.cms' % (rack_to_host[3], (index-15))
		else:
			if index < 16:
				return 'dvferol-c2f32-%d-%02d.dvfbs2v0.cms' % (rack_to_host[self.ferolRack], (index+1))
		## TODO Automatize retrieving of basename and datanet name, see ~pzejdl/src/ferol/dvfrlpc-C2F32-09-01/feroltest/getFerolIP.sh

	def addI2OProtocol(self):
		i2ons = "http://xdaq.web.cern.ch/xdaq/xsd/2004/I2OConfiguration-30"
		prot = Element(QN(i2ons, 'protocol').text)

		## Add EVM:
		prot.append(Element(QN(i2ons, 'target').text, {'class':'%s::EVM'%self.evbns , 'instance':"0", "tid":"1"}))
		## Add RUs:
		ru_starting_tid = 10
		ru_instances_to_add = [n for n in range(self.nrus)]
		if self.evbns == 'evb': ru_instances_to_add.remove(0)
		for n in ru_instances_to_add:
			prot.append(Element(QN(i2ons, 'target').text, {'class':'%s::RU'%self.evbns , 'instance':"%d"%n, "tid":"%d"%(ru_starting_tid+n)}))
		## Add BUs:
		bu_starting_tid = 30
		for n in xrange(self.nbus):
			prot.append(Element(QN(i2ons, 'target').text, {'class':'%s::BU'%self.evbns , 'instance':"%d"%n, "tid":"%d"%(bu_starting_tid+2*n)}))

		self.config.append(prot)
	def addGTPe(self):
		bitmask = '0b'
		if self.useEFEDs:
			bitmask += self.nSlices*'1'
			partitionId = 3
		else:
			bitmask += '1000'
			partitionId = 0

		enableMask = str(hex(int(bitmask,2))) ## convert '0b1000' into '0x8' etc.
		index = 0
		fragmentname = 'GTPe.xml'
		GTPE = elementFromFile(self.fragmentdir+fragmentname)

		gtpens = self.xdaqappns%'d2s::GTPeController'
		prop = GTPE.find(QN(self.xdaqns, 'Application').text+'/'+QN(gtpens, 'properties').text)
		prop.find(QN(gtpens, 'daqPartitionId').text).text         = str(partitionId)
		prop.find(QN(gtpens, 'detPartitionEnableMask').text).text = str(enableMask)
		prop.find(QN(gtpens, 'triggerRate').text).text            = str(100.)
		if self.verbose>0: print 70*'-'
		if self.verbose>0: print 'GTPe partitionId %d, enableMask %s (%s)' %(partitionId,enableMask,bitmask)

		self.config.append(GTPE)

	def makeFerolController(self, slotNumber, fedId0, fedId1, sourceIp, nStreams=1):
		fragmentname = 'FerolController.xml'
		ferol = elementFromFile(self.fragmentdir+fragmentname)
		classname = 'ferol::FerolController'
		physSlot = slotNumber
		if physSlot > 16:
			physSlot -= 16 ## restart physical slot number for crate 3 if used together with the other crates
		self.setPropertyInApp(ferol, classname, 'slotNumber',      physSlot)
		self.setPropertyInApp(ferol, classname, 'expectedFedId_0', fedId0)
		self.setPropertyInApp(ferol, classname, 'expectedFedId_1', fedId1)
		self.setPropertyInApp(ferol, classname, 'SourceIP',        sourceIp)

		if nStreams == 1:
			self.setPropertyInApp(ferol, classname, 'TCP_CWND_FED0', 135000)
			self.setPropertyInApp(ferol, classname, 'TCP_CWND_FED1', 135000)
		if nStreams == 2:
			self.setPropertyInApp(ferol, classname, 'TCP_CWND_FED0', 62500)
			self.setPropertyInApp(ferol, classname, 'TCP_CWND_FED1', 62500)

		if nStreams == 1:
			self.setPropertyInApp(ferol, classname, 'enableStream0', 'true')
			self.setPropertyInApp(ferol, classname, 'enableStream1', 'false')
		if nStreams == 2:
			self.setPropertyInApp(ferol, classname, 'enableStream0', 'true')
			self.setPropertyInApp(ferol, classname, 'enableStream1', 'true')

		if self.disablePauseFrame: self.setPropertyInApp(ferol, classname, 'ENA_PAUSE_FRAME', 'false')
		if self.enablePauseFrame:  self.setPropertyInApp(ferol, classname, 'ENA_PAUSE_FRAME', 'true')
		if self.setCWND >= 0:      self.setPropertyInApp(ferol, classname, 'TCP_CWND_FED0', self.setCWND)
		if self.setCWND >= 0:      self.setPropertyInApp(ferol, classname, 'TCP_CWND_FED1', self.setCWND)

		## Distribute the streams to the RUs and their endpoints
		ruindex = (slotNumber-1)/((self.nferols)//self.nrus) ## split them up evenly, e.g. 8 ferols on 4 rus: 0,0,1,1,2,2,3,3
		if self.verbose>0: print "ferol %2d, streaming to RU%d, fedids %3d/%3d"% (slotNumber, ruindex, fedId0, fedId1)
		self.setPropertyInApp(ferol, classname, 'DestinationIP', 'RU%d_FRL_HOST_NAME'%ruindex)
		self.setPropertyInApp(ferol, classname, 'TCP_DESTINATION_PORT_FED0', 'RU%d_FRL_PORT'%ruindex)
		self.setPropertyInApp(ferol, classname, 'TCP_DESTINATION_PORT_FED1', '60600')
		if self.streams_per_ferol==1 and slotNumber%2==0: ## route every second one to port 60600 if there is only one stream per RU
			self.setPropertyInApp(ferol, classname, 'TCP_DESTINATION_PORT_FED0', '60600')
		try:
			self.setPropertyInApp(ferol, classname, 'OperationMode',  FEROL_OPERATION_MODES[self.operation_mode][0])
			if FEROL_OPERATION_MODES[self.operation_mode][1] is not None:
				self.setPropertyInApp(ferol, classname, 'FrlTriggerMode', FEROL_OPERATION_MODES[self.operation_mode][1])
			else:
				self.removePropertyInApp(ferol, classname, 'FrlTriggerMode')
		except KeyError as e:
			printError('Unknown ferol operation mode "%s"'%self.operation_mode, instance=self)
			raise RuntimeError('Unknown ferol operation mode')


		ferol.set('url', ferol.get('url')%(slotNumber-1, slotNumber-1))

		return ferol
	def addFerolControllers(self, nferols, streams_per_ferol=1):
		if self.verbose>0: print 70*'-'
		for n in xrange(nferols):
			fedids = self.fedIdsForFEROLIndex(n)
			self.config.append(self.makeFerolController(slotNumber=n+1, fedId0=fedids[0], fedId1=fedids[1], sourceIp=self.getFerolSourceIp(n), nStreams=streams_per_ferol))

	def makeEFED(self, feds):
		startid = 50
		fragmentname = 'eFED_context.xml'
		eFED_context = elementFromFile(self.fragmentdir+fragmentname)

		efedns = self.xdaqappns%"d2s::FEDEmulator"
		eFED_app_fragment = elementFromFile(self.fragmentdir+'eFED_application.xml')
		for n,(fedid,slot) in enumerate(feds):
			eFED_app = deepcopy(eFED_app_fragment)
			eFED_app.set('id', str(50+n))
			eFED_app.set('instance', str(self.eFED_app_instance))
			eFED_app.find(QN(efedns, 'properties').text+'/'+QN(efedns, 'slot').text).text = str(slot)
			eFED_app.find(QN(efedns, 'properties').text+'/'+QN(efedns, 'FedSourceId').text).text = str(fedid)

			eFED_context.append(eFED_app)
			self.eFED_app_instance  += 1

		eFED_context.set('url', eFED_context.get('url')%(self.eFED_crate_counter, self.eFED_crate_counter))

		self.eFED_crate_counter += 1
		return eFED_context
	def addEFEDs(self):
		for fed_group in self.eFEDs:
			if len(fed_group) == 0: continue
			self.config.append(self.makeEFED(fed_group))

	def addFMM(self, cards):
		fragmentname = 'FMM_context.xml'
		FMM_context = elementFromFile(self.fragmentdir+fragmentname)

		fmmns = self.xdaqappns%"tts::FMMController"
		fmm_config = FMM_context.find(QN(self.xdaqns,'Application').text +'/'+ QN(fmmns,'properties').text +'/'+ QN(fmmns,'config').text)
		fmm_config.attrib[QN(self.soapencns, 'arrayType').text] = "xsd:ur-type[%d]"%(len(cards))

		fmm_card_fragment = elementFromFile(self.fragmentdir+'FMM_card_eFED.xml')
		for n,(geoslot, inputmask, inputlabels, outputlabels, label) in enumerate(cards):
			cmm_card = deepcopy(fmm_card_fragment)
			cmm_card.attrib[QN(self.soapencns, 'position').text] = '[%d]'%n
			cmm_card.find(QN(fmmns,'geoslot').text).text         = str(geoslot)
			cmm_card.find(QN(fmmns,'inputEnableMask').text).text = str(inputmask)
			cmm_card.find(QN(fmmns,'inputLabels').text).text     = str(inputlabels)
			cmm_card.find(QN(fmmns,'outputLabels').text).text    = str(outputlabels)
			cmm_card.find(QN(fmmns,'label').text).text           = str(label)
			fmm_config.append(cmm_card)
		self.config.append(FMM_context)
	def createFMMCards(self):
		if self.verbose>0: print 70*'-'
		inputlabel_template = ("N/C;"+9*"%s;N/C;"+"%s") if self.streams_per_ferol == 1 else ("N/C;"+19*"%s;")[:-1]
		geoslots = [5,7,9]
		labels   = ['CSC_EFED', 'ECAL_EFED', 'TRACKER_EFED']

		cards = []
		for n,fed_group in enumerate(self.eFEDs):
			## Construct input label and mask
			feds = [fed for fed,_ in fed_group]
			filler = tuple((10-len(feds))*['N/C']) if self.streams_per_ferol == 1 else tuple((19-len(feds))*['N/C'])
			inputlabel = inputlabel_template%(tuple([str(fed) for fed in feds]) + filler)
			# print inputlabel
			bitmask = '0b'
			for item in reversed(inputlabel.split(';')):
				if item == 'N/C': bitmask += '0'
				else            : bitmask += '1'

			inputmask = str(hex(int(bitmask,2))) ## convert '0b00000000000010101010' into '0xaa'

			outputlabel = "GTPe:%d;N/C;N/C;N/C" % n
			geoslot     = geoslots[n]
			label       = labels[n]
			cards.append([geoslot, inputmask, inputlabel, outputlabel, label])
			if self.verbose>0: print ' %d %-14s %-4s (%s)  %s   %s' % (geoslot, label, inputmask, bitmask, inputlabel, outputlabel)

		# inputlabels      = ["N/C;900;N/C;902;N/C;904;N/C;906;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C",
		#                     "N/C;908;N/C;910;N/C;912;N/C;914;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C",
		#                     "N/C;N/C;N/C;918;919;920;921;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C"]
		# outputlabels     = ["GTPe:0;N/C;N/C;N/C",
        #                     "GTPe:1;N/C;N/C;N/C",
        #                     "GTPe:2;N/C;N/C;N/C"]
		# geoslots         = [5,7,9]
		# inputEnableMasks = ['0xAA', '0xAA', '0x78']
		# return zip(geoslots, inputEnableMasks, inputlabels, outputlabels, labels)
		return cards
	def createEmptyFMMCard(self):
		geoslot     = 5
		inputmask   = "0x400"
		inputlabel  = "N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;950;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C;N/C"
		outputlabel = "GTPe:3;N/C;N/C;N/C"
		label       = "CSC_EFED"
		return [[geoslot, inputmask, inputlabel, outputlabel, label]]

	def makeRU(self, index):
		fragmentname = 'RU/%s/RU_context.xml'%self.evbns
		ru_context = elementFromFile(self.fragmentdir+fragmentname)

		## Add policy
		addFragmentFromFile(target=ru_context, filename=self.fragmentdir+'/RU/%s/RU_policy_%s.xml'%(self.evbns,self.ptprot), index=0)
		polns = "http://xdaq.web.cern.ch/xdaq/xsd/2013/XDAQPolicy-10"
		for element in ru_context.findall(QN(polns,"policy").text+'/'+QN(polns,"element").text):
			if 'RU%d' in element.get('pattern'): element.set('pattern',element.get('pattern').replace('RU%d', 'RU%d'%(index)))
		## Add builder network endpoint
		ru_context.insert(3,Element(QN(self.xdaqns, 'Endpoint').text, {'protocol':'%s'%self.ptprot , 'service':"i2o", "hostname":"RU%d_I2O_HOST_NAME"%(index), "port":"RU%d_I2O_PORT"%(index), "network":"infini"}))
		## Add builder network pt application
		addFragmentFromFile(target=ru_context, filename=self.fragmentdir+'/RU/%s/RU_%s_application.xml'%(self.evbns,self.ptprot), index=4) ## add after the two endpoints
		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		ru_context.insert(5,module)

		## Add frl routing
		pt_frl_ns = self.xdaqappns%"pt::frl::Application"
		frl_routing_element = ru_context.find(QN(self.xdaqns,'Application').text +'/'+ QN(pt_frl_ns,'properties').text +'/'+ QN(pt_frl_ns,'frlRouting').text)
		frl_routing_element.attrib[QN(self.soapencns, 'arrayType').text] = "xsd:ur-type[%d]"%(self.nferols*self.streams_per_ferol/self.nrus)
		item_element = elementFromFile(self.fragmentdir+'/RU/RU_frl_routing.xml')
		classname_to_add = "%s::EVM"%self.evbns if index == 0 and self.evbns == 'evb' else "%s::RU"%self.evbns
		item_element.find(QN(pt_frl_ns,'className').text).text = classname_to_add
		item_element.find(QN(pt_frl_ns,'instance').text).text = "%d"%index

		feds_to_add = self.fedIdsForRUIndex(index)
		for n,fed in enumerate(feds_to_add):
			item_to_add = deepcopy(item_element)
			item_to_add.attrib[QN(self.soapencns, 'position').text] = '[%d]'%n
			item_to_add.find(QN(pt_frl_ns,'fedid').text).text = str(fed)
			frl_routing_element.append(item_to_add)

		## RU application
		ru_app = elementFromFile(filename=self.fragmentdir+'/RU/%s/RU_application.xml'%self.evbns)
		if self.evbns == 'evb' and index == 0: ## make the first one an EVM in case of EvB
			ru_app = elementFromFile(filename=self.fragmentdir+'/RU/evb/RU_application_EVM.xml')
		ru_context.insert(7,ru_app)
		ru_app.set('instance',str(index))

		## In case of EvB, add expected fedids
		if self.evbns == 'evb':
			ruevbappns = self.xdaqappns%'evb::RU' if index>0 else self.xdaqappns%'evb::EVM'
			fedSourceIds = ru_app.find(QN(ruevbappns, 'properties').text+'/'+QN(ruevbappns, 'fedSourceIds').text)
			fedSourceIds.attrib[QN(self.soapencns, 'arrayType').text] = "xsd:ur-type[%d]"%(self.nferols*self.streams_per_ferol/self.nrus)
			item_element = fedSourceIds.find(QN(ruevbappns,'item').text)
			fedSourceIds.remove(item_element)
			for n,fed in enumerate(feds_to_add):
				item_to_add = deepcopy(item_element)
				item_to_add.attrib[QN(self.soapencns, 'position').text] = '[%d]'%n
				item_to_add.text = str(fed)
				fedSourceIds.append(item_to_add)

		## Set instance and url
		for app in ru_context.findall(QN(self.xdaqns, 'Endpoint').text):
			if 'RU%d' in app.attrib['hostname']:
				app.set('hostname', app.get('hostname')%index)
			if 'RU%d' in app.attrib['port']:
				app.set('port', app.get('port')%index)
		ru_context.set('url', ru_context.get('url')%(index, index))

		return ru_context
	def addRUs(self, nrus):
		for n in xrange(nrus):
			self.config.append(self.makeRU(n))
	def makeEVM(self):
		index = 0
		fragmentname = 'EVM/EVM_context.xml'
		evm_element = elementFromFile(self.fragmentdir+fragmentname)

		## Add policy
		addFragmentFromFile(target=evm_element, filename=self.fragmentdir+'/EVM/EVM_policy_%s.xml'%(self.ptprot), index=0)
		## Add builder network endpoint
		evm_element.insert(3,Element(QN(self.xdaqns, 'Endpoint').text, {'protocol':'%s'%self.ptprot , 'service':"i2o", "hostname":"EVM%d_I2O_HOST_NAME"%(index), "port":"EVM%d_I2O_PORT"%(index), "network":"infini"}))
		## Add builder network pt application
		addFragmentFromFile(target=evm_element, filename=self.fragmentdir+'/EVM/EVM_%s_application.xml'%(self.ptprot), index=4) ## add after the two endpoints
		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		evm_element.insert(5,module)

		## Set instance and url
		for app in evm_element.findall(QN(self.xdaqns, 'Application').text):
			if app.attrib['class'] != "%s::EVM"%self.evbns: continue
			app.set('instance', str(index))
			break

		evm_element.set('url', evm_element.get('url')%(index, index))

		return evm_element
	def addEVM(self):
		self.config.append(self.makeEVM())

	def makeBU(self, index):
		fragmentname = 'BU/BU_context.xml'
		bu_context = elementFromFile(self.fragmentdir+fragmentname)

		## Add policy
		addFragmentFromFile(target=bu_context, filename=self.fragmentdir+'/BU/%s/BU_policy_%s.xml'%(self.evbns,self.ptprot), index=0)
		## Add builder network endpoint
		bu_context.insert(3,Element(QN(self.xdaqns, 'Endpoint').text, {'protocol':'%s'%self.ptprot , 'service':"i2o", "hostname":"BU%d_I2O_HOST_NAME"%(index), "port":"BU%d_I2O_PORT"%(index), "network":"infini"}))
		## Add builder network pt application
		addFragmentFromFile(target=bu_context, filename=self.fragmentdir+'/BU/BU_%s_application.xml'%(self.ptprot), index=4) ## add after the two endpoints
		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		bu_context.insert(5,module)

		## BU application
		bu_app = elementFromFile(filename=self.fragmentdir+'/BU/%s/BU_application.xml'%self.evbns)
		bu_context.insert(7,bu_app)
		bu_app.set('instance',str(index))

		## Set instance and url
		for app in bu_context.findall(QN(self.xdaqns, 'Application').text):
			if app.attrib['class'] != "%s::BU"%self.evbns: continue
			app.set('instance', str(index))
			break
		bu_context.set('url', bu_context.get('url')%(index, index))

		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libevb.so" if self.evbns == 'evb' else "$XDAQ_ROOT/lib/libgevb2g.so"
		bu_context.insert(8,module)

		return bu_context
	def addBUs(self, nbus):
		for n in xrange(nbus):
			self.config.append(self.makeBU(n))

	def writeConfig(self, destination):
		with open(destination, 'w') as file:
			file.write(ElementTree.tostring(self.config))
			file.close()
		subprocess.call(['xmllint', '--format', '--nsclean', destination, '-o', destination]) ## pass through xmllint for formatting
		with open(destination, 'r') as oldfile:
			lines = oldfile.readlines()
			lines.remove('<?xml version="1.0"?>\n')
			with open(destination+'temp', 'w') as newfile:
				for line in lines:
					newfile.write(line)
		subprocess.call(['mv', '-f', destination+'temp', destination])

	def makeConfig(self, nferols=8, streams_per_ferol=2, nrus=1, nbus=2, destination='configuration.template.xml'):
		self.nrus              = nrus
		self.nbus              = nbus
		self.nferols           = nferols
		self.streams_per_ferol = streams_per_ferol

		self.makeFEDConfiguration()

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
		self.addFerolControllers(nferols=nferols, streams_per_ferol=streams_per_ferol)
		self.addRUs(nrus=nrus)
		if self.evbns == 'gevb2g': self.addEVM()
		self.addBUs(nbus=nbus)

		self.writeConfig(destination)
		if self.verbose>0: print 70*'-'


