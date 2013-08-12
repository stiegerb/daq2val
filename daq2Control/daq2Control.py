#! /usr/bin/env python
import subprocess
import os, shlex, glob
import re

import xml.etree.ElementTree as ET


separator = 70*'-'

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


class daq2Control(object):
	"""docstring for daq2Control"""
	def __init__(self,dryrun=False,symbolMap=''):
		try:
			self._symbolMapFile = os.environ['TESTS_SYMBOL_MAP']
			self._testDir       = os.environ['RUB_TESTER_HOME']
			self._outputDir     = self._testDir + '/data/'
			self._testCase      = ''
			self._platform      = os.environ['XDAQ_PLATFORM']
			self._runDir        = self._testDir + '/' + self._platform + '/'
			self._user          = os.environ['USER']
			self._testType      = os.environ['TEST_TYPE']
		except KeyError as e:
			print 30*'#'
			print 'Environment missing, did you forget to source setenv-COL.sh? Aborting.'
			print 30*'#'
			raise e

		if len(symbolMap)>0:
			self._symbolMapFile = symbolMap

		self._dryRun    = dryrun ## if true, only print commands without doing anything
		self._testEnv   = ""
		self._symbolMap = {} ## a dictionary of all symbols in the map


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

		self.namespace = 'gevb2g::'
		if options.useEVB: self.namespace = 'evb::'


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
		print 20*'-'
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

	def sleep(self,time=0.5):
		if self._dryRun: print 'sleep', time
		else: subprocess.call(['sleep', str(time)])

	def readXDAQConfigTemplate(self, configfile):
		# self._testCase = os.path.basename(configfile).strip('.xml')
		self._testCase = os.path.dirname(configfile).split('/').pop()
		config = ET.parse(configfile)
		partition = config.getroot()
		for context in partition:
			if not context.tag.endswith('Context'): continue

			url = context.attrib['url']
			pattern = re.compile(r'http://([A-Z_0-9]*?)([0-9]+)_SOAP_HOST_NAME:.*')
			h,n = pattern.match(url).group(1), pattern.match(url).group(2)
			try:
				soap_host, soap_port = self._symbolMap[h+n+'_SOAP_HOST_NAME'], self._symbolMap[h+n+'_SOAP_PORT']
				try:
					print 'Adding', h+n, 'at', soap_host+':'+str(soap_port)
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
								if ho.enableStream0: self._nStreams += 1
								if ho.enableStream1: self._nStreams += 1
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

	def stopXDAQLaunchers(self):
		"""Kills the xdaqLauncher process on all the SOAP hosts defined in the symbolmap"""
		for host in self._allHosts:
			# host,port = self._symbolMap[hostkey+"_SOAP_HOST_NAME"], self._symbolMap[hostkey+"_SOAP_PORT"]
			print "Stopping xdaqLauncher for %-20s on %s:%d" % (host.name, host.host, host.port)
			self.sendCmdToLauncher(host.host, host.lport, 'STOPLAUNCHER')

	def stopXDAQs(self):
		"""Sends a 'STOPXDAQ' cmd to all SOAP hosts defined in the symbolmap"""
		print "Stopping XDAQs"
		for host in self._allHosts:
			self.sendCmdToLauncher(host.host, host.lport, 'STOPXDAQ')
		print separator

	def startXDAQLauncher(self, host, port,logfile):
		"""Start a single xdaqLauncher process on host:port"""
		sshCmd      = "ssh -x -n " + host
		launcherCmd = '"cd /tmp && sudo rm -f /tmp/core.* && source %s/setenv%s.sh && xdaqLauncher %d"' % (self._testDir, self._testEnv, port)
		awkCmd      = "awk '{print \"%s:%d \" $0}'" % (host, port)
		cmd         = sshCmd + " \"sudo -u %s sh -c \\\""%self._user + launcherCmd +"\\\"\" | " +  awkCmd + " &"
		if self._dryRun:
			print cmd
		else: return subprocess.call(shlex.split(cmd), stderr=logfile, stdout=logfile)
		## TODO: Handle return value and failure procedure

	def startXDAQLaunchers(self, logfile):
		"""Starts an xdaqLauncher process on all the SOAP hosts defined in the symbolmap"""
		for host in self._allHosts:
			print "Starting xdaqLauncher for %-20s on %s:%d(LAUNCHER):%d(SOAP)" % (host.name, host.host, host.lport, host.port)
			self.startXDAQLauncher(host.host,host.lport,logfile)

	def fillTemplate(self, filename):
		with open(filename, 'r') as ifile:
			template = ifile.read()
			filled = template
			for key in self._symbolMap.keys():
				filled = filled.replace(str(key), str(self._symbolMap[key]))
		return filled

	def sendCmdToEVMRUBU(self, cmd): ## ordering for configure
		for n,evm in enumerate(self._EVM):
			self.sendSimpleCmdToApp(evm.host, evm.port, self.namespace+'EVM', str(n), cmd)
		for n,ru in enumerate(self._RUs):
			classname = 'RU'
			if options.useEVB and n==0: classname = 'EVM'
			self.sendSimpleCmdToApp(ru.host, ru.port, self.namespace+classname, str(n), cmd)
		for n,bu in enumerate(self._BUs):
			self.sendSimpleCmdToApp(bu.host, bu.port, self.namespace+'BU', str(n), cmd)

	def sendCmdToRUEVMBU(self, cmd): ## ordering for enable
		for n,ru in enumerate(self._RUs):
			classname = 'RU'
			if options.useEVB and n==0: classname = 'EVM'
			self.sendSimpleCmdToApp(ru.host, ru.port, self.namespace+classname, str(n), cmd)
		for n,evm in enumerate(self._EVM):
			self.sendSimpleCmdToApp(evm.host, evm.port, self.namespace+'EVM', str(n), cmd)
		for n,bu in enumerate(self._BUs):
			self.sendSimpleCmdToApp(bu.host, bu.port, self.namespace+'BU', str(n), cmd)

	def sendCmdToFEROLs(self, cmd):
		for frl in self._FEROLs:
			self.sendSimpleCmdToApp(frl.host, frl.port, 'ferol::FerolController', 0, cmd)

	def setSizeFEROLs(self, fragSize, fragSizeStd, rate='max'):
		delay=20
		if not rate=='max':
			# delay = int(1000000.0 / rate - fragSize/8.0*6.4 - 150) # Obsolete according to Petr
			delay = int(1000000.0 / rate - fragSize/8.0*6.4)

		for frl in self._FEROLs:
			if frl.enableStream0:
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED0',       'unsignedInt', fragSize)
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED0', 'unsignedInt', fragSizeStd)
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED0',           'unsignedInt', delay)
			if frl.enableStream1:
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED1',       'unsignedInt', fragSize)
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED1', 'unsignedInt', fragSizeStd)
				self.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED1',           'unsignedInt', delay)

	def downloadMeasurements(self, host, port, classname, instance, outputfile):
		url = 'http://%s:%d/urn:xdaq-application:class=%s,instance=%d/downloadMeasurements'
		url = url % (host, int(port), classname, int(instance))
		if self._dryRun: print 'curl -o', outputfile, url
		else: subprocess.check_call(['curl', '-o', outputfile, url])

	def setSize(self, fragSize, fragSizeStd=0, rate='max'):
		superFragSize = self._nStreams*int(fragSize) ## TODO: This has to change if eFEROLs are included
		print separator
		print "Setting fragment size to %5d bytes +- %-5d at %s rate" % (fragSize, fragSizeStd, str(rate))
		print separator

		## Set fragment size and delay for FEROLs:
		self.setSizeFEROLs(fragSize, fragSizeStd, rate)

		## Configure and enable pt::frl application on eFEROLs:
		for n,efrl in enumerate(self._eFEROLs):
			self.sendSimpleCmdToApp(efrl.host, efrl.port, 'pt::frl::Application', n, 'Configure')
		for n,efrl in enumerate(self._eFEROLs):
			self.sendSimpleCmdToApp(efrl.host, efrl.port, 'pt::frl::Application', n, 'Enable')
		self.sleep(2)

		## Set fragment size for eFEROLs
		for n,efrl in enumerate(self._eFEROLs):
			if options.useEVB: self.setParam(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'fedSize', 'unsignedInt', fragSize) ## EVB
			else:      self.setParam(efrl.host, efrl.port, 'Client', n, 'currentSize', 'unsignedLong', fragSize)


		## Set super-fragment size for BUs
		if not options.useEVB: ## EVB
			print separator
			for n,bu in enumerate(self._BUs):
				self.setParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'unsignedLong', superFragSize)
			for n,bu in enumerate(self._BUs):
				if not self._dryRun: print bu.name, 'dummyFedPayloadSize', self.getParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'xsd:unsignedLong')
			print separator

		self.sendCmdToFEROLs('Configure')
		print separator
		self.sleep(5)

		## Configure FED ids
		# How will this work with eFEROLs?
		print "Setting FED ids on FEROLs"
		fedid = 0
		for frl in self._FEROLs:
			if frl.enableStream0:
				self.writeItem(frl.host, frl.port, 'ferol::FerolController', 0, 'GEN_FED_SOURCE_BX_FED0', fedid)
				fedid += 1
			if frl.enableStream1:
				self.writeItem(frl.host, frl.port, 'ferol::FerolController', 0, 'GEN_FED_SOURCE_BX_FED1', fedid)
				fedid += 1


		print separator
		for n,efrl in enumerate(self._eFEROLs):
			self.sendSimpleCmdToApp(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'Configure')

		print separator
		self.sendCmdToEVMRUBU('Configure')
		print separator
		self.sendCmdToRUEVMBU('Enable') ## Have to enable RUs/EVM/BUs here?
		print separator

		## Enable eFEROL clients
		for n,efrl in enumerate(self._eFEROLs):
			if options.useEVB: self.sendSimpleCmdToApp(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'Enable')
			else:      self.sendSimpleCmdToApp(efrl.host, efrl.port, 'Client', n, 'start')

	def changeSize(self, fragSize, fragSizeStd=0, rate='max'):
		superFragSize = self._nStreams*fragSize ## TODO: This has to change if eFEROLs are included
		print separator
		print "Changing fragment size to %5d bytes +- %5d at %s rate" % (fragSize, fragSizeStd, str(rate))
		print separator

		## Pause FEROLs
		self.sendCmdToFEROLs('Pause')

		## Change fragment size and delay for FEROLs:
		self.setSizeFEROLs(fragSize, fragSizeStd, rate)

		# ## Halt input emulator
		# if len(self._eFEROLs)>0:
		# 	for n,ru in enumerate(self._RUs):
		# 		self.sendSimpleCmdToApp(ru.host, ru.port, 'gevb2g::InputEmulator', n, 'Halt')

		## Halt EVM/RUs/BUs
		self.sendCmdToEVMRUBU('Halt')

		self.sleep(2)

		# ## Change fragment size for eFEROLs
		# for n,efrl in enumerate(self._eFEROLs):
		# 	self.setParam(efrl.host, efrl.port, 'Client', n, 'currentSize', 'unsignedLong', fragSize)


		## Change super-fragment size for BUs
		for n,bu in enumerate(self._BUs):
			self.setParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'unsignedLong', superFragSize)
		for n,bu in enumerate(self._BUs):
			if not self._dryRun: print bu.name, 'dummyFedPayloadSize', self.getParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'xsd:unsignedLong')

		# ## Configure input emulator
		# if len(self._eFEROLs)>0:
		# 	for n,ru in enumerate(self._RUs):
		# 		self.sendSimpleCmdToApp(ru.host, ru.port, 'gevb2g::InputEmulator', n, 'Configure')



		self.sendCmdToEVMRUBU('Configure')
		self.sendCmdToRUEVMBU('Enable')
		self.sendCmdToFEROLs('SetupEVG')
		self.sendCmdToFEROLs('Resume')

		# ## Enable input emulator
		# if len(self._eFEROLs)>0:
		# 	for n,ru in enumerate(self._RUs):
		# 		self.sendSimpleCmdToApp(ru.host, ru.port, 'gevb2g::InputEmulator', n, 'Enable')


	## Untested
	def sendSOAPMsg(self, host, port, classname, instance, message):
		curlCmd  = "curl --stderr /dev/null -H \"Content-Type: text/xml\" -H \"Content-Description: SOAP Message\" -H \"SOAPAction: urn:xdaq-application:class=%s,instance=%d\" http://%s:%d -d \"%s\"" % (classname, instance, host, port, soapmsg)
		return subprocess.call(shlex.split(curlCmd))

	## Untested
	def sendSimpleCmdToAppNew(self, host, port, classname, instance, cmdName):
		"""Usage sendSimpleCmdToApp host port class instance cmdName"""

		soapbody = '<xdaq:%s xmlns:xdaq="urn:xdaq-soap:3.0"/>' % cmdName
		soapmsg  = self._SOAPEnvelope % soapbody

		self.sendSOAPMsg(host, port, classname, instance, soapmsg)

		## Need to add output handling
		# if($reply =~ m#<(\w+):${cmdName}Response\s[^>]*>(.*)</\1:${cmdName}Response>#) {
		#   my $returnValue = $2;
		#   print "$returnValue\n";
		# } elsif($reply =~ m#<\w+:${cmdName}Response\s[^>]*\>#) {
		#   print "EMPTY SOAP MESSAGE\n";
		# } else {
		#   print "ERROR\n";
		#   print "$reply\n";
		# }


	## Control methods
	def setup(self, configfile):
		"""Read config file, clean up and re-create run directory, fill config templates"""
		self.readXDAQConfigTemplate(configfile)
		self._runDir += self._testCase
		subprocess.check_call(['rm', '-rf', self._runDir])
		subprocess.check_call(['mkdir', '-p', self._runDir])

		print separator
		print 'Filling configuration template in ' + self._runDir + '/configuration.xml'
		filledconfig = self.fillTemplate(configfile)
		with open(self._runDir+'/configuration.xml', 'w') as file:
			file.write(filledconfig)

		print 'Producing configuration command file in ' + self._runDir + '/configure.cmd.xml'
		with open(self._runDir+'/configure.cmd.xml', 'w') as file:
			configureBody = '<xdaq:Configure xmlns:xdaq=\"urn:xdaq-soap:3.0\">\n\n\n' + filledconfig + '\n\n\n</xdaq:Configure>\n'
			configureCmd = self._SOAPEnvelope % configureBody
			file.write(configureCmd)
		print separator

	def start(self, fragSize):
		"""Start all XDAQ processes, set configuration for fragSize and start running"""
		print "Starting XDAQ processes"
		for h in self._hosts:
			self.sendCmdToLauncher(h.host, h.lport, 'STARTXDAQ'+str(h.port))
		print separator

		# self.webPingXDAQ()

		print "Configuring XDAQ processes"
		for h in self._hosts:
			self.sendCmdToExecutive(h.host, h.port, self._runDir+'/configure.cmd.xml')
		print separator

		self.sleep(2)
		self.setSize(fragSize)
		self.sleep(5)
		self.sendCmdToRUEVMBU('Enable')
		print separator
		self.sendCmdToFEROLs('Enable')
		print separator

	def getResults(self):
		"""Create output directory and download results for each BU, store them in server.csv"""
		from time import strftime
		outputdir = self._outputDir + self._testCase + '/'
		# outputdir = self._outputDir + strftime('%b%d_%Y') + '/' + self._testCase + '/'
		print outputdir
		subprocess.check_call(['mkdir', '-p', outputdir])

		if self._dryRun: return

		## Download output
		outputfiles = []
		for n,h in enumerate(self._BUs):
			outputfile = '%s/server%d.csv' % (outputdir, n)
			self.downloadMeasurements(h.host, h.port, self.namespace+'BU', n, outputfile)
			outputfiles.append(outputfile)

		## Concatenate output files
		with open(outputdir+'/server.csv', 'w') as outfile:
			for fname in outputfiles:
				with open(fname, 'r') as infile:
					outfile.write(infile.read())
					outfile.write('\n')
		print separator


	##### SIMPLE WRAPPERS:
	def sendSimpleCmdToApp(self, host, port, classname, instance, cmdName):
		if self._dryRun: print '%-18s %25s:%-5d %25s %1s\t%-12s' % ('sendSimpleCmdToApp', host, port, classname, instance, cmdName)
		else: return subprocess.check_call(['sendSimpleCmdToApp', host, str(port), classname, str(instance), cmdName])

	def sendCmdToLauncher(self, host, port, cmd):
		if self._dryRun: print '%-18s %25s:%-5d %-15s' % ('sendCmdToLauncher', host, port, cmd)
		else: return subprocess.check_call(['sendCmdToLauncher', host, str(port), cmd])

	def sendCmdToExecutive(self, host, port, cmdfile):
		if self._dryRun: print '%-18s %25s:%-5d %-35s' % ('sendCmdToExecutive', host, port, cmdfile)
		else: return subprocess.check_call(['sendCmdToExecutive', host, str(port), cmdfile])

	def sendCmdToApp(self, host, port, classname, instance, cmd):
		"""Sends a SOAP message contained in cmd to the application with classname and instance on host:port"""
		## Note that there are two versions of sendCmdToApp, the original taking a FILE as input, the new one taking directly the command string
		## I renamed the old one to be 'sendCmdFileToApp'
		if self._dryRun: print '%-18s %25s:%-5d %25s %1s:\n%s' % ('sendCmdToApp', host, port, classname, instance, cmd)
		else: return subprocess.check_call(['/nfshome0/stiegerb/cmsosrad/trunk/daq/benchmark/test/scripts/sendCmdToApp', host, str(port), classname, str(instance), cmd])
		# else: return subprocess.check_call(['sendCmdToApp', host, str(port), classname, str(instance), cmd])

	def sendCmdFileToApp(self, host, port, classname, instance, cmdFile):
		"""Sends a SOAP message contained in cmdFile to the application with classname and instance on host:port"""
		## This will call the old version of sendCmdToApp (see comment above)
		if self._dryRun: print '%-18s %25s:%-5d %25s %1s:\n%s' % ('sendCmdToApp', host, port, classname, instance, cmdFile)
		else: return subprocess.check_call(['sendCmdFileToApp', host, str(port), classname, str(instance), cmdFile])

	def setParam(self, host, port, classname, instance, paramName, paramType, paramValue):
		if self._dryRun: print '%-18s %25s:%-5d %25s %1s\t%-25s %12s %6s' % ('setParam', host, port, classname, instance, paramName, paramType, paramValue)
		else: return subprocess.check_call(['setParam', host, str(port), classname, str(instance), paramName, paramType, str(paramValue)])

	def getParam(self, host, port, classname, instance, paramName, paramType):
		if self._dryRun: print '%-18s %25s:%-5d %25s %1s\t%-25s %12s' % ('getParam', host, port, classname, instance, paramName, paramType)
		else:
			call = subprocess.Popen(['getParam', host, str(port), classname, str(instance), paramName, paramType], stdout=subprocess.PIPE)
			out,err = call.communicate()
			return out

	def writeItem(self, host, port, classname, instance, item, data, offset=0):
		body = '<xdaq:WriteItem xmlns:xdaq="urn:xdaq-soap:3.0" offset="%s"  item="%s" data="%s"/>' % (str(offset), item, str(data))
		cmd = self._SOAPEnvelope % body
		cmd = cmd.replace('\"','\\\"') ## need to escape the quotes when passing as argument
		return self.sendCmdToApp(host, port, classname, str(instance), cmd)

	# def tryWebPing(self, host, port):
	# 	if self._dryRun:
	# 		print '%-18s %25s:%-5d' % ('webPing', host, port)
	# 		return
	# 	cmd = "wget -o /dev/null -O /dev/null http://%s:%d/urn:xdaq-application:lid=3" % (host,int(port))
	# 	return subprocess.call(shlex.split(cmd))

	# def webPingXDAQ(self):
	# 	print "Checking availability of all hosts"
	# 	for host in self._allHosts:
	# 		print " ... checking %25s:%-5d" % (host.host, host.port)
	# 		if tryWebPing(host.host, host.port): continue

	# 		self.sendCmdToLauncher(host.host, host.lport, 'STOPXDAQ')
	# 	print separator

	# 	else: return subprocess.check_call(["webPingXDAQ"])


##########################################
## Interface:
def testBuilding(d2c, minevents=1000, verbose=0):
	if verbose>1: print separator
	if verbose>1: print 'Testing event building'
	eventCounter = []
	for n,bu in enumerate(d2c._BUs):
		if options.useEVB: nEvts = d2c.getParam(bu.host, bu.port, d2c.namespace+'BU', str(n), 'nbEventsBuilt', 'xsd:unsignedInt')
		else:              nEvts = d2c.getParam(bu.host, bu.port, d2c.namespace+'BU', str(n), 'eventCounter',  'xsd:unsignedLong')
		eventCounter.append(nEvts)
		if verbose>1: print bu.name, 'number of events built: ', nEvts
	print separator

	totEvents = 0
	for evtCount in eventCounter:
		if evtCount < minevents:
			if verbose>0: print 'Test failed, built less than %d events!' % minevents
			return -1
		else:
			totEvents += evtCount

	if verbose>0: print 'Test successful (built %d events), continuing...' % totEvents
	return totEvents

def runTest(configfile, fragSize, dryrun=False, symbolMap='', duration=10):
	"""Usage: runTest(configfile, fragSize)
Run a test reading the setup from configfile and using fragment size fragSize"""
	d2c = daq2Control(dryrun=dryrun, symbolMap=symbolMap)
	print separator
	d2c.setup(configfile)

	d2c.stopXDAQs()
	d2c.start(fragSize)

	print separator
	d2c.sleep(10)

	if testBuilding(d2c, verbose=1) < 1:
		d2c.stopXDAQs()
		exit(-1)

	print "Building events ..."
	d2c.sleep(duration)
	d2c.getResults()

	# raw_input("Press Enter to stop the XDAQs...")
	print separator
	d2c.stopXDAQs()

def getListOfSizes(maxSize, minSize=256):
	steps = [ n*minSize for n in xrange(1, 1000) if n*minSize <= 8192] ## multiples of minSize up to 8192
	if maxSize > 9000: steps += [9216, 10240, 11264, 12288, 13312, 14336, 15360, 16000]
	return steps

def runScan(configfile, nSteps, minSize, maxSize, dryrun=False, symbolMap='', duration=10):
	"""Usage: runScan(configfile, nSteps, minSize, maxSize)
Run a test reading the setup from configfile and using fragment size fragSize"""
	d2c = daq2Control(dryrun=dryrun, symbolMap=symbolMap)
	print separator
	d2c.setup(configfile)

	d2c.stopXDAQs()
	d2c.start(minSize)

	print separator
	d2c.sleep(10)

	if testBuilding(d2c, verbose=1) < 1:
		d2c.stopXDAQs()
		exit(-1)


	steps = getListOfSizes(nSteps, minSize, maxSize)
	for step in steps:
		d2c.changeSize(step)
		print "Building events at fragment size %d for %d seconds..." % (step, duration)
		d2c.sleep(duration)

	# d2c.changeSize(1024, fragSizeStd=1024) ## With a std dev for the lognormal generator (default is 0)
	# d2c.sleep(duration)
	#
	# d2c.changeSize(1024, rate=100)         ## With a limited rate in kHz (default is maximum rate)
	# d2c.sleep(duration)

	d2c.getResults()

	print separator
	d2c.stopXDAQs()


def test(configfile):
	d2c = daq2Control()
	d2c.readXDAQConfigTemplate(configfile)
	d2c.printHosts()


if __name__ == "__main__":
	from optparse import OptionParser
	usage = """ %prog [options] --runTest config.xml fragsize	"""

	parser = OptionParser(usage=usage)
	parser.add_option("--runTest", default=False,
	                  action="store_true", dest="runTest",
	                  help="Run a test setup, needs two arguments: config and fragment size")
	parser.add_option("--runScan", default=True,
	                  action="store_true", dest="runScan",
	                  help="Run a scan over fragment sizes, set the range using the options --maxSize and --minSize")
	parser.add_option("--useEVB", default=False,
	                  action="store_true", dest="useEVB",
	                  help="Set true to use EvB instead of gevb [default is gevb]")
	parser.add_option("-d", "--duration", default=30,
	                  action="store", type="int", dest="duration",
	                  help="Duration of a single step in seconds, [default: %default s]")
	parser.add_option("--maxSize", default=16000,
	                  action="store", type="int", dest="maxSize",
	                  help="Maximum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--minSize", default=256,
	                  action="store", type="int", dest="minSize",
	                  help="Minimum fragment size of a scan in bytes, [default: %default]")
	parser.add_option("--nSteps", default=100,
	                  action="store", type="int", dest="nSteps",
	                  help="Number of steps between minSize and maxSize, [default: %default]")

	parser.add_option("--test", default=False,
	                  action="store_true", dest="test",
	                  help="Just run the test method and quit (for debugging)")
	parser.add_option("--dry", default=False,
	                  action="store_true", dest="dry",
	                  help="Just print the commands without sending anything")

	parser.add_option("--kill", default=False,
	                  action="store_true", dest="kill",
	                  help="Stop all the XDAQ launchers and exit")
	parser.add_option("--start", default=False,
	                  action="store_true", dest="start",
	                  help="Start all the XDAQ launchers and exit")
	parser.add_option("--stop", default=False,
	                  action="store_true", dest="stop",
	                  help="Stop all the XDAQ processes and exit")
	parser.add_option("-m", "--symbolMap", default='',
	                  action="store", type="string", dest="symbolMap",
	                  help="Use a symbolmap different from the one set in the environment")
	(options, args) = parser.parse_args()


	# raw_input("Press Enter to stop the XDAQs...")

	if options.kill:
		d2c = daq2Control(symbolMap=options.symbolMap, dryrun=options.dry)
		d2c.stopXDAQs()
		d2c.stopXDAQLaunchers()
		exit(0)

	if options.stop:
		d2c = daq2Control(symbolMap=options.symbolMap, dryrun=options.dry)
		d2c.stopXDAQs()
		exit(0)

	if options.start:
		with open('launcherLog.txt', 'w') as logfile:
			d2c = daq2Control(symbolMap=options.symbolMap, dryrun=options.dry)
			d2c.startXDAQLaunchers(logfile)
		exit(0)

	if options.test:
		test(args[0])
		exit(0)

	if options.runTest and len(args) > 1:
		runTest(args[0], int(args[1]), dryrun=options.dry, symbolMap=options.symbolMap, duration=options.duration)
		exit(0)

	if options.runScan and len(args) > 3:
		runScan(args[0], options.nSteps, options.minSize, options.maxSize, dryrun=options.dry, symbolMap=options.symbolMap, duration=options.duration)
		exit(0)

	parser.print_help()
	exit(-1)

