#! /usr/bin/env python
######################################################################
#  For now we assume that we either run with FEROLs or eFEROLs,      #
#  never with both!                                                  #
#                                                                    #
#  ToDo-List:                                                        #
#   - Fix order of stopping xdaqs to prevent log spamming            #
#   - Output naming for --runScan? Why no _RMS_X.X behind name?      #
#   - Automatize the number of samples, depending on duration        #
#   - Add option to use dummyFerol                                   #
#   - Testing testing testing                                        #
######################################################################

import subprocess
import re, os, shlex
import time
from sys import stdout
import xml.etree.ElementTree as ET

separator = 70*'-'

SIZE_LIMIT_TABLE = {
     # max size, scan until
	 4 : (32000, 16000),  # merging by  4
	 8 : (32000, 16000),  # merging by  8
	12 : (21000, 10240),  # merging by 12
	16 : (16000,  8192),  # merging by 16
	24 : (10500,  5120)   # merging by 24
}


######################################################################
class host(object):
	"""Baseclass for a SOAP host"""
	def __init__(self,name,index,soaphost,soapport,hosttype):
		self.name  = name
		self.index = index
		self.host  = soaphost
		self.port  = soapport
		self.type  = hosttype
		self.lport = 0 # launcher port
	def __str__(self):
		return '%-20s%3d at %25s:%-5d with launcher at %-5d' % (self.type, self.index, self.host, self.port, self.lport)

class FEROL(host):
	"""Holds additional information on FEROL configuration"""
	def __init__(self, name,index,soaphost,soapport,hosttype, enableStream0=True, enableStream1=False):
		super(FEROL, self).__init__()
		self.enableStream0 = enableStream0
		self.enableStream1 = enableStream1
	def cfgStringToBool(self, string):
		return string in ('true', 'True', '1')
	def setStreams(self, enableStream0, enableStream1):
		self.enableStream0 = self.cfgStringToBool(enableStream0)
		self.enableStream1 = self.cfgStringToBool(enableStream1)

######################################################################
class daq2Control(object):
	"""docstring for daq2Control"""
	def __init__(self, options):
		try:
			self._symbolMapFile = os.environ['TESTS_SYMBOL_MAP']
			self._testDir       = os.environ['RUB_TESTER_HOME']
			self._outputDir     = self._testDir + '/data/'
			self._platform      = os.environ['XDAQ_PLATFORM']
			self._runDir        = self._testDir + '/' + self._platform + '/'
			self._user          = os.environ['USER']
			self._testType      = os.environ['TEST_TYPE']
		except KeyError as e:
			print 30*'#'
			print 'Environment missing, did you forget to source setenv-COL.sh? Aborting.'
			print 30*'#'
			raise e

		if len(options.symbolMap)>0:
			self._symbolMapFile = symbolMap

		self._dryRun    = options.dry ## if true, only print commands without doing anything
		self._symbolMap = {} ## a dictionary of all symbols in the map

		self.verbose      = options.verbose
		self.useLogNormal = options.useLogNormal
		self.stopRestart  = options.stopRestart

		self._hosts     = [] ## a list of the hosts defined in the xml config
		self._allHosts  = [] ## a list of all soap hosts defined in the symbol map
		self._FEROLs    = []
		self._eFEROLs   = []
		self._nStreams  = 0  ## total number of streams
		self._RUs       = []
		self._BUs       = []
		self._EVM       = []
		self._hostTypes = {'FEROLCONTROLLER' : self._FEROLs,
		                   'FEROL'           : self._eFEROLs,
		                   'RU'              : self._RUs,
		                   'BU'              : self._BUs,
		                   'EVM'             : self._EVM}

		self._testEnv   = ""
		if len(self._testType) > 0: self._testEnv = "-"+self._testType
		self.fillSymbolMap()

		self._SOAPEnvelope = '''<SOAP-ENV:Envelope
   SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"
   xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
   xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/">
      <SOAP-ENV:Header>
      </SOAP-ENV:Header>
      <SOAP-ENV:Body>
         %s
      </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
'''

	## Core
	def fillSymbolMap(self):
		with open(self._symbolMapFile, 'r') as file:
		    for line in file:
				if line.startswith('#') or len(line.strip())==0: continue
				key,value = line.split()
				self._symbolMap[key] = value

				match = re.match(r'([A-Z_0-9]*?[A-Z]*)([0-9]+)_SOAP_HOST_NAME$',key)
				## matches a NAME23_SOAP_HOST_NAME structure for the 'NAME' and '23'
				if match:
					hosttype, index = (match.group(1), match.group(2))
					name = hosttype+index
					soaphost = value
					# print hosttype, index, name, key, soaphost
					ho = host(name, int(index), soaphost, 0, hosttype)
					self._allHosts.append(ho)

		try:
			soap_base_port     = int(self._symbolMap['SOAP_BASE_PORT'])
			frl_base_port      = int(self._symbolMap['FRL_BASE_PORT'])
			launcher_base_port = int(self._symbolMap['LAUNCHER_BASE_PORT'])
			i2o_base_port      = int(self._symbolMap['I2O_BASE_PORT'])

			for n,h in enumerate(self._allHosts):
				self._symbolMap[h.name+'_SOAP_PORT']     = soap_base_port     + n
				self._symbolMap[h.name+'_FRL_PORT']      = frl_base_port      + n
				self._symbolMap[h.name+'_LAUNCHER_PORT'] = launcher_base_port + n
				self._symbolMap[h.name+'_I2O_PORT']      = i2o_base_port      + n
				self._allHosts[n].port  = int(soap_base_port + n)
				self._allHosts[n].lport = int(launcher_base_port + n)
		except KeyError as e:
			print 30*'#'
			print 'Not all base ports defined (SOAP, FRL, LAUNCHER, I2O), check your symbolmap! Aborting.'
			print 30*'#'
			raise e
	def printSymbolMap(self):
		print 20*'-'
		for key in sorted(self._symbolMap.keys()):
			print '%-35s%-35s' % (key, self._symbolMap[key])
	def printAllHosts(self):
		print 20*'-'
		for host in self._allHosts:
			print host
	def printHosts(self):
		print separator
		## Count enabled FEROL streams:
		streams = 0
		for host in self._FEROLs:
			if host.enableStream0: streams += 1
			if host.enableStream1: streams += 1

		config = '%ds%dfx%dx%d' % (streams, len(self._FEROLs), len(self._RUs), len(self._BUs))
		print 'Found a', config, 'config'
		if len(self._FEROLs)>0 : print 'FEROLs:'
		for host in self._FEROLs:
			print host
		if len(self._eFEROLs)>0 : print 'eFEROLs:'
		for host in self._eFEROLs:
			print host
		print 'RUs:'
		for host in self._RUs:
			print host
		print 'BUs:'
		for host in self._BUs:
			print host
		print 'EVM:'
		for host in self._EVM:
			print host

	def sleep(self,naptime=0.5):
		if self._dryRun:
			if self.verbose > 1: print 'sleep', naptime
			return

		barlength = len(separator)-1
		starttime = time.time()
		if self.verbose > 0 and naptime > 0.5:
			stdout.write(''+barlength*' '+'-')
			stdout.write('\r')
			stdout.flush()
		while(time.time() < starttime+naptime):
			time.sleep(naptime/float(barlength))
			if self.verbose > 0 and naptime > 0.5:
				stdout.write('-')
				stdout.flush()
		if self.verbose > 0 and naptime > 0.5:
			stdout.write('-')
			stdout.flush()
			stdout.write('\r' + (barlength+5)*' ')
			stdout.write('\r')
			stdout.flush()

		# if not self._dryRun: time.sleep(naptime)
		# if not self._dryRun: subprocess.call(['sleep', str(time)])
	def readXDAQConfigTemplate(self, configfile):
		if not os.path.exists(configfile):
			raise IOError('File '+configfile+' not found')
		self._testCase      = os.path.dirname(configfile[configfile.find('cases/')+6:])
		self._testCaseShort = os.path.dirname(configfile).split('/')[-1]
		self._runDir += self._testCaseShort
		config = ET.parse(configfile)
		partition = config.getroot()

		## Check <i2o:protocol> element for evb: or gevb2g: tags to determine which of the two we're dealing with here:
		i2o_namespace = 'http://xdaq.web.cern.ch/xdaq/xsd/2004/I2OConfiguration-30'
		i2o_protocol = partition.find("{%s}protocol" % i2o_namespace)
		if 'gevb2g::' in i2o_protocol[0].attrib['class']: ## there is something with a gevb2g tag
			if self.verbose > 0 : print "Found a gevb2g configuration"
			self.useEvB = False
			self.namespace = 'gevb2g::'
		elif 'evb::' in i2o_protocol[0].attrib['class']: ## there is something with a evb tag
			if self.verbose > 0 : print "Found an EvB configuration"
			self.useEvB = True
			self.namespace = 'evb::'
		else:
			raise RuntimeError("Couldn't determine EvB/gevb2g case!")


		maxsizes = []
		## Scan <xc:Context>'s to extract configuration
		for context in partition:
			if not context.tag.endswith('Context'): continue

			url = context.attrib['url']
			pattern = re.compile(r'http://([A-Z_0-9]*?)([0-9]+)_SOAP_HOST_NAME:.*')
			h,n = pattern.match(url).group(1), pattern.match(url).group(2)
			try:
				soap_host, soap_port = self._symbolMap[h+n+'_SOAP_HOST_NAME'], self._symbolMap[h+n+'_SOAP_PORT']
				try:
					if self.verbose > 0: print 'Adding', h+n, 'at', soap_host+':'+str(soap_port)
					ho = host(h+n, int(n), soap_host, int(soap_port), h)
					ho.lport = self._symbolMap[h+n+'_LAUNCHER_PORT']

					## For FEROLs, check which of the streams are enabled
					if h == 'FEROLCONTROLLER':
						for app in context.findall("./{http://xdaq.web.cern.ch/xdaq/xsd/2004/XMLConfiguration-30}Application"):
							if app.attrib['class'] == 'ferol::FerolController':
								frlns = '{urn:xdaq-application:ferol::FerolController}'
								prop = app.find(frlns + 'properties')
								ho.__class__ = FEROL ## Make it a FEROL
								ho.setStreams(prop.find(frlns + 'enableStream0').text, prop.find(frlns + 'enableStream1').text)
								if ho.enableStream0:
									self._nStreams += 1
									maxsizes.append(int(prop.find(frlns + 'Event_Length_Max_bytes_FED0').text))
								if ho.enableStream1:
									self._nStreams += 1
									maxsizes.append(int(prop.find(frlns + 'Event_Length_Max_bytes_FED1').text))
								break

					if h == 'FEROL': ## Misnomer, eFEROLs are called FEROLS
						self._nStreams += 1


					self._hostTypes[h].append(ho)
					self._hosts.append(ho)

				except KeyError as e:
					print 30*'#'
					print 'Unknown host type', h, ' Aborting.'
					print 30*'#'
					raise e

			except KeyError as e:
				print 30*'#'
				print h+n, 'is not defined in symbol map. Aborting.'
				print 30*'#'
				raise e

		if len(maxsizes) > 0:
			## Check whether they were all filled
			if len(maxsizes) != self._nStreams:
				raise RuntimeError("Didn't find all Event_Length_Max_bytes parameter in config file?!")

			## Check they are all the same:
			size_set = set()
			for x in maxsizes: size_set.add(x)
			if len(size_set) > 1:
				print "##########################################################"
				print "WARNING: You have FEROLs with different"
				print "         Event_Length_Max_bytes parameters in your config file!"
				print "         That probably shouldn't be."
				print " will wait for you to read this for 10s and then continue..."
				self.sleep(10)
				print "WARNING: You have FEROLs with different Event_Length_Max_bytes parameters in your config file!"

			## Check they are correct and alert
			if maxsizes[0] != SIZE_LIMIT_TABLE[self._nStreams//len(self._RUs)][0]:
				print "##########################################################"
				print "WARNING: Event_Length_Max_bytes for FEROLs seems to be set"
				print "         to the wrong value in your config .xml file!"
				print " Is set to:", maxsizes[0], "in config. Expected value:", SIZE_LIMIT_TABLE[self._nStreams//len(self._RUs)][0]
				print " will wait for you to read this for 10s and then continue..."
				self.sleep(10)
	def fillTemplate(self, filename):
		with open(filename, 'r') as ifile:
			template = ifile.read()
			filled = template
			for key in self._symbolMap.keys():
				filled = filled.replace(str(key), str(self._symbolMap[key]))
		return filled

	def sendSOAPMessage(self, host, port, message, command):
		"""Sends a SOAP message via curl, where message could be
			'SOAPAction: urn:xdaq-application:lid=0'
			or
			'Content-Location: urn:xdaq-application:class=CLASSNAME,instance=INSTANCE'
			and command could be a file:
			configure.cmd.xml
			or a simple command like:
			'Configure'
		"""
		cmd = "curl --stderr /dev/null -H \"Content-Type: text/xml\" -H \"Content-Description: SOAP Message\" -H \"%s\" http://%s:%d -d %s"
		'SOAPAction: urn:xdaq-application:lid=0'

		if 'SOAPAction' in message:
			## Want to send a command file, i.e. need to prepend a \@ before the filename
			command = '\@'+command
		elif 'Content-Location' in message:
			## Want to send a simple command, need to wrap it in escaped quotes
			command = '\"'+command+'\"'

		cmd = cmd % (message, host, port, command)

		call = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
		out,err = call.communicate()

		if 'Response' in out:
			print 'OK'
			return 0
		elif 'Fault' in out:
			print 'FAULT'
			return 1
		elif len(out) == 0:
			print 'NONE'
			return 1
		else:
			print 'UNKNOWN RESPONSE:'
			print separator
			print out
			print separator
			return 1
	def sendCmdFileToExecutive(self, host, port, cmdfile):
		if self._dryRun:
			if self.verbose > 1: print '%-18s %25s:%-5d %-35s' % ('sendCmdFileToExecutive', host, port, cmdfile)
			return 0

		if not os.path.exists(cmdfile):
			raise IOError('File '+configfile+' not found')
		stdout.write('Sending command file to executive %s:%d ... ' % (host, port))
		stdout.flush()
		message = 'SOAPAction: urn:xdaq-application:lid=0'
		return self.sendSOAPMessage(host, port, message, cmdfile)
	def sendCmdFileToApp(self, host, port, classname, instance, cmdFile): ## UNTESTED
		"""Sends a SOAP message contained in cmdfile to the application with classname and instance on host:port"""
		if self._dryRun:
			if self.verbose > 1: print '%-18s %25s:%-5d %25s %1s:\n%s' % ('sendCmdToApp', host, port, classname, instance, cmdFile)
			return

		message = 'SOAPAction: urn:xdaq-application:class=%s,instance=%d' % (classname, instance)
		command = '`cat %s`' % cmdfile
		return self.sendSOAPMessage(host, port, message, command)

		if not self._dryRun: return subprocess.check_call(['sendCmdFileToApp', host, str(port), classname, str(instance), cmdFile])
	def sendCmdToApp(self, host, port, classname, instance, command):
		"""Sends a simple command via SOAP to the application with classname and instance on host:port"""
		if self._dryRun:
			if self.verbose > 1: print '%-18s %25s:%-5d %25s %1s:\n%s' % ('sendCmdToApp', host, port, classname, instance, command)
			return 0
		message = 'Content-Location: urn:xdaq-application:class=%s,instance=%d' % (classname, int(instance))
		return self.sendSOAPMessage(host, port, message, command)
	def downloadMeasurements(self, host, port, classname, instance, outputfile):
		if self.verbose > 1: print separator
		url = 'http://%s:%d/urn:xdaq-application:class=%s,instance=%d/downloadMeasurements'
		url = url % (host, int(port), classname, int(instance))
		if self._dryRun: print 'curl -o', outputfile, url
		else: subprocess.check_call(['curl', '-o', outputfile, url])

	## Wrapper for existing perl scripts
	def sendSimpleCmdToApp(self, host, port, classname, instance, cmdName):
		if self.verbose > 1 and self._dryRun: print '%-18s %25s:%-5d %25s %1s\t%-12s' % ('sendSimpleCmdToApp', host, port, classname, instance, cmdName)
		if not self._dryRun: return subprocess.check_call(['sendSimpleCmdToApp', host, str(port), classname, str(instance), cmdName])
	def sendCmdToLauncher(self, host, port, cmd):
		if self.verbose > 1 and self._dryRun: print '%-18s %25s:%-5d %-15s' % ('sendCmdToLauncher', host, port, cmd)
		if not self._dryRun: return subprocess.call(['sendCmdToLauncher', host, str(port), cmd])
	def setParam(self, host, port, classname, instance, paramName, paramType, paramValue):
		if self.verbose > 1 and self._dryRun: print '%-18s %25s:%-5d %25s %1s\t%-25s %12s %6s' % ('setParam', host, port, classname, instance, paramName, paramType, paramValue)
		if not self._dryRun: return subprocess.check_call(['setParam', host, str(port), classname, str(instance), paramName, paramType, str(paramValue)])
	def getParam(self, host, port, classname, instance, paramName, paramType):
		if self.verbose > 1 and self._dryRun: print '%-18s %25s:%-5d %25s %1s\t%-25s %12s' % ('getParam', host, port, classname, instance, paramName, paramType)
		if not self._dryRun:
			call = subprocess.Popen(['getParam', host, str(port), classname, str(instance), paramName, paramType], stdout=subprocess.PIPE)
			out,err = call.communicate()
			return out
	def writeItem(self, host, port, classname, instance, item, data, offset=0):
		body = '<xdaq:WriteItem xmlns:xdaq="urn:xdaq-soap:3.0" offset="%s"  item="%s" data="%s"/>' % (str(offset), item, str(data))
		cmd = self._SOAPEnvelope % body
		cmd = cmd.replace('\"','\\\"') ## need to escape the quotes when passing as argument
		return self.sendCmdToApp(host, port, classname, str(instance), cmd)

	## Launchers
	def stopXDAQLaunchers(self):
		"""Kills the xdaqLauncher process on all the SOAP hosts defined in the symbolmap"""
		for host in self._allHosts:
			# host,port = self._symbolMap[hostkey+"_SOAP_HOST_NAME"], self._symbolMap[hostkey+"_SOAP_PORT"]
			if self.verbose > 1: print "Stopping xdaqLauncher for %-20s on %s:%d" % (host.name, host.host, host.port)
			self.sendCmdToLauncher(host.host, host.lport, 'STOPLAUNCHER')
	def startXDAQLauncher(self, host, port, logfile):
		"""Start a single xdaqLauncher process on host:port"""
		sshCmd      = "ssh -x -n " + host
		launcherCmd = '"cd /tmp && sudo rm -f /tmp/core.* && source %s/setenv%s.sh && xdaqLauncher %d"' % (self._testDir, self._testEnv, port)
		awkCmd      = "awk '{print \"%s:%d \" $0}'" % (host, port)
		# cmd         = sshCmd + " \"sudo -u %s sh -c \\\""%self._user + launcherCmd +"\\\"\" | " +  awkCmd + " &"
		cmd         = sshCmd + " \"sudo -u %s sh -c \\"%self._user + launcherCmd +"\\\" | " +  awkCmd + " &"
		# print cmd
		if self._dryRun:
			print cmd
		else: return subprocess.call(cmd, stderr=logfile, stdout=logfile, shell=True)
		# else: return subprocess.call(shlex.split(cmd), stderr=stdout, stdout=stdout)
	def startXDAQLaunchers(self, logfile):
		"""Starts an xdaqLauncher process on all the SOAP hosts defined in the symbolmap"""
		for host in self._allHosts:
			message = "Starting xdaqLauncher for %-20s on %s:%d(LAUNCHER):%d(SOAP)" % (host.name, host.host, host.lport, host.port)
			logfile.write(message + '\n')
			print message
			self.startXDAQLauncher(host.host,host.lport,logfile)
			self.sleep(0.2)

	## Multi-commands
	def sendCmdToEVMRUBU(self, cmd): ## ordering for configure
		if self.verbose > 0: print separator
		for n,evm in enumerate(self._EVM):
			self.sendSimpleCmdToApp(evm.host, evm.port, self.namespace+'EVM', str(n), cmd)
		for n,ru in enumerate(self._RUs):
			classname = 'RU'
			if self.useEvB and n==0: classname = 'EVM'
			self.sendSimpleCmdToApp(ru.host, ru.port, self.namespace+classname, str(n), cmd)
		for n,bu in enumerate(self._BUs):
			self.sendSimpleCmdToApp(bu.host, bu.port, self.namespace+'BU', str(n), cmd)
	def sendCmdToRUEVMBU(self, cmd): ## ordering for enable
		if self.verbose > 0: print separator
		for n,ru in enumerate(self._RUs):
			classname = 'RU'
			if self.useEvB and n==0: classname = 'EVM'
			self.sendSimpleCmdToApp(ru.host, ru.port, self.namespace+classname, str(n), cmd)
		for n,evm in enumerate(self._EVM):
			self.sendSimpleCmdToApp(evm.host, evm.port, self.namespace+'EVM', str(n), cmd)
		for n,bu in enumerate(self._BUs):
			self.sendSimpleCmdToApp(bu.host, bu.port, self.namespace+'BU', str(n), cmd)
	def sendCmdToFEROLs(self, cmd):
		if self.verbose > 0: print separator
		for frl in self._FEROLs:
			self.sendSimpleCmdToApp(frl.host, frl.port, 'ferol::FerolController', 0, cmd)
	def setSizeFEROLs(self, fragSize, fragSizeRMS, rate='max'):
		if self.verbose > 0: print separator
		delay=20
		if not rate=='max':
			# delay = int(1000000.0 / rate - fragSize/8.0*6.4 - 150) # Obsolete according to Petr
			delay = int(1000000.0 / rate - fragSize/8.0*6.4)

		for frl in self._FEROLs:
			if frl.enableStream0:
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED0',       'unsignedInt', int(fragSize))
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED0', 'unsignedInt', int(fragSizeRMS))
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED0',           'unsignedInt', int(delay))
			if frl.enableStream1:
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED1',       'unsignedInt', int(fragSize))
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED1', 'unsignedInt', int(fragSizeRMS))
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED1',           'unsignedInt', int(delay))

	## Control methods
	def setup(self, configfile, relRMS=-1):
		"""Read config file, clean up and re-create run directory, fill config templates, create output directory"""
		if self.verbose > 0: print separator

		## Read config file, cleanup run dir
		if self.verbose > 0: print 'Reading config file', configfile
		self.readXDAQConfigTemplate(configfile)
		if not self._dryRun:
			subprocess.check_call(['rm', '-rf', self._runDir])
			subprocess.check_call(['mkdir', '-p', self._runDir])

		## Clean up and create output dir
		self.prepareOutputDir(relRMS)

		## Fill configuration template
		if self.verbose > 0: print 'Filling configuration template in ' + self._runDir + '/configuration.xml'
		if not self._dryRun:
			filledconfig = self.fillTemplate(configfile)
			with open(self._runDir+'/configuration.xml', 'w') as file:
				file.write(filledconfig)

		## Produce configure command file
		if self.verbose > 0: print 'Producing configuration command file in ' + self._runDir + '/configure.cmd.xml'
		if not self._dryRun:
			with open(self._runDir+'/configure.cmd.xml', 'w') as file:
				configureBody = '<xdaq:Configure xmlns:xdaq=\"urn:xdaq-soap:3.0\">\n\n\n' + filledconfig + '\n\n\n</xdaq:Configure>\n'
				configureCmd = self._SOAPEnvelope % configureBody
				file.write(configureCmd)
	def start(self, fragSize, fragSizeRMS=0, rate='max'):
		"""Start all XDAQ processes, set configuration for fragSize and start running"""
		self.currentFragSize = fragSize
		if self.verbose > 0: print separator
		if self.verbose > 0: print "Starting XDAQ processes"
		for h in self._hosts:
			self.sendCmdToLauncher(h.host, h.lport, 'STARTXDAQ'+str(h.port))
		self.sleep(2)

		if not self.webPingXDAQ():
			if self.verbose > 0: print separator
			if self.verbose > 0: print 'Waiting 3 seconds and checking again...'
			self.sleep(3)
			if not self.webPingXDAQ():
				raise RuntimeError('Not all hosts ready!')

		if self.verbose > 0: print separator
		if self.verbose > 0: print "Configuring XDAQ processes"
		for h in self._hosts:
			if self.sendCmdFileToExecutive(h.host, h.port, self._runDir+'/configure.cmd.xml') != 0:
				raise RuntimeError('Failed to send configure command to %s at %s:%d!' % (h.name, h.host, h.port))

		self.sleep(2)
		self.setSize(fragSize, fragSizeRMS, rate=rate)
		self.sleep(5)
		# self.sendCmdToRUEVMBU('Enable')
		self.sendCmdToFEROLs('Enable')
	def stopXDAQ(self, host):
		if self._dryRun:
			if self.verbose > 0: print 'Stopping %25s:%-5d' % (host.host, host.lport)
			return
		iterations = 0
		while self.tryWebPing(host.host, host.port) == 0:
			self.sendCmdToLauncher(host.host, host.lport, 'STOPXDAQ')
			iterations += 1
			if iterations > 1:
				print " repeating %s:%-d" % (host.host, host.port)
	def stopXDAQs(self):
		"""Sends a 'STOPXDAQ' cmd to all SOAP hosts defined in the symbolmap that respond to a tryWebPing call"""
		if self.verbose > 0: print separator
		if self.verbose > 0: print "Stopping XDAQs"
		# self.sendCmdToFEROLs('Pause')
		# self.sendCmdToEVMRUBU('Halt')
		for host in self._allHosts:
			self.stopXDAQ(host)
	def setSize(self, fragSize, fragSizeRMS=0, rate='max'):
		## This is supposed to work both for eFEROLs and FEROLS!
		if self.verbose > 0: print separator
		if self.verbose > 0: print "Setting fragment size to %5d bytes +- %-5d at %s kHz rate" % (fragSize, fragSizeRMS, str(rate))

		## In case of FEROLs:
		if len(self._FEROLs) > 0:
			## Set fragment size and delay for FEROLs:
			self.setSizeFEROLs(fragSize, fragSizeRMS, rate)
			self.currentFragSize = fragSize

			## Set super-fragment size for BUs
			if not self.useEvB:
				if self.verbose > 0: print separator
				for n,bu in enumerate(self._BUs):
					self.setParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'unsignedLong', self._nStreams*int(fragSize))
				if not self._dryRun:
					for n,bu in enumerate(self._BUs):
						print bu.name, 'dummyFedPayloadSize', int(self.getParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'xsd:unsignedLong'))

			self.sendCmdToFEROLs('Configure')
			self.sleep(5)

			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToRUEVMBU('Enable') ## Have to enable RUs/EVM/BUs here?
			return

		## In case of eFEROLs:
		elif len(self._eFEROLs) > 0:
			## Configure and enable pt::frl application on eFEROLs:
			if self.verbose > 0: print separator
			for n,efrl in enumerate(self._eFEROLs):
				self.sendSimpleCmdToApp(efrl.host, efrl.port, 'pt::frl::Application', n, 'Configure')
			if self.verbose > 0: print separator
			for n,efrl in enumerate(self._eFEROLs):
				self.sendSimpleCmdToApp(efrl.host, efrl.port, 'pt::frl::Application', n, 'Enable')
			self.sleep(2)

			## Set fragment size for eFEROLs
			if self.verbose > 0: print separator
			for n,efrl in enumerate(self._eFEROLs):
				if self.useEvB or self.useLogNormal: self.setParam(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'fedSize',     'unsignedInt',  fragSize)
				else:                                self.setParam(efrl.host, efrl.port, 'Client',                n, 'currentSize', 'unsignedLong', fragSize)
			self.currentFragSize = fragSize


			## Set lognormal rms for eFEROLs (when running with --useLogNormal)
			if self.useLogNormal:
				if self.verbose > 0: print separator
				for n,efrl in enumerate(self._eFEROLs):
					self.setParam(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'fedSizeStdDev', 'unsignedInt', int(fragSizeRMS))
					self.setParam(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'useLogNormal',  'boolean',     'true')

			## Set super-fragment size for BUs
			if not self.useEvB:
			# if not self.useEvB and not self.useLogNormal: ## pre Aug25
				if self.verbose > 0: print separator
				for n,bu in enumerate(self._BUs):
					self.setParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'unsignedLong', self._nStreams*int(fragSize))
				if not self._dryRun:
					for n,bu in enumerate(self._BUs):
						print bu.name, 'dummyFedPayloadSize', int(self.getParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'xsd:unsignedLong'))

			if self.verbose > 0: print separator

			if self.useEvB or self.useLogNormal:
				for n,efrl in enumerate(self._eFEROLs):
					self.sendSimpleCmdToApp(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'Configure')

			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToRUEVMBU('Enable') ## Have to enable RUs/EVM/BUs here?

			if self.verbose > 0: print separator
			## Enable eFEROL clients
			for n,efrl in enumerate(self._eFEROLs):
				if self.useEvB or self.useLogNormal: self.sendSimpleCmdToApp(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'Enable')
				else:                                self.sendSimpleCmdToApp(efrl.host, efrl.port, 'Client',                n, 'start')
			return
	def changeSize(self, fragSize, fragSizeRMS=0, rate='max'):
		## For FEROLs: pause, change size, resume
		if len(self._FEROLs) > 0 and not self.useEvB and not self.stopRestart:
			if self.verbose > 0: print separator
			if self.verbose > 0: print "Changing fragment size to %5d bytes +- %5d at %s rate" % (fragSize, fragSizeRMS, str(rate))

			## Pause FEROLs
			self.sendCmdToFEROLs('Pause')

			## Change fragment size and delay for FEROLs:
			self.setSizeFEROLs(fragSize, fragSizeRMS, rate)
			self.currentFragSize = fragSize

			## Halt EVM/RUs/BUs
			self.sendCmdToEVMRUBU('Halt')
			self.sleep(2)

			## Change super-fragment size for BUs
			if self.verbose > 0: print separator
			for n,bu in enumerate(self._BUs):
				self.setParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'unsignedLong', self._nStreams*int(fragSize))
			if self.verbose > 0: print separator
			for n,bu in enumerate(self._BUs):
				if not self._dryRun: print bu.name, 'dummyFedPayloadSize', int(self.getParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'xsd:unsignedLong'))

			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToRUEVMBU('Enable')
			self.sendCmdToFEROLs('SetupEVG')
			self.sendCmdToFEROLs('Resume')
			return

		## For eFEROLs: stop everything, set new size, start again
		elif len(self._eFEROLs) > 0 or self.useEvB or self.stopRestart:
			self.stopXDAQs()
			self.sleep(5)
			self.start(fragSize, fragSizeRMS=fragSizeRMS)
			return

		else: return
	def prepareOutputDir(self, relRMS):
		import glob
		self._outputDir += self._testCase
		if self.useLogNormal: self._outputDir += '_RMS_%3.1f/' % float(relRMS)
		if not self._outputDir.endswith('/'): self._outputDir += '/'
		if self.verbose > 0: print separator
		if self.verbose > 0: print 'Storing output in:', self._outputDir
		if self._dryRun: return

		if os.path.exists(self._outputDir):
			newdir = self._outputDir + 'previous/' + time.strftime('%b%d-%H%M%S')
			os.makedirs(newdir)
			if len(glob.glob(self._outputDir+'*.csv')) > 0:
				subprocess.check_call(['mv'] + glob.glob(self._outputDir+'*.csv') + [newdir])
		else:
			os.makedirs(self._outputDir)

		## Prepare output file:
		with open(self._outputDir+'/server.csv', 'a') as outfile:
			outfile.write('## Testcase: %s\n' % self._testCase)
			if self.useLogNormal: outfile.write('## useLogNormal = True, RMS = %5.2f\n' % float(relRMS) )
			outfile.write('## %s\n' % time.strftime('%a %b %d, %Y / %H:%M:%S'))
			outfile.write('\n')
			outfile.close()
	def getResultsEvB(self, duration, interval=5):
		"""Python implementation of testRubuilder.pl script
		This will get the parameter RATE from the BU after an interval time for
		a total duration."""
		if self._dryRun: return
		if self.useEvB:
			sufragsize = self._nStreams/len(self._RUs) * self.currentFragSize
			ratesamples = []
			starttime = time.time()
			stdout.write('Rate samples: ')
			while(time.time() < starttime+duration):
				time.sleep(interval)
				sample = int(self.getParam(self._RUs[0].host, self._RUs[0].port, 'evb::EVM', str(0), 'eventRate', 'xsd:unsignedInt'))
				ratesamples.append(sample)
				if self.verbose > 0:
					stdout.write(str(sample)+' ')
					stdout.flush()
			print '\n'

			with open(self._outputDir+'/server.csv', 'a') as outfile:
				if self.verbose > 0: print 'Saving output to', self._outputDir+'server.csv'
				outfile.write(str(sufragsize))
				for rate in ratesamples:
					outfile.write(', ')
					outfile.write(str(rate))
				outfile.write('\n')

		else:
			print "getResultsEvB() only works when running with the EvB, try getResults()"
			return
	def getResults(self):
		"""Download results for each BU, concatenate them, and store them in server.csv. Only works for the gevb2g!"""
		if self._dryRun: return
		if not self.useEvB:
			outputfiles = []
			for n,h in enumerate(self._BUs):
				outputfile = '%s/server%d.csv' % (self._outputDir, n)
				self.downloadMeasurements(h.host, h.port, self.namespace+'BU', n, outputfile) ## need namespace here? this only works for gevb2g anyway
				outputfiles.append(outputfile)

			## Concatenate output files
			with open(self._outputDir+'/server.csv', 'a') as outfile:
				if self.verbose > 0: print 'Saving output to', self._outputDir+'server.csv'
				for fname in outputfiles:
					with open(fname, 'r') as infile:
						outfile.write(infile.read())
						outfile.write('\n')
		else:
			print "getResults() only works when running with the gevb2g, try getResultsEvB()"
			return
	def webPingXDAQ(self):
		print separator
		print "Checking availability of relevant hosts"
		for host in self._hosts:
			stdout.write(" ... checking %25s:%-5d \t\t ... " % (host.host, host.port))
			stdout.flush()
			if self._dryRun or self.tryWebPing(host.host, host.port) == 0:
				stdout.write("OK\n")
				stdout.flush()
			else:
				stdout.write("FAILED\n")
				stdout.flush()
				return False
		return True
	def tryWebPing(self, host, port):
		if self._dryRun:
			print '%-18s %25s:%-5d' % ('webPing', host, port)
			return 0
		cmd = "wget -o /dev/null -O /dev/null --timeout=30 http://%s:%d/urn:xdaq-application:lid=3" % (host,int(port))
		return subprocess.call(shlex.split(cmd))


######################################################################
## Interface:
######################################################################
def testBuilding(d2c, minevents=1000, waittime=20):
	if options.verbose > 0: print separator
	if options.verbose > 0: print 'Testing event building for', waittime, 'seconds'
	d2c.sleep(waittime)
	if d2c._dryRun: return True
	eventCounter = []
	for n,bu in enumerate(d2c._BUs):
		if d2c.useEvB: nEvts = d2c.getParam(bu.host, bu.port, d2c.namespace+'BU', str(n), 'nbEventsBuilt', 'xsd:unsignedInt')
		else:          nEvts = d2c.getParam(bu.host, bu.port, d2c.namespace+'BU', str(n), 'eventCounter',  'xsd:unsignedLong')
		try:
			eventCounter.append(int(nEvts))
		except ValueError:
			print 50*'#'
			print 'Error getting number of events built. Message was:'
			print nEvts
			print 50*'#'
			return False
		if options.verbose > 1: print bu.name, 'number of events built: ', int(nEvts)
	print separator

	totEvents = 0
	for evtCount in eventCounter:
		if evtCount < minevents:
			return False
		else:
			totEvents += evtCount
	return True
def getListOfSizes(maxSize, minSize=256):
	stepsize = 256
	allsteps = [ n*stepsize for n in xrange(1, 1000) if n*stepsize <= 8192] ## multiples of stepsize up to 8192
	allsteps += [9216, 10240, 11264, 12288, 13312, 14336, 15360, 16000]
	if options.short: allsteps = [256, 512, 1024, 2048, 3072, 4096, 6144, 8192, 12288, 16000]

	steps = []
	for step in allsteps:
		if step >= minSize and step <= maxSize: steps.append(step)

	print ' Will scan over the following sizes:', steps
	return steps

## Run a single test
def runTest(configfile, fragSize, options, relRMS=0.0):
	"""Usage: runTest(configfile, fragSize)
	Run a test reading the setup from configfile and using fragment size fragSize"""
	d2c = daq2Control(options)
	d2c.useLogNormal = options.useLogNormal
	d2c.setup(configfile, relRMS=relRMS)

	d2c.stopXDAQs()
	d2c.start(fragSize, float(relRMS)*fragSize, rate=options.useRate)

	if not testBuilding(d2c, 1000, 15):
		if options.verbose > 0: print 'Test failed, built less than 1000 events!'
		d2c.stopXDAQs()
		exit(-1)
	if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'

	if d2c.verbose > 0: print "Building events ..."
	if d2c.useEvB:
		## Get results ala testRubuilder script every 5 seconds
		d2c.getResultsEvB(options.duration, interval=5)
	else:
		## Wait for the full duration, then get all the results at once
		d2c.sleep(options.duration)
		d2c.getResults()

	if options.waitBeforeStop: raw_input("Press Enter to stop the XDAQs...")

	d2c.stopXDAQs()
	print separator
	print ' DONE '
	print separator

## Run a scan over fragment sizes
def runScan(configfile, options, relRMS=0.0):
	"""Usage: runScan(configfile, nSteps, minSize, maxSize)
	Run a scan of fragment sizes reading the setup from configfile"""
	d2c = daq2Control(options)
	d2c.setup(configfile, relRMS=relRMS)

	steps = getListOfSizes(options.maxSize, minSize=options.minSize)

	## Check maxSize from table and merging case:
	mergingby = d2c._nStreams//len(d2c._RUs)
	if steps[-1] > SIZE_LIMIT_TABLE[mergingby][1]:
		print "##########################################################"
		print "WARNING: Your maximum size for scanning doesn't seem to"
		print "         make sense. Please consider!"
		print " Is set to:", steps[-1], ". Expected to scan only until:", SIZE_LIMIT_TABLE[mergingby][1]
		print " will wait for you to read this for 10s and then continue..."
		d2c.sleep(10)


	d2c.stopXDAQs()
	d2c.start(options.minSize, float(relRMS)*options.minSize, rate=options.useRate)

	if not testBuilding(d2c, 1000, 15):
		if options.verbose > 0: print 'Test failed, built less than 1000 events!'
		d2c.stopXDAQs()
		exit(-1)
	if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'

	for step in steps:
		d2c.changeSize(step, float(relRMS)*step, rate=options.useRate)
		if options.verbose > 0: print separator
		if options.verbose > 0: print "Building events at fragment size %d for %d seconds..." % (step, options.duration)
		if d2c.useEvB:
			## Get results ala testRubuilder script every 5 seconds
			d2c.getResultsEvB(options.duration, interval=5)
		else:
			## Wait for the full duration and get results at the end
			d2c.sleep(options.duration)
			## For eFEROLs, get results after each step
			if len(d2c._eFEROLs) > 0 or d2c.stopRestart: d2c.getResults()
		if options.verbose > 0: print "Done"

	## For FEROLs, get results at the end
	if len(d2c._FEROLs) > 0 and not d2c.useEvB and not d2c.stopRestart: d2c.getResults()

	d2c.stopXDAQs()
	print separator
	print ' DONE '
	print separator

######################################################################
## main
def addOptions(parser):
	usage = """
	%prog [options] --start config.xml fragsize
	%prog [options] --changeSize config.xml newfragsize
	%prog [options] --changeSize --useLogNormal config.xml newfragsize relRMS

	%prog [options] --runTest config.xml fragsize
	%prog [options] --runTest --useLogNormal config.xml fragsize fragsizerms
	%prog [options] --runScan config.xml
	%prog [options] --runScan --useLogNormal config.xml fragsizerms

	%prog [options] --runRMSScan config.xml

	Examples:
	%prog [options] --runTest --duration 30 /nfshome0/mommsen/daq/dev/daq/evb/test/cases/daq2val/FEROLs/16s8fx1x4/configuration.template.xml 1024
	%prog [options] --runTest --useLogNormal ~/andrea_test/cases/eFEROLs/gevb2g/dummyFerol/16x2x2/configuration.template.xml 1024 0.5
	%prog [options] --runScan --useLogNormal ../cases/FEROLs/gevb2g/16s16fx2x2/configuration.template.xml 2.0
	%prog [options] --runTest --useRate 100 --useLogNormal config.template.xml 1024 0.5

	Debugging options:
		--dry            (don't send any commands, just print them)
		--waitBeforeStop (wait for a key press before stopping the running system)
		--verbose        (set verbose level)
		--symbolMap      (use a custom symbol map)

	Launcher options:
		--startLaunchers   (start XDAQ launchers on all machines defined in symbol map)
		--stopLaunchers    (start XDAQ processes on all machines defined in symbol map)
		--stopXDAQs        (kill XDAQ launchers on all machines defined in symbol map)

	"""
	parser.usage = usage

	## Standard interface:
	parser.add_option("--runTest", default=False, action="store_true",                dest="runTest",        help="Run a test setup, needs two arguments: config and fragment size")
	parser.add_option("--runScan", default=False, action="store_true",                dest="runScan",        help="Run a scan over fragment sizes, set the range using the options --maxSize and --minSize")
	parser.add_option("--runRMSScan", default=False, action="store_true",             dest="runRMSScan",     help="Run four scans over fragment sizes with different RMS values")
	parser.add_option("--useLogNormal", default=False, action="store_true",           dest="useLogNormal",   help="Use lognormal generator for e/FEROLs (will use the dummyFerol instead of the Client in case of the eFEROLS). You need to provide the relative rms (i.e. in multiples of the fragment size) as an argument.")
	parser.add_option("-d", "--duration", default=60, action="store", type="int",     dest="duration",       help="Duration of a single step in seconds, [default: %default s]")
	parser.add_option("--useRate", default=0, action="store", type="int",             dest="useRate",        help="Event rate in kHz, [default is maximum rate]")
	parser.add_option("--maxSize", default=16000, action="store", type="int",         dest="maxSize",        help="Maximum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--minSize", default=256, action="store", type="int",           dest="minSize",        help="Minimum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--nSteps", default=100, action="store", type="int",            dest="nSteps",         help="Number of steps between minSize and maxSize, [default: %default]")
	parser.add_option("--short", default=False, action="store_true",                  dest="short",          help="Run a short scan with only a few points")
	parser.add_option("--stopRestart", default=False, action="store_true",            dest="stopRestart",    help="Stop XDAQ processes after each size and restart instead of changing the size on the fly (only relevant for scans)")

	## Debugging options:
	parser.add_option("--dry", default=False, action="store_true",                    dest="dry",            help="Just print the commands without sending anything")
	parser.add_option("-w", "--waitBeforeStop", default=False, action="store_true",   dest="waitBeforeStop", help="For for key press before stopping the event building")
	parser.add_option("-v", "--verbose", default=1, action="store", type='int',       dest="verbose",        help="Set the verbose level, [default: %default (semi-quiet)]")

	## Control:
	parser.add_option("--stopLaunchers", default=False, action="store_true",          dest="stopLaunchers",        help="Stop all the XDAQ launchers and exit")
	parser.add_option("--startLaunchers", default=False, action="store_true",         dest="startLaunchers",       help="Start all the XDAQ launchers and exit")
	parser.add_option("--stopXDAQs", default=False, action="store_true",              dest="stopXDAQs",            help="Stop all the XDAQ processes and exit")
	parser.add_option("-l", "--logFile", default='launcherLog.txt', action="store", type='string', dest="logFile", help="Store stdout and stderr output of XDAQ launchers in this file, [default: %default]")

	parser.add_option("--start", default=False, action="store_true",                  dest="start",          help="Read a config, set up and start running. Needs config, size, optionally rms as arguments.")
	parser.add_option("--changeSize", default=False, action="store_true",             dest="changeSize",     help="Halt, change size and resume. Needs config and new size as arguments.")

	parser.add_option("-m", "--symbolMap", default='', action="store", type="string", dest="symbolMap",      help="Use a symbolmap different from the one set in the environment")

if __name__ == "__main__":
	from optparse import OptionParser
	parser = OptionParser()
	addOptions(parser)
	(options, args) = parser.parse_args()

	if options.useRate == 0: options.useRate = 'max'

	if options.stopLaunchers:
		d2c = daq2Control(options)
		d2c.stopXDAQs()
		d2c.stopXDAQLaunchers()
		exit(0)
	if options.stopXDAQs:
		d2c = daq2Control(options)
		d2c.stopXDAQs()
		print separator
		exit(0)
	if options.startLaunchers:
		with open(options.logFile, 'w') as logfile:
			length = 120
			logfile.write(length*'#' + '\n')
			logfile.write(length*'#' + '\n')
			logfile.write('\n')
			logfile.write('  Starting launchers at %s \n' % time.strftime('%a %b %d, %Y / %H:%M:%S'))
			logfile.write('\n')
			logfile.write(length*'#' + '\n')
			logfile.write(length*'#' + '\n')
			d2c = daq2Control(options)
			d2c.startXDAQLaunchers(logfile)
			logfile.write(length*'#' + '\n')
			logfile.write(length*'#' + '\n')
			logfile.write('\n')
		exit(0)

	if options.start and len(args) > 1:
		## this creates also output and run dirs
		if options.useLogNormal:
			if len(args) < 3:
				print "You need give an RMS argument when using --useLogNormal"
				exit(-1)
			else:
				d2c = daq2Control(options)

				## Stop previously running things
				d2c.stopXDAQs()
				d2c.useLogNormal = True

				relRMS = float(args[2])
				fragSize = int(args[1])

				d2c.setup(args[0], relRMS=relRMS)
				d2c.start(fragSize, float(relRMS)*fragSize, rate=options.useRate)
				if not testBuilding(d2c, 1000, 15):
					if options.verbose > 0: print 'Test failed, built less than 1000 events!'
					exit(-1)
				if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'
				exit(0)
		else:
			d2c = daq2Control(options)

			## Stop previously running things
			d2c.stopXDAQs()

			d2c.useLogNormal = False
			fragSize = int(args[1])

			d2c.setup(args[0])
			d2c.start(fragSize, rate=options.useRate)
			d2c.sleep(10)
			if not testBuilding(d2c, 1000):
				if options.verbose > 0: print 'Test failed, built less than 1000 events!'
				exit(-1)
			if options.verbose > 0: print 'Test successful (built more than 1000 events in each BU), continuing...'
			exit(0)
	if options.changeSize and len(args) > 1:
		if options.useLogNormal:
			if len(args) < 3:
				print "You need to give an RMS argument when using --useLogNormal"
				exit(-1)
			else:
				d2c = daq2Control(options)
				d2c.useLogNormal = True
				relRMS = float(args[2])
				fragSize = int(args[1])
				d2c.readXDAQConfigTemplate(args[0])
				d2c.changeSize(fragSize, relRMS*fragSize, rate=options.useRate)
				exit(0)
		else:
			d2c = daq2Control(options)
			d2c.useLogNormal = False
			fragSize = int(args[1])
			d2c.readXDAQConfigTemplate(args[0])
			d2c.changeSize(fragSize, rate=options.useRate)
			exit(0)

	if options.runTest and len(args) > 1:
		if options.useLogNormal:
			if len(args) < 3:
				print "You need give an RMS argument when using --useLogNormal"
				exit(-1)
			else:
				runTest(args[0], options, fragSize=int(args[1]), relRMS=args[2])
				exit(0)
		else:
			runTest(args[0], options, fragSize=int(args[1]))
			exit(0)
	if options.runScan and len(args) > 0:
		if options.useLogNormal:
			if len(args) < 2:
				print "You need give an RMS argument when using --useLogNormal"
				exit(-1)
			else:
				runScan(args[0], options, relRMS=args[1])
				exit(0)
		else:
			runScan(args[0], options)
			exit(0)
	if options.runRMSScan and len(args) > 0:
		config = args[0]
		# rms_values = [0.5, 1.0, 2.0]
		rms_values = [0.0, 0.5, 1.0, 2.0]
		for rms in rms_values:
			print 80*'#'
			print 80*'#'
			print '## STARTING SCAN OF RMS =', rms
			print 80*'#'
			print 80*'#'
			runScan(config, options, relRMS=rms)
		print 80*'#'
		print 80*'#'
		print '## EVERYTHING DONE'
		print 80*'#'
		print 80*'#'
		exit(0)

	parser.print_help()
	exit(-1)

