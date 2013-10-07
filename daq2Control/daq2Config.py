import subprocess
import re, os, shlex
import time
from sys import stdout
import xml.etree.ElementTree as ET

from daq2Utils import printError, printWarningWithWait, sleep, SIZE_LIMIT_TABLE, checkMaxSize

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

######################################################################
from daq2SymbolMap import daq2SymbolMap
class daq2Config(object):
	'''
---------------------------------------------------------------------
  class daq2Config

 - Reads a template xdaq config.xml file and returns an object that will know the
   setup of the system.
 - Checks the config for EvB vs gevb2g cases, for GTPe, etc.
 - Additional checks on the config file, such as enableStream0/1,
   Event_Length_Max_bytes_FED0/1, etc.
---------------------------------------------------------------------
'''
	def __init__(self, configFile):
		self.verbose = 1
		self.file = configFile
		self.hosts     = [] ## a list of the hosts defined in the xml config
		self.FEROLs    = []
		self.eFEROLs   = []
		self.nStreams  = 0  ## total number of streams
		self.RUs       = []
		self.BUs       = []
		self.EVM       = []
		self.GTPe      = []
		self.FMM       = []
		self._hostTypes = {'FEROLCONTROLLER' : self.FEROLs,
		                   'FEROL'           : self.eFEROLs,
		                   'RU'              : self.RUs,
		                   'BU'              : self.BUs,
		                   'EVM'             : self.EVM,
		                   'GTPE'            : self.GTPe,
		                   'FMM'             : self.FMM}

		self.readXDAQConfigTemplate(configFile)
		self.useGTPe = False
		if len(self.GTPe) > 0:
			self.useGTPe = True

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

	def printHosts(self):
		separator = 70*'-'
		print separator
		## Count enabled FEROL streams:
		streams = 0
		for host in self.FEROLs:
			if host.enableStream0: streams += 1
			if host.enableStream1: streams += 1

		if len(self.FEROLs) > 0: config = '%ds%dfx%dx%d' % (streams, len(self.FEROLs), len(self.RUs), len(self.BUs))
		else              : config = '%dx%dx%d'     % (len(self.eFEROLs), len(self.RUs), len(self.BUs))
		print config, 'configuration with', 'EvB' if self.useEvB else 'gevb2g'
		print separator
		for host in self.hosts:
			print '%-20s at %25s:%-5d (SOAP) :%-5d (LAUNCHER)' % (host.name, host.host, host.port, host.lport)
		print separator

	def readXDAQConfigTemplate(self, configFile):
		if not os.path.exists(configFile):
			raise IOError('File '+configFile+' not found')
		self.testCase      = os.path.dirname(configFile[configFile.find('cases/')+6:])
		self.testCaseShort = os.path.dirname(configFile).split('/')[-1]
		config = ET.parse(configFile)
		partition = config.getroot()

		## Check <i2o:protocol> element for evb: or gevb2g: tags to determine which of the two we're dealing with here:
		i2o_namespace = 'http://xdaq.web.cern.ch/xdaq/xsd/2004/I2OConfiguration-30'
		i2o_protocol = partition.find("{%s}protocol" % i2o_namespace)
		if 'gevb2g::' in i2o_protocol[0].attrib['class']: ## there is something with a gevb2g tag
			if self.verbose > 2 : print "Found a gevb2g configuration"
			self.useEvB = False
			self.namespace = 'gevb2g::'
		elif 'evb::' in i2o_protocol[0].attrib['class']: ## there is something with a evb tag
			if self.verbose > 2 : print "Found an EvB configuration"
			self.useEvB = True
			self.namespace = 'evb::'
		else:
			raise RuntimeError("Couldn't determine EvB/gevb2g case!")

		maxsizes = []
		tcp_cwnd = []
		## Scan <xc:Context>'s to extract configuration
		for context in partition:
			if not context.tag.endswith('Context'): continue

			url = context.attrib['url']
			pattern = re.compile(r'http://([A-Z_0-9]*?)([0-9]+)_SOAP_HOST_NAME:.*')
			h,n = pattern.match(url).group(1), pattern.match(url).group(2)
			try:
				if self.verbose > 2: print 'Adding', h+n
				ho = host(h+n, int(n), h)

				## For FEROLs, check which of the streams are enabled
				if h == 'FEROLCONTROLLER':
					for app in context.findall("./{http://xdaq.web.cern.ch/xdaq/xsd/2004/XMLConfiguration-30}Application"):
						if app.attrib['class'] == 'ferol::FerolController':
							frlns = '{urn:xdaq-application:ferol::FerolController}'
							prop = app.find(frlns + 'properties')
							ho.__class__ = FEROL ## Make it a FEROL
							ho.setStreams(prop.find(frlns + 'enableStream0').text, prop.find(frlns + 'enableStream1').text)
							if ho.enableStream0:
								self.nStreams += 1
								maxsizes.append(int(prop.find(frlns + 'Event_Length_Max_bytes_FED0').text))
								tcp_cwnd.append(int(prop.find(frlns + 'TCP_CWND_FED0').text))
							if ho.enableStream1:
								self.nStreams += 1
								maxsizes.append(int(prop.find(frlns + 'Event_Length_Max_bytes_FED1').text))
								tcp_cwnd.append(int(prop.find(frlns + 'TCP_CWND_FED1').text))
							break

				if h == 'FEROL': ## Misnomer, eFEROLs are called FEROLS
					self.nStreams += 1

				self._hostTypes[h].append(ho)
				self.hosts.append(ho)

			except KeyError as e:
				printError('Unknown host type %s. Aborting.' % h, self)
				raise e

		if len(maxsizes) > 0:
			## Check whether they were all filled
			if len(maxsizes) != self.nStreams:
				raise RuntimeError("Didn't find all Event_Length_Max_bytes parameter in config file?!")

			## Check they are all the same:
			size_set = set()
			for x in maxsizes: size_set.add(x)
			if len(size_set) > 1:
				message = """
WARNING: You have FEROLs with different
         Event_Length_Max_bytes parameters in your config file!

 That probably shouldn't be.
"""
				printWarningWithWait(message, instance=self)

			## Check they are correct and alert
			if not checkMaxSize(maxsizes[0], self.nStreams//len(self.RUs)):
			# if maxsizes[0] != SIZE_LIMIT_TABLE[self.nStreams//len(self.RUs)][0]:
				message = """
WARNING: Event_Length_Max_bytes for FEROLs seems to be set
         to the wrong value in your config .xml file!

 Is set to: %d in config. Expected value: %d
""" % (int(maxsizes[0]), int(SIZE_LIMIT_TABLE[self.nStreams//len(self.RUs)][0]))
				printWarningWithWait(message, instance=self)

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

			## Check they are correct and alert
			message = """
WARNING: TCP_CWND_FEDX for FEROLs seems to be set
         to the wrong value in your config .xml file!

 Is set to: %d in config. Expected value: %d
"""
			if nStreams == len(self.FEROLs) and str(35000) in cwnd_set:
				printWarningWithWait(message%(35000, 55000), instance=self)
			if nStreams == 2*len(self.FEROLs) and str(55000) in cwnd_set:
				printWarningWithWait(message%(55000, 35000), instance=self)

