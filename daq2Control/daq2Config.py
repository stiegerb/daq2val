import subprocess
import re, os, shlex
import time
from sys import stdout
from copy import deepcopy
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import QName as QN

from daq2Utils import printError, printWarningWithWait, sleep, SIZE_LIMIT_TABLE, checkMaxSize

from daq2Configurator import propertyInApp

separator = 70*'-'


######################################################################
class host(object):
	"""Baseclass for a SOAP host"""
	def __init__(self,name,index,hosttype,soaphost='undefined',soapport=-99):
		self.name  = name
		self.index = index
		self.host  = soaphost
		self.port  = soapport
		self.type  = hosttype
		self.lport = 0 # launcher port
		self.applications = [] ## should be filled with ('classname', instance) tuples
	def __str__(self):
		return '%-20s%3d at %25s:%-5d with launcher at %-5d' % (self.type, self.index, self.host, self.port, self.lport)

######################################################################
class FEROL(host):
	"""Holds additional information on FEROL configuration"""
	def __init__(self,name,index,soaphost,soapport,hosttype, enableStream0=True, enableStream1=False):
		super(FEROL, self).__init__()
		self.enableStream0 = enableStream0
		self.enableStream1 = enableStream1
	def cfgStringToBool(self, string):
		return string in ('true', 'True', '1')
	def setStreams(self, enableStream0, enableStream1):
		self.enableStream0 = self.cfgStringToBool(enableStream0)
		self.enableStream1 = self.cfgStringToBool(enableStream1)
	def setFEDIDs(self, fedid1, fedid2):
		self.fedID1 = fedid1
		self.fedID2 = fedid2

######################################################################
class eFED(host):
	"""Holds additional information on eFED configuration"""
	def __init__(self,name,index,soaphost='undefined',soapport=-99):
		super(FEROL, self).__init__()
		streams = []
	def addStream(self, instance, fedid=900, slot=-1):
		if not hasattr(self, 'streams'): ## want to morph hosts into eFEDs, i.e. constructor might not have been called
			self.streams = []
		self.streams.append((instance, fedid, slot))
	def __len__(self):
		return len(streams)
	def __str__(self):
		text  = '%-20s%3d at %25s:%-5d with launcher at %-5d\n' % (self.type, self.index, self.host, self.port, self.lport)
		for n,(instance,fedid,slot) in enumerate(self.streams):
			text += '  stream %d at instance %2d, fedid %d, slot %d\n' % (n, instance, fedid, slot)
		return text

######################################################################
class FMM(host):
	"""Holds additional information on FMM configuration"""
	def __init__(self,name,index,soaphost='undefined',soapport=-99):
		super(FEROL, self).__init__()
		streams = []
	def addSlot(self, geoslot=0, label='', inputs='', outputs=''):
		if not hasattr(self, 'slots'): ## want to morph hosts into FMMs, i.e. constructor might not have been called
			self.slots = []
		self.slots.append((geoslot, label, inputs, outputs))
	def __len__(self):
		return len(streams)
	def __str__(self):
		text  = '%-20s%3d at %25s:%-5d with launcher at %-5d\n' % (self.type, self.index, self.host, self.port, self.lport)
		for n,(geoslot, label, inputs, outputs) in enumerate(self.slots):
			text += '  geoslot %d (%-15s) inputLabels: %-82s outputLabels: %-20s\n' % (geoslot, label, inputs, outputs)
		return text

######################################################################
from daq2SymbolMap import daq2SymbolMap
class daq2Config(object):
	'''
---------------------------------------------------------------------
  class daq2Config

 - Reads a template xdaq config.xml file and returns an object that will know the
   setup of the system.
 - Checks the config for EvB vs gevb2g cases, for GTPe, IBV/UDAPL, etc.
 - Additional checks on the config file, such as enableStream0/1,
   Event_Length_Max_bytes_FED0/1, etc.
---------------------------------------------------------------------
'''
	def __init__(self, configFile, verbose=1):
		self.verbose = verbose
		self.configfile = configFile
		self.hosts      = [] ## a list of the hosts defined in the xml config
		self.FEROLs     = []
		self.eFEROLs    = []
		self.nStreams   = 0  ## total number of streams
		self.RUs        = []
		self.BUs        = []
		self.EVM        = []
		self.eFEDs      = []
		self.GTPe       = []
		self.FMM        = []
		self._hostTypes = {'FEROLCONTROLLER' : self.FEROLs,
		                   'FEROL'           : self.eFEROLs,
		                   'RU'              : self.RUs,
		                   'BU'              : self.BUs,
		                   'EVM'             : self.EVM,
		                   'EFED'            : self.eFEDs,
		                   'GTPE'            : self.GTPe,
		                   'FMM'             : self.FMM}

		self.config   = ET.parse(configFile)
		self.ETroot   = self.config.getroot()

		self.xcns     = re.match(r'\{(.*?)\}Partition', self.ETroot.tag).group(1) ## Extract xdaq namespace
		self.ferolns  = "urn:xdaq-application:ferol::FerolController"

		self.contexts = self.ETroot.getiterator(str(QN(self.xcns,'Context')))

		self.dropAtRU = False
		self.useMSIO = False
		self.useInputEmulator = False
		self.readXDAQConfigTemplate(configFile)
		self.useGTPe = False
		if len(self.GTPe) > 0:
			self.useGTPe = True

		self.setTestCase()
		if self.verbose>1: self.printHosts()

	def setTestCase(self):
		if len(self.FEROLs) > 0:
			config = '%ds%dfx%dx%d' % (self.nStreams, len(self.FEROLs),
				                       len(self.RUs), len(self.BUs))
		elif self.useMSIO or self.useInputEmulator:
			config = '%dx%d' % (len(self.RUs), len(self.BUs))
		else:
			config = '%dx%dx%d' % (len(self.eFEROLs), len(self.RUs),
				                   len(self.BUs))
		self.testCase = config


	def fillFromSymbolMap(self, symbolMap):
		"""Adds the hostname and ports from a symbol map for each host"""
		for host in self.hosts:
			try:
				host.host  = symbolMap(host.name+'_SOAP_HOST_NAME')
				host.port  = symbolMap(host.name+'_SOAP_PORT')
				host.lport = symbolMap(host.name+'_LAUNCHER_PORT')
			except KeyError as e:
				printError("Didn't find host %s in symbol map." % host.name, self)
				raise e

	def printHosts(self, out=None, prepend=''):
		if out==None: out = stdout
		separator = 70*'-'
		out.write(prepend+separator+'\n')
		builder = 'EvB' if self.useEvB else 'gevb2g'
		if self.useMSIO: builder = 'mstreamio'
		ptprotocol = 'IBV' if self.useIBV else 'UDAPL'
		out.write('%s%s configuration with %s/%s\n' % (prepend, self.testCase, builder,ptprotocol))
		out.write(prepend+separator+'\n')
		for host in self.hosts:
			out.write(prepend+'%-20s at %25s:%-5d (SOAP) :%-5d (LAUNCHER), Applications:' % (host.name, host.host, host.port, host.lport))
			for app,inst in host.applications:
				if inst is not None: out.write(' %s(%d)' % (app, inst))
				else:                out.write(' %s' % app)
			out.write('\n')

			if host.__class__ == eFED:
				for n,(instance,fedid,slot) in enumerate(host.streams):
					out.write(prepend+'  stream %d at instance %2d, fedid %d, slot %d\n' % (n, instance, fedid, slot))
			if host.__class__ == FMM:
				for n,(geoslot, label, inputs, outputs) in enumerate(host.slots):
					out.write(prepend+'  geoslot %d (%-15s) inputLabels: %-82s outputLabels: %-20s\n' % (geoslot, label, inputs, outputs))
		out.write(prepend+separator+'\n')

	def setFerolParameter(self, param_name, param_value):
		self.setProperty(['FEROLCONTROLLER'], 'ferol::FerolController', param_name, param_value)

	def printFerolParameter(self, param_name):
		for context in self.contexts:
			if not 'FEROLCONTROLLER' in context.attrib['url']: continue
			param = context.find(QN(self.xcns,'Application').text+'/'+QN(self.ferolns,'properties').text+'/'+QN(self.ferolns,param_name).text)
			try:
				print context.attrib['url'], param_name, param.text
			except AttributeError:
				raise KeyError('Ferol parameter '+param_name+' not found')

	def setRUIBVParameter(self, param_name, param_value):
		self.setProperty(['RU','EVM'], 'pt::ibv::Application', param_name, param_value)

	def fillRUInstances(self, maskRUs=""):
		maskRU_lst = [r.strip('.cms') for r in maskRUs.split(',')]

		rus_to_add = [r.index for r in self.RUs if not r.index==0 and
		                         not r.host.strip('.cms') in maskRU_lst]
		rus_to_add = [(n,r) for n,r in enumerate(rus_to_add)]

		soapencns = "http://schemas.xmlsoap.org/soap/encoding/"
		appns = 'urn:xdaq-application:evb::EVM'

		# Make the ruInstances element
		ruInstances = Element(QN(appns, 'ruInstances').text)
		ruInstances.attrib[QN(soapencns, 'arrayType').text] = (
			                    "xsd:ur-type[%d]"%(len(rus_to_add)))
		ruInstances.attrib[QN('xsi', 'type').text] = QN(soapencns, "Array").text

		# Make an empty item element
		item_element = Element('item')
		item_element.attrib[QN('xsi','type').text] = "xsd:unsignedInt"

		# Fill the item elements and add them to ruInstances
		for pos,index in rus_to_add:
			item_to_add = deepcopy(item_element)
			item_to_add.attrib[QN(soapencns, 'position').text] = "[%d]"%pos
			item_to_add.text = str(index)
			ruInstances.append(item_to_add)

		# Remove the old ruInstances element and add the new one
		for context in self.contexts:
			(host,number) = self.urlToHostAndNumber(context.attrib['url'])
			if not host == 'RU': continue
			for app in context.findall(QN(self.xcns, 'Application').text):
				if not app.attrib['class'] == 'evb::EVM': continue ## find correct application
				try:
					prop = app[0] ## Assume here that there is only one element, which is the properties
					if 'properties' in prop.tag:
						oldInstances = app.find(QN(appns,'properties').text+'/'+
							                    QN(appns,'ruInstances').text)
						prop.remove(oldInstances)
						prop.append(ruInstances)
				except IndexError: ## i.e. app[0] didn't work
					pass
		return

	def getProperty(self, application, prop_name):
		pass

	def setProperty(self, context_list, classname, prop_name, prop_value, instance=None):
		for context in self.contexts:
			(host,number) = self.urlToHostAndNumber(context.attrib['url'])
			if not host in context_list: continue
			if instance is not None and instance != int(number): continue
			for app in context.findall(QN(self.xcns, 'Application').text):
				if not app.attrib['class'] == classname: continue ## find correct application
				try:
					prop = app[0] ## Assume here that there is only one element, which is the properties
					if not 'properties' in prop.tag:
						raise RuntimeError('Could not identify properties of %s application in %s context.'%(app.attrib['class'], context.attrib['url']))
					appns = re.match(r'\{(.*?)\}properties', prop.tag).group(1) ## Extract namespace
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


	def urlToHostAndNumber(self, url):
		"""
		Converts context url strings like
		'http://RU0_SOAP_HOST_NAME:RU0_SOAP_PORT'
		to a pair of strings of hosttype and index. I.e. 'RU' and '0' in this case.
		"""
		pattern = re.compile(r'http://([A-Z_0-9]*?)([0-9]+)_SOAP_HOST_NAME:.*')
		h,n = pattern.match(url).group(1), pattern.match(url).group(2) ## so h will be RU/BU/EVM/FEROLCONTROLLER/..., n will be 0,1,2,3,...
		return h,n

	def readXDAQConfigTemplate(self, configFile):
		if not os.path.exists(configFile):
			raise IOError('File '+configFile+' not found')

		## Check <i2o:protocol> element for evb: or gevb2g: tags to determine which of the two we're dealing with here:
		i2o_namespace = 'http://xdaq.web.cern.ch/xdaq/xsd/2004/I2OConfiguration-30'
		i2o_protocol = self.ETroot.find(QN(i2o_namespace, 'protocol').text)
		try:
			if 'gevb2g::' in i2o_protocol[0].attrib['class']: ## there is something with a gevb2g tag
				if self.verbose > 2 : print "Found a gevb2g configuration"
				self.useEvB = False
				self.useMSIO = False
				self.namespace = 'gevb2g::'
			elif 'evb::' in i2o_protocol[0].attrib['class']: ## there is something with a evb tag
				if self.verbose > 2 : print "Found an EvB configuration"
				self.useEvB = True
				self.useMSIO = False
				self.namespace = 'evb::'
			elif ('Client' in i2o_protocol[0].attrib['class'] or
			      'Server' in i20_protocol[0].attrib['class']):
				if self.verbose > 2 : print "Found an mstreamio configuration"
				self.useEvB = False
				self.useMSIO = True
				self.namespace = 'gevb2g::'
			else:
				raise RuntimeError("Couldn't determine EvB/gevb2g case!")
		except TypeError,e:
			if i2o_protocol == None:
				if self.verbose > 2: print ("Warning: Did not find i2o protocol"
					                        " to determine namespace, setting "
					                        "to 'evb' and useEvB to True")
				self.namespace = 'evb::'
				self.useEvB = True
				self.useMSIO = False
			else:
				raise e

		maxsizes = []
		tcp_cwnd = []
		checked_ibv = False
		checked_evbie = False

		#### Scan <xc:Context>'s to extract configuration
		for context in self.contexts:
			apps = context.findall(QN(self.xcns, 'Application').text) ## all 'Application's of this context
			## Match context url
			h,n = self.urlToHostAndNumber(context.attrib['url'])
			try:
				if self.verbose > 2: print 'Adding', h+n
				ho = host(h+n, int(n), h)

				## Save a list of all applications and instances running in each context
				for app in apps:
					try:
						classname,instance = (str(app.attrib['class']), int(app.attrib['instance']))
					except KeyError:
						classname,instance = (str(app.attrib['class']), None)
					ho.applications.append((classname, instance))

				## For RU, check whether IVB or UDAPL (only do it once)
				## and whether there is an InputEmulator
				if h == 'RU' and not checked_ibv:
					self.useIBV = False
					for app in apps:
						if app.attrib['class'] == 'pt::ibv::Application':
							self.useIBV = True  ## Found IBV configuration
							if self.verbose > 2 : print "Found IBV peer transport protocol"
							break
						if app.attrib['class'] == 'pt::udapl::Application':
							self.useIBV = False ## Found UDAPL configuration
							if self.verbose > 2 : print "Found UDAPL peer transport protocol"
							break
					for app in apps:
						if app.attrib['class'] == 'gevb2g::InputEmulator':
							self.useInputEmulator = True
							if self.verbose > 2 : print "Found gevb2g InputEmulator"
							break
					checked_ibv = True

				## For evb RU (or EVM), check whether inputSource is set to Local
				if h == 'RU' and self.useEvB and not checked_evbie:
					for app in apps:
						if app.attrib['class'] == 'evb::EVM':
							try:
								if propertyInApp(app, 'inputSource') == 'Local':
									self.useInputEmulator = True
									if self.verbose > 2 : print "Found evb InputEmulator"
								if propertyInApp(app, 'dropInputData') == 'true':
									self.dropAtRU = True
								else:
									self.dropAtRU = False
							except RuntimeError: ## Didn't find properties
								pass

							break
					checked_evbie = True

				## For FEROLs, check which of the streams are enabled
				if h == 'FEROLCONTROLLER':
					for app in apps:
						if app.attrib['class'] == 'ferol::FerolController':
							prop = app.find(QN(self.ferolns,'properties').text)
							ho.__class__ = FEROL ## Make it a FEROL
							ho.setStreams(prop.find(QN(self.ferolns, 'enableStream0').text).text, prop.find(QN(self.ferolns, 'enableStream1').text).text)
							if ho.enableStream0:
								self.nStreams += 1
								maxsizes.append(int(prop.find(QN(self.ferolns, 'Event_Length_Max_bytes_FED0').text).text))
								tcp_cwnd.append(int(prop.find(QN(self.ferolns, 'TCP_CWND_FED0').text).text))
							if ho.enableStream1:
								self.nStreams += 1
								maxsizes.append(int(prop.find(QN(self.ferolns, 'Event_Length_Max_bytes_FED1').text).text))
								tcp_cwnd.append(int(prop.find(QN(self.ferolns, 'TCP_CWND_FED1').text).text))
							try:
								ho.setFEDIDs(int(prop.find(QN(self.ferolns, 'expectedFedId_0').text).text),
									         int(prop.find(QN(self.ferolns, 'expectedFedId_1').text).text))
							except Exception, e:
								printError("Failed to read FEDIDs for %s%s"%(h,n), self)
								raise e
							break

				## For eFEDs, count the number of enabled streams and their instances
				if h == 'EFED':
					ho.__class__ = eFED ## Make it an eFED
					for app in apps:
						if app.attrib['class'] == 'd2s::FEDEmulator':
							efedns = 'urn:xdaq-application:d2s::FEDEmulator'
							prop = app.find(QN(efedns,'properties').text)
							fedid    = int(prop.find(QN(efedns,'FedSourceId').text).text)
							slot     = int(prop.find(QN(efedns,'slot').text).text)
							instance = int(app.attrib['instance'])
							ho.addStream(instance, fedid, slot)

				## For FMM, check the different geoslots and input/output labels
				if h == 'FMM':
					ho.__class__ = FMM ## Make it an FMM
					for app in apps:
						if app.attrib['class'] == 'tts::FMMController':
							fmmns = 'urn:xdaq-application:tts::FMMController'
							prop = app.find(QN(fmmns,'properties').text)
							fmmconfig = prop.find(QN(fmmns,'config').text)
							for item in fmmconfig.findall(QN(fmmns,"item").text):
								geoslot = int(item.find(QN(fmmns,'geoslot').text).text)
								label   = str(item.find(QN(fmmns,'label').text).text)
								inputs  = str(item.find(QN(fmmns,'inputLabels').text).text)
								outputs = str(item.find(QN(fmmns,'outputLabels').text).text)
								ho.addSlot(geoslot, label, inputs, outputs)

				if h == 'FEROL': ## Misnomer, eFEROLs are called FEROLS
					self.nStreams += 1

				self._hostTypes[h].append(ho)
				self.hosts.append(ho)

			except KeyError as e:
				printError('Unknown host type %s. Aborting.' % h, self)
				raise e

		if self.verbose < 1: return
		if len(maxsizes) > 0:
			## Check whether they were all filled
			if len(maxsizes) != self.nStreams:
				raise RuntimeError("Didn't find all Event_Length_Max_bytes parameter in config file?!")

			## Check they are all the same:
			size_set = set(maxsizes)
			if len(size_set) > 1:
				message = """
WARNING: You have FEROLs with different
         Event_Length_Max_bytes parameters in your config file!

 That probably shouldn't be.
"""
				printWarningWithWait(message, instance=self)

# 			## Check they are correct and alert
# 			if not checkMaxSize(maxsizes[0], self.nStreams//len(self.RUs)):
# 			# if maxsizes[0] != SIZE_LIMIT_TABLE[self.nStreams//len(self.RUs)][0]:
# 				message = """
# WARNING: Event_Length_Max_bytes for FEROLs seems to be set
#          to the wrong value in your config .xml file!

#  Is set to: %d in config. Expected value: %d
# """ % (int(maxsizes[0]), int(SIZE_LIMIT_TABLE[self.nStreams//len(self.RUs)][0]))
# 				printWarningWithWait(message, instance=self)

		if len(tcp_cwnd) > 0:
			## Check whether they were all filled
			if len(tcp_cwnd) != self.nStreams:
				raise RuntimeError("Didn't find all TCP_CWND_FEDX parameters in config file?!")

			## Check they are all the same:
			cwnd_set = set()
			for x in tcp_cwnd: cwnd_set.add(x)
			if len(cwnd_set) > 1:
				message = """
WARNING: You have FEROLs with different
         TCP_CWND_FEDX parameters in your config file!

 That probably shouldn't be.
"""
				printWarningWithWait(message, instance=self)


			## Check they are correct and alert in case:
			message = """
WARNING: TCP_CWND_FEDX for FEROLs seems to be set
         to the wrong value in your config .xml file!

 Is set to: %d in config. Expected value: %d
"""
			cwnd = cwnd_set.pop()
			if self.nStreams == len(self.FEROLs) and cwnd not in [80000]:
				printWarningWithWait(message%(cwnd, 80000), instance=self, waittime=2)
			if self.nStreams == 2*len(self.FEROLs) and cwnd not in [80000]:
				printWarningWithWait(message%(cwnd, 80000), instance=self, waittime=2)


	def writeConfig(self, destination):
		self.config.write(destination)
