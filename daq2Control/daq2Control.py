#! /usr/bin/env python
######################################################################
#  For now we assume that we either run with FEROLs or eFEROLs,      #
#  never with both!                                                  #
#                                                                    #
#  ToDo-List:                                                        #
#   - Event_Delay_ns in FEROL when running with GTPe?                #
#   - Automatize the number of samples, depending on duration        #
#   - Add option to use dummyFerol                                   #
#   - Testing testing testing                                        #
######################################################################

import subprocess
import re, os, shlex
import time
import itertools
from sys import stdout
from multiprocessing import Pool

separator = 70*'-'

from daq2Config import daq2Config, host, FEROL
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import printError, printWarningWithWait, sleep
from logNormalTest import averageFractionSize
import daq2Utils as utils

import xml.etree.ElementTree as ET

######################################################################
class daq2Control(object):
	'''
---------------------------------------------------------------------
  class daq2Control

 - Takes a daq2Config and a daq2SymbolMap to setup
 - Sets up and starts a FRL/eFRL x RU x BU system
---------------------------------------------------------------------
'''
	def __init__(self, configFile, options):
		## Read environment variables
		try:
			self._testDir   = os.environ['RUB_TESTER_HOME']
			self._platform  = os.environ['XDAQ_PLATFORM']
			self._user      = os.environ['USER']
			self._testType  = os.environ['TEST_TYPE']
		except KeyError as e:
			printError('Environment missing, did you forget to source '
				       'setenv-COL.sh? Aborting.', self)
			raise e

		self.options = options
		if len(options.symbolMap)>0:
			self.symbolMap = daq2SymbolMap(options.symbolMap)
		else:
			self.symbolMap = daq2SymbolMap() ## take it from the environment

		self.setupConfig(configFile)

		self.__RETRY_COUNTER = 0
		if not hasattr(self.options, 'retries'):
			self.options.retries = 5

		if self.config.useGTPe and self.options.useRate == 'max':
			printWarningWithWait("Failed to specify rate for GTPe. Setting "
				                 "it to 100 kHz.", waittime=0, instance=self)
			self.options.useRate = 100

		self._runDir  = self._testDir + '/' + self._platform + '/'
		if len(self._testType)>0: self._runDir += (self._testType + '/')
		self._runDir += (time.strftime('%d%H%M%S') + '/')

		if self.options.outputDir:
			if self.options.outputDir.endswith('/'):
				self.options.outputDir = self.options.outputDir[:-1]
			if self.options.outputTag:
				self._outputDir = (self.options.outputDir+'_'+
					               self.options.outputTag)
			else:
				self._outputDir = self.options.outputDir
		else:
			self._outputDir = self._testDir + '/data/'

		self._testEnv   = ""
		if len(self._testType) > 0: self._testEnv = "-"+self._testType

	def reset(self):
		"""Reset counters."""
		self.__RETRY_COUNTER = 0
	def setupConfig(self, configFile):
		try:
			self.config = daq2Config(configFile)
			self.splitConfig = False
		except IOError: ## TODO fix this
			self.configDir = configFile
			configFile = os.path.join(configFile, 'full.xml')
			self.config = daq2Config(configFile)
			self.splitConfig = True

		self.config.fillFromSymbolMap(self.symbolMap)
		if self.options.enablePauseFrame:
			self.config.setFerolParameter('ENA_PAUSE_FRAME', 'true')
		if self.options.disablePauseFrame:
			self.config.setFerolParameter('ENA_PAUSE_FRAME', 'false')
		if self.options.setCWND > 0:
			self.config.setFerolParameter('TCP_CWND_FED0',
				                          self.options.setCWND)
			self.config.setFerolParameter('TCP_CWND_FED1',
				                          self.options.setCWND)
		if self.options.verbose>1: self.config.printHosts()
	def fillConfig(self, filename):
		basename = os.path.split(filename)[1]
		runconfig = os.path.join(self._runDir,basename)
		if self.options.verbose > 5:
			print 'Filling configuration template in ' + runconfig
		if not self.options.dry:
			## write out the parsed xml to a file (still templated)
			parsedconfig = ET.parse(filename)
			parsedconfig.write(runconfig)
			## fill the template with actual hosts and port numbers
			filledconfig = self.symbolMap.fillTemplate(runconfig)
			with open(runconfig, 'w') as configfile:
				configfile.write(filledconfig)

		## Produce configure command file
		cfg_cmd_file = '%s/%s.configure.cmd.xml' % (self._runDir, basename)
		if self.options.verbose > 5:
			print 'Producing configuration command file in', cfg_cmd_file
		if not self.options.dry:
			with open(cfg_cmd_file, 'w') as file:
				configureBody =  '<xdaq:Configure xmlns:xdaq=\"'
				configureBody += 'urn:xdaq-soap:3.0\">\n\n\n'
				configureBody += filledconfig
				configureBody += '\n\n\n</xdaq:Configure>\n'
				configureCmd = utils.SOAPEnvelope % configureBody
				file.write(configureCmd)

	## Multi-commands
	def sendCmdToEVMRUBU(self, cmd): ## ordering for configure
		if self.options.verbose > 0: print separator
		for n,evm in enumerate(self.config.EVM):
			utils.sendSimpleCmdToApp(evm, self.config.namespace+'EVM',
				                     cmd, verbose=self.options.verbose,
				                     dry=self.options.dry)
		for n,ru in enumerate(self.config.RUs):
			classname = 'RU'
			if self.config.useEvB and n==0: classname = 'EVM'
			utils.sendSimpleCmdToApp(ru, self.config.namespace+classname,
				                     cmd, verbose=self.options.verbose,
				                     dry=self.options.dry)
		for n,bu in enumerate(self.config.BUs):
			utils.sendSimpleCmdToApp(bu, self.config.namespace+'BU',
				                     cmd, verbose=self.options.verbose,
				                     dry=self.options.dry)
	def sendCmdToRUEVMBU(self, cmd): ## ordering for enable
		if self.options.verbose > 0: print separator
		for n,ru in enumerate(self.config.RUs):
			classname = 'RU'
			if self.config.useEvB and n==0: classname = 'EVM'
			utils.sendSimpleCmdToApp(ru, self.config.namespace+classname,
				                     cmd, verbose=self.options.verbose,
				                     dry=self.options.dry)
		for n,evm in enumerate(self.config.EVM):
			utils.sendSimpleCmdToApp(evm, self.config.namespace+'EVM',
				                     cmd, verbose=self.options.verbose,
				                     dry=self.options.dry)
		for n,bu in enumerate(self.config.BUs):
			utils.sendSimpleCmdToApp(bu, self.config.namespace+'BU',
				                     cmd, verbose=self.options.verbose,
				                     dry=self.options.dry)
	def sendCmdToBUEVMRU(self, cmd): ## ordering for enable
		if self.options.verbose > 0: print separator
		for n,bu in enumerate(self.config.BUs):
			utils.sendSimpleCmdToApp(bu, self.config.namespace+'BU',
				                     cmd, verbose=self.options.verbose,
				                     dry=self.options.dry)
		for n,evm in enumerate(self.config.EVM):
			utils.sendSimpleCmdToApp(evm, self.config.namespace+'EVM',
				                     cmd, verbose=self.options.verbose,
				                     dry=self.options.dry)
		sleep(2, self.options.verbose, self.options.dry)
		for n,ru in enumerate(self.config.RUs):
			classname = 'RU'
			if self.config.useEvB and n==0: classname = 'EVM'
			utils.sendSimpleCmdToApp(ru, self.config.namespace+classname,
				                     cmd, verbose=self.options.verbose,
				                     dry=self.options.dry)
	def sendCmdToFEROLs(self, cmd):
		if self.options.verbose > 0: print separator
		for frl in self.config.FEROLs:
			utils.sendSimpleCmdToApp(frl, 'ferol::FerolController', cmd,
				                     verbose=self.options.verbose,
				                     dry=self.options.dry)
	def sendCmdToEFEDs(self, cmd):
		if self.options.verbose > 0: print separator
		for efed in self.config.eFEDs:
			for instance,_,_ in efed.streams:
				utils.sendSimpleCmdToApp(efed, 'd2s::FEDEmulator', cmd,
					                     instance=instance, port=efed.port,
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)
	def sendCmdToGTPeFMM(self, cmd, invert=False):
		try:
			gtpe = self.symbolMap('GTPE0')
			fmm  = self.symbolMap('FMM0')
			if not invert:
				utils.sendSimpleCmdToApp(gtpe, 'd2s::GTPeController',
					                     str(cmd),
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)
				utils.sendSimpleCmdToApp(fmm, 'tts::FMMController',
					                     str(cmd),
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)
				return
			else:
				utils.sendSimpleCmdToApp(fmm, 'tts::FMMController',
					                     str(cmd),
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)
				utils.sendSimpleCmdToApp(gtpe, 'd2s::GTPeController',
					                     str(cmd),
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)
				return
		except KeyError as e:
			if not self.config.useGTPe:
				printError("You're trying to send a command to a "
					       "non-existing GTPe...", self)
				raise RuntimeError('Addressing GTPe in non-GTPe running '
					               'mode')
			raise e
	def sendCmdToFMM(self, cmd):
		try:
			fmm = self.symbolMap('FMM0')
			utils.sendSimpleCmdToApp(fmm, 'tts::FMMController', cmd,
				                     verbose=self.options.verbose,
				                     dry=self.options.dry)
		except KeyError as e:
			printWarningWithWait('No FMM found in symbol map, aborting.',
				                 waittime=0, instance=self)
			raise e
	def sendCmdToGTPe(self, cmd):
		try:
			gtpe = self.symbolMap('GTPE0')
			utils.sendSimpleCmdToApp(gtpe, 'd2s::GTPeController', cmd,
				                     verbose=self.options.verbose,
				                     dry=self.options.dry)
		except KeyError as e:
			printWarningWithWait('No GTPe found in symbol map, aborting.',
				                 waittime=0, instance=self)
			pass

	def setSizeFEROLs(self, fragSize, fragSizeRMS, rate='max'):
		if self.options.verbose > 0: print separator

		## Flat profile (i.e. each stream has the same size)
		if self.options.sizeProfile == 'flat':
			delay = utils.getFerolDelay(fragSize, rate)

			## Max rate when running with GTPe?
			if self.config.useGTPe: delay = 20

			for frl in self.config.FEROLs:

				##### BUG HERE???? frl is ru sometimes?

				print frl
				if self.config.useEvB and frl.index == 0:
					## this sends to the EVM
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_bytes_FED0',
						           'unsignedInt', 1024,
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_Stdev_bytes_FED0',
						           'unsignedInt', 0,
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Delay_ns_FED0',
						           'unsignedInt', int(delay),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					continue

				if frl.enableStream0:
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_bytes_FED0',
						           'unsignedInt', int(fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_Stdev_bytes_FED0',
						           'unsignedInt', int(fragSizeRMS),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Delay_ns_FED0',
						           'unsignedInt', int(delay),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
				if frl.enableStream1:
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_bytes_FED1',
						           'unsignedInt', int(fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_Stdev_bytes_FED1',
						           'unsignedInt', int(fragSizeRMS),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Delay_ns_FED1',
						           'unsignedInt', int(delay),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
		else:
			if not self.options.profilePerFRL:
				## same size for both streams of each FEROL!
				sizeProfile = utils.getSizeProfile(fragSize,
					                               len(self.config.FEROLs),
					                               self.options.sizeProfile)
				delayProfile = [utils.getFerolDelay(size, rate)
				                                  for size in sizeProfile]
				relRMS = fragSizeRMS/fragSize

				## Max rate when running with GTPe?
				if self.config.useGTPe:
					delayProfile = len(self.config.FEROLs)*[20]

				for fragSize,delay,frl in itertools.izip(sizeProfile,
					                                     delayProfile,
					                                     self.config.FEROLs):
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_bytes_FED0',
						           'unsignedInt', int(fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_Stdev_bytes_FED0',
						           'unsignedInt', int(relRMS*fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Delay_ns_FED0',
						           'unsignedInt', int(delay),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_bytes_FED1',
						           'unsignedInt', int(fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Length_Stdev_bytes_FED1',
						           'unsignedInt', int(relRMS*fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(frl, 'ferol::FerolController',
						           'Event_Delay_ns_FED1',
						           'unsignedInt', int(delay),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
			else: ## profile applied to the two FEROL streams
				sizeProfile = utils.getSizeProfile(fragSize, 2,
					                               self.options.sizeProfile)
				delayProfile = [utils.getFerolDelay(size, rate)
				                             for size in sizeProfile]
				relRMS = fragSizeRMS/fragSize

				## Max rate when running with GTPe?
				if self.config.useGTPe: delayProfile = 2*[20]

				for frl in self.config.FEROLs:
					if frl.enableStream0:
						utils.setParam(frl,  'ferol::FerolController',
							           'Event_Length_bytes_FED0',
							           'unsignedInt', int(sizeProfile[0]),
							           verbose=self.options.verbose,
							           dry=self.options.dry)
						utils.setParam(frl,  'ferol::FerolController',
							           'Event_Length_Stdev_bytes_FED0',
							           'unsignedInt',
							           int(relRMS*sizeProfile[0]),
							           verbose=self.options.verbose,
							           dry=self.options.dry)
						utils.setParam(frl,  'ferol::FerolController',
							           'Event_Delay_ns_FED0',
							           'unsignedInt', int(delayProfile[0]),
							           verbose=self.options.verbose,
							           dry=self.options.dry)
					if frl.enableStream1:
						utils.setParam(frl,  'ferol::FerolController',
							           'Event_Length_bytes_FED1',
							           'unsignedInt', int(sizeProfile[1]),
							           verbose=self.options.verbose,
							           dry=self.options.dry)
						utils.setParam(frl,  'ferol::FerolController',
							           'Event_Length_Stdev_bytes_FED1',
							           'unsignedInt',
							           int(relRMS*sizeProfile[1]),
							           verbose=self.options.verbose,
							           dry=self.options.dry)
						utils.setParam(frl,  'ferol::FerolController',
							           'Event_Delay_ns_FED1',
							           'unsignedInt', int(delayProfile[0]),
							           verbose=self.options.verbose,
							           dry=self.options.dry)
	def setSizeEFEDs(self, fragSize, fragSizeRMS):
		if self.options.verbose > 0: print separator

		## Flat profile (i.e. each stream has the same size)
		if self.options.sizeProfile == 'flat':
			for efed in self.config.eFEDs:
				## loop on eFED machines
				for instance,fedid,_ in efed.streams:
					## loop on applications for each eFED
					utils.setParam(efed, 'd2s::FEDEmulator',
						           'eventSize',
						           'unsignedInt', int(fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(efed, 'd2s::FEDEmulator',
						           'eventSizeStdDev',
						           'unsignedInt', int(fragSizeRMS),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
		else: ## UNTESTED
			raise RuntimeError('not implemented yet!')
			sizeProfile = utils.getSizeProfile(fragSize,
				                               len(self.config.nStreams),
				                               self.options.sizeProfile)
			relRMS = fragSizeRMS/fragSize

			for fragSize,efed in zip(sizeProfile, self.config.eFEDs):
				utils.setParam(efed, 'd2s::FEDEmulator',
					           'eventSize', 'unsignedInt',
					           int(fragSize),
					           verbose=self.options.verbose,
					           dry=self.options.dry)
				utils.setParam(efed, 'd2s::FEDEmulator',
					           'eventSizeStdDev', 'unsignedInt',
					           int(relRMS*fragSize),
					           verbose=self.options.verbose,
					           dry=self.options.dry)

	def setRunNumber(self, number=0):
		## Set Runnumber here:
		if number==0:
			number = time.strftime('%d%H%M')
			if number[0] == '0': number = number[1:]

		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Setting run number", number
		if self.options.verbose > 0: print separator
		self.runNumber = number

		## gevb2g doesn't know about runnumbers
		if not self.config.useEvB: return

		for n,h in enumerate(self.config.FMM):
			utils.setParam(h, 'tts::FMMController',
				           'runNumber', 'unsignedInt', number,
				           verbose=self.options.verbose,
				           dry=self.options.dry)
		for n,h in enumerate(self.config.RUs):
			classname = 'RU' if not self.config.useEvB or n>0 else 'EVM'
			utils.setParam(h, self.config.namespace+classname,
				           'runNumber', 'unsignedInt', number,
				           verbose=self.options.verbose,
				           dry=self.options.dry)
		for n,h in enumerate(self.config.EVM):
			utils.setParam(h, self.config.namespace+'EVM',
				           'runNumber', 'unsignedInt', number,
				           verbose=self.options.verbose,
				           dry=self.options.dry)
		for n,h in enumerate(self.config.BUs):
			utils.setParam(h, self.config.namespace+'BU',
				           'runNumber', 'unsignedInt', number,
				           verbose=self.options.verbose,
				           dry=self.options.dry)
	def setCurrentSize(self, size, rms, rate):
		self.currentFragSize    = size
		self.currentFragSizeRMS = rms
		self.currentRate        = rate
		try:
			## TODO: Get these from the config
			self.currentCorrFragSize = averageFractionSize(size, rms,
				                                           24, 65000)
		except ZeroDivisionError:
			self.currentCorrFragSize = size

	## Control methods
	def setup(self):
		"""
		Clean up and re-create run directory, fill config templates,
		create output directory
		"""
		if self.options.verbose > 0: print separator

		if self.options.relRMS and not self.options.useLogNormal:
			printWarningWithWait("  Non-zero rms value, but not "
				                 "--useLogNormal!\n"
				                 "  Most likely something went wrong "
				                 "somewhere.")

		## Cleanup run dir
		if not self.options.dry:
			subprocess.check_call(['rm', '-rf', self._runDir])
			subprocess.check_call(['mkdir', '-p', self._runDir])

		## Clean up and create output dir
		self.prepareOutputDir()

		## Fill configuration template(s)
		if not self.splitConfig:
			runconfig = self._runDir + '/configuration.xml'
			if self.options.verbose > 0:
				print 'Filling configuration template in ' + runconfig
			if not self.options.dry:
				## write out the parsed xml to a file (still templated)
				self.config.writeConfig(runconfig)
				## fill the template with actual hosts and port numbers
				filledconfig = self.symbolMap.fillTemplate(runconfig)
				with open(runconfig, 'w') as configfile:
					configfile.write(filledconfig)

			## Produce configure command file
			if self.options.verbose > 0:
				print ('Producing configuration command file in ' +
					    self._runDir + '/configure.cmd.xml')
			if not self.options.dry:
				with open(self._runDir+'/configure.cmd.xml', 'w') as file:
					configureBody =  '<xdaq:Configure xmlns:xdaq=\"'
					configureBody += 'urn:xdaq-soap:3.0\">\n\n\n'
					configureBody += filledconfig
					configureBody += '\n\n\n</xdaq:Configure>\n'
					configureCmd = utils.SOAPEnvelope % configureBody
					file.write(configureCmd)
		else:
			print 'Producing configuration command files in',self._runDir
			filenames = os.listdir(self.configDir)
			for n,filename in enumerate(filenames):
				utils.printProgress(n, len(filenames))
				if not os.path.splitext(filename)[1] == '.xml':
					continue
				self.fillConfig(os.path.join(self.configDir,filename))
		if self.config.useInputEmulator and self.config.useEvB:
			self.dropBUCaches()
			sleep(5, self.options.verbose, self.options.dry)
	def start(self, fragSize, fragSizeRMS=0, rate='max', onlyPrepare=False):
		"""
		Start all XDAQ processes, set configuration for fragSize and start
		running onlyPrepare=True will stop before configuring and enabling
		"""
		self.setCurrentSize(fragSize, fragSizeRMS, rate)

		## Start the xdaq processes from the launchers
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Starting XDAQ processes"
		for h in self.config.hosts:
			if (self.options.maskHost is not None and
				self.options.maskHost in h.host):
				printWarningWithWait("Skipping %s" % h.host,
					                  waittime=1, instance=self)
				continue
			utils.sendCmdToLauncher(h.host, h.lport, 'STARTXDAQ'+str(h.port),
				                    verbose=self.options.verbose,
				                    dry=self.options.dry)
		sleep(2, self.options.verbose, self.options.dry)

		## Check availability of xdaq processes on relevant hosts
		if not self.webPingXDAQ():
			## Check again, maybe it needs more time to start?
			if self.options.verbose > 0:
				print separator
				print 'Waiting 5 seconds and checking again...'
			sleep(5, self.options.verbose, self.options.dry)
			if not self.webPingXDAQ():
				self.retry('Not all hosts ready!')
				return

		## Send the configuration file to each host
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Configuring XDAQ processes"

		configfilelist = []
		for host in self.config.hosts:
			filename = '%s/%s%d.xml.configure.cmd.xml'%(self._runDir,
				                                            host.type,
				                                            host.index)
			configfilelist.append(filename)

		if not self.splitConfig:
			if not utils.sendToHostListInParallel(
				          self.config.hosts,
	                      utils.sendCmdFileToExecutivePacked,
				          (self._runDir+'/configure.cmd.xml',
				           self.options.verbose, self.options.dry)):
				self.retry("Failed to send command file to all hosts")
				return
		else:
			if not utils.sendToHostListInParallel(
				          self.config.hosts,
	                      utils.sendCmdFileToExecutivePacked,
	                      configfilelist,
				          (self.options.verbose, self.options.dry)):
				self.retry("Failed to send command file to all hosts")
				return
		sleep(2, self.options.verbose, self.options.dry)

		## Set the fragment size, rms, and rate
		self.setSize(fragSize, fragSizeRMS, rate=rate)
		sleep(2, self.options.verbose, self.options.dry)

		if onlyPrepare: return

		## Configure and enable:
		self.configure()
		self.enable()

	def stop(self):
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Stopping"

		## Pause GTPe
		if self.config.useGTPe:
			self.sendCmdToGTPe('Pause')
			sleep(2, self.options.verbose, self.options.dry)

		## Stop EVM, RUs, BUs, eFEDs, FEROLs, FMM, and GTPe
		self.sendCmdToEVMRUBU('Stop')
		self.sendCmdToEFEDs(  'Stop')
		self.sendCmdToFEROLs( 'Stop')
		if self.config.useGTPe:
			self.sendCmdToGTPe('Stop')
		sleep(3, self.options.verbose, self.options.dry)
		self.checkStopped()
		return
	def checkStopped(self):
		if self.options.verbose > 0: print separator
		## Check everything is 'Configured' or 'Ready'
		to_be_checked = [
		        (self.config.RUs[1:] + self.config.FEROLs, 'Configured'),
		        ([self.config.RUs[0]] + self.config.BUs + self.config.EVM +
		          self.config.eFEDs + self.config.GTPe, 'Ready')]
		if not self.config.useEvB:
			to_be_checked = [
			    (self.config.RUs + self.config.FEROLs, 'Configured'),
			    (self.config.BUs + self.config.EVM +
			     self.config.eFEDs + self.config.GTPe, 'Ready')]

		for hostlist, state in to_be_checked:
			if utils.checkStates(hostlist, state,
				                 verbose=self.options.verbose,
				                 dry=self.options.dry): continue
			printWarningWithWait("Failed to reach 'Configured' state.",
				                 waittime=0, instance=self)
			return False
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print 'STOPPED'
		if self.options.verbose > 0: print separator
		return True

	def configure(self):
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Configuring"

		## In case of EvB/gevb2g InputEmulator:
		if self.config.useInputEmulator:
			# Configure gevb2g InputEmulator application
			if not self.config.useEvB:
				for n,ru in enumerate(self.config.RUs):
					utils.sendSimpleCmdToApp(ru, 'gevb2g::InputEmulator',
						                     'Configure',
						                     verbose=self.options.verbose,
						                     dry=self.options.dry)
				sleep(2, self.options.verbose, self.options.dry)
			self.sendCmdToEVMRUBU('Configure')

			if self.config.useEvB:
				utils.sendSimpleCmdToApp(
					         self.config.RUs[0],
		                     'pt::ibv::Application',
		                     'connect',
		                     verbose=self.options.verbose,
		                     dry=self.options.dry)
				sleep(5, self.options.verbose, self.options.dry)

			return

		## In case of mstreamio configurations:
		if self.config.useMSIO:
			if self.config.useIBV: ## Only do this for ibv!
				pool = Pool(min(16,len(self.config.RUs)))

				tasklist = [(ru.host, ru.port, 'pt::ibv::Application', 0,
					         'connect',
					         self.options.verbose,
					         self.options.dry) for ru in self.config.RUs]
				pool.map(utils.sendSimpleCmdToAppPacked, tasklist)
			sleep(2, self.options.verbose, self.options.dry)
			return

		## In case of eFED:
		if len(self.config.eFEDs) > 0:
			self.sendCmdToGTPeFMM('Configure', invert=False)
			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToEFEDs('Configure')
			self.sendCmdToFEROLs('Configure')
			sleep(10, self.options.verbose, self.options.dry)
			if not self.checkConfigured():
				printWarningWithWait("Not everything configured. Waiting "
					                 "another 10s and checking again.",
					                 waittime=10, instance=self)
				if not self.checkConfigured():
					self.retry('Failed to configure.')
					return

			if self.config.useIBV: ## Only do this for ibv!
				for h in self.config.RUs:
					print "Sending init to", h.name
					utils.sendSimpleCmdToApp(h, "pt::ibv::Application",
						                     'connect',
						                     verbose=self.options.verbose,
						                     dry=self.options.dry)
				sleep(2, self.options.verbose, self.options.dry)
			return

		## In case of FEROLs:
		if len(self.config.FEROLs) > 0:
			self.sendCmdToFEROLs('Configure')
			self.sendCmdToEVMRUBU('Configure')

			## Configure GTPe and FMM:
			if self.config.useGTPe:
				self.sendCmdToGTPeFMM('Configure', invert=False)

			sleep(10, self.options.verbose, self.options.dry)
			if not self.checkConfigured():
				printWarningWithWait("Not everything configured. Waiting "
					                 "another 10s and checking again.",
					                 waittime=10, instance=self)
				if not self.checkConfigured():
					self.retry('Failed to configure.')
					return

			if self.config.useIBV: ## Only do this for ibv!
				for h in self.config.RUs:
					print "Sending init to", h.name
					utils.sendSimpleCmdToApp(h, "pt::ibv::Application",
						                     'connect',
						                     verbose=self.options.verbose,
						                     dry=self.options.dry)
				sleep(2, self.options.verbose, self.options.dry)
			return

		printWarningWithWait("daq2Control::Configure ==> Doing nothing.",
			                 waittime=1, instance=self)
		return
	def checkConfigured(self):
		if self.options.verbose > 0: print separator
		## Check everything is 'Configured' or 'Ready'
		to_be_checked = [(self.config.FEROLs, 'Configured'),
		                 (self.config.RUs + self.config.BUs +
		                  self.config.EVM + self.config.eFEDs +
		                  self.config.FMM + self.config.GTPe, 'Ready')]
		if not self.config.useEvB:
			to_be_checked = [(self.config.FEROLs, 'Configured')]

		configured = True
		for hostlist, state in to_be_checked:
			if utils.checkStates(hostlist, state,
				                 verbose=self.options.verbose,
				                 dry=self.options.dry): continue
			printWarningWithWait('Configure failed for some machines.',
				                  waittime=0, instance=self)
			configured = False
		if configured:
			if self.options.verbose > 0: print separator
			if self.options.verbose > 0: print 'CONFIGURED'
			if self.options.verbose > 0: print separator
			return True
		return False
	def enable(self):
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Enabling"

		## Set Runnumber:
		self.setRunNumber()

		## In case of eFEDs or FEROLs:
		if len(self.config.eFEDs) > 0 or len(self.config.FEROLs) > 0:
			self.sendCmdToRUEVMBU('Enable')

			## Enable FEROLs
			self.sendCmdToFEROLs('Enable')
			sleep(10, self.options.verbose, self.options.dry)

			## Enable FMM:
			if self.config.useGTPe:
				fmm = self.symbolMap('FMM0')
				utils.sendSimpleCmdToApp(fmm, 'tts::FMMController',
					                     'Enable',
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)

			self.sendCmdToEFEDs('Enable')

			if not self.checkEnabled():
				if self.options.verbose > 0: print "Waiting a bit longer..."
				sleep(10, self.options.verbose, self.options.dry)
				if not self.checkEnabled():
					self.retry('Failed to enable all FEROLs and RUs.')
					return

			## Enable GTPe:
			if self.config.useGTPe:
				gtpe = self.symbolMap('GTPE0')
				utils.sendSimpleCmdToApp(gtpe, 'd2s::GTPeController',
					                     'Enable',
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)

			sleep(2, self.options.verbose, self.options.dry)
			return

		## In case of mstreamio configurations:
		if self.config.useMSIO:
			if self.options.verbose > 0: print separator
			for n,bu in enumerate(self.config.BUs):
				utils.sendSimpleCmdToApp(bu, 'Server', 'start',
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)
			for n,ru in enumerate(self.config.RUs):
				utils.sendSimpleCmdToApp(ru, 'Client', 'start',
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)
			return

		## In case of EvB/gevb2g InputEmulator:
		if self.config.useInputEmulator:
			if self.config.useEvB:
				self.sendCmdToBUEVMRU('Enable')
			else:
				self.sendCmdToRUEVMBU('Enable')
			sleep(2, self.options.verbose, self.options.dry)

			# Enable InputEmulator application in Gevb2g case
			if not self.config.useEvB:
				for n,ru in enumerate(self.config.RUs):
					utils.sendSimpleCmdToApp(ru, 'gevb2g::InputEmulator',
						                     'Enable',
						                     verbose=self.options.verbose,
						                     dry=self.options.dry)
				sleep(2, self.options.verbose, self.options.dry)
			return

		printWarningWithWait("daq2Control::Enable ==> Doing nothing.",
			                 waittime=1, instance=self)
		return
	def checkEnabled(self):
		if self.options.verbose > 0: print separator

		## Check Status of FEROLs and EVM/RUs:
		if self.config.useEvB:
			hosts_to_check =  self.config.FEROLs[:]
			hosts_to_check += self.config.RUs
			hosts_to_check += self.config.BUs
			if not utils.checkStates(hosts_to_check, 'Enabled',
				                     verbose=self.options.verbose,
				                     dry=self.options.dry):
				return False
		if not self.config.useEvB:
			if not utils.checkStates(self.config.FEROLs, 'Enabled',
				                     verbose=self.options.verbose,
				                     dry=self.options.dry):
				return False

		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print 'ENABLED'
		if self.options.verbose > 0: print separator
		return True
	def retry(self, message):
		if self.__RETRY_COUNTER < self.options.retries:
			print " -- retry %d of %d" % (self.__RETRY_COUNTER+1,
				                          self.options.retries)
			self.__RETRY_COUNTER += 1
			printWarningWithWait(message+' ... retrying',
				                 waittime=0,
				                 instance=self)
			utils.stopXDAQs(self.symbolMap,
				            verbose=self.options.verbose,
				            dry=self.options.dry)
			sleep(10, self.options.verbose, self.options.dry)
			self.start(fragSize=self.currentFragSize,
				       fragSizeRMS=self.currentFragSizeRMS,
				       rate=self.currentRate)
		else:
			printError(message, instance=self)
			raise RuntimeError(message)

	def prepareOutputDir(self):
		import glob
		if not self.options.outputDir:
			self._outputDir += self.config.testCase
			if self.config.useMSIO:
				self._outputDir += '_MSIO'
			if self.config.useInputEmulator:
				if self.config.useEvB:
					self._outputDir += '_gevbIE'
				else:
					self._outputDir += '_EvBIE'
			if self.options.useLogNormal:
				self._outputDir += '_RMS_%3.1f' % float(self.options.relRMS)
			if self.options.outputTag:
				self._outputDir += '_'+self.options.outputTag
		if not self._outputDir.endswith('/'): self._outputDir += '/'
		if self.options.verbose > 0:
			print separator
			print 'Storing output in:', self._outputDir
		if self.options.dry: return

		## Create output directory
		try:
			os.makedirs(self._outputDir)
		except OSError: ## dir exists, save previous measurements:
			newdir =  self._outputDir
			newdir += 'previous/'
			newdir += time.strftime('%b%d-%H%M%S')
			os.makedirs(newdir)
			if len(glob.glob(self._outputDir+'*.csv')) > 0:
				subprocess.check_call(['mv'] +
					                  glob.glob(self._outputDir+'*.csv') +
					                  [newdir])
			if os.path.exists(self._outputDir+'infospaces'):
				subprocess.check_call(['mv', self._outputDir+'infospaces',
					                   newdir])

		if self.options.storeInfoSpaces:
			try:
				os.makedirs(self._outputDir + "infospaces")
			except OSError: pass ## dir exists already


		## Prepare output file:
		with open(self._outputDir+'/server.csv', 'a') as outfile:
			outfile.write('## Testcase: %s\n' % self.config.testCase)
			if self.options.useLogNormal:
				outfile.write('## useLogNormal = True, RMS = %5.2f\n' %
					           float(self.options.relRMS) )
			outfile.write('## %s\n' %
				               time.strftime('%a %b %d, %Y / %H:%M:%S'))
			hashtag = utils.getGitHashTag()
			outfile.write('## Git Hashtag: %s (%s)\n' %
				               (hashtag[:7], hashtag))
			outfile.write('\n##\n')
			self.config.printHosts(out=outfile, prepend='## ')
			outfile.write('\n\n')
			outfile.close()

	def setSize(self, fragSize, fragSizeRMS=0, rate='max'):
		if self.options.verbose > 0:
			print separator
			print ("Setting fragment size to %5d bytes +- %-5d at %s "
				   "kHz rate" % (fragSize, fragSizeRMS, str(rate)))
		self.setCurrentSize(fragSize, fragSizeRMS, rate)

		## In case of eFED:
		if len(self.config.eFEDs) > 0:
			## Set fragment size and delay for eFEDs:
			self.setSizeEFEDs(fragSize, fragSizeRMS)

			## Set trigger rate at GTPe
			try:
				gtpe = self.symbolMap('GTPE0')
				utils.setParam(gtpe, 'd2s::GTPeController',
					           'triggerRate', 'double',
					           str(float(rate)*1000),
					           verbose=self.options.verbose,
					           dry=self.options.dry)
			except KeyError as e:
				message = "Need to use GTPe with eFEDs!"
				printError(message, self)
				raise e
			except ValueError as e:
				if rate == 'max': printError('Failed to specify a rate '
					                         'when running with GTPe. Use '
					                         'option --useRate', self)
				raise e
			return

		## In case of FEROLs:
		if len(self.config.FEROLs) > 0:
			## Set fragment size and delay for FEROLs:
			self.setSizeFEROLs(fragSize, fragSizeRMS, rate)

			## Set trigger rate at GTPe
			if self.config.useGTPe:
				gtpe = self.symbolMap('GTPE0')
				try:
					utils.setParam(gtpe, 'd2s::GTPeController',
						           'triggerRate', 'double',
						           str(float(rate)*1000),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
				except ValueError as e:
					if rate == 'max':
						printError('Failed to specify a rate when running '
							       'with GTPe. Use option --useRate', self)
					raise e

			## Set super-fragment size for BUs
			if not self.config.useEvB:
				if self.options.verbose > 0: print separator
				for n,bu in enumerate(self.config.BUs):
					utils.setParam(bu, 'gevb2g::BU',
						           'currentSize', 'unsignedLong',
						           self.config.nStreams*int(fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
				if not self.options.dry:
					for bu in self.config.BUs:
						print ("%s dummyFedPayloadSize %d " %
			                   (bu.name, int(utils.getParam(bu,
			                   	                  'gevb2g::BU',
			                   	                  'currentSize',
			                   	                  'xsd:unsignedLong'))))

			return

		## In case of eFEROLs (also configure and enable in this case):
		elif len(self.config.eFEROLs) > 0:
			pool = Pool(min(16,len(self.config.eFEROLs)))

			## Configure and enable pt::frl application on eFEROLs:
			if self.options.verbose > 0: print separator
			tasklist = [(efrl.host, efrl.port, 'pt::frl::Application', n,
				         'Configure',
				         self.options.verbose,
				         self.options.dry) for n,efrl in enumerate(
				                                       self.config.eFEROLs)]
			pool.map(utils.sendSimpleCmdToAppPacked, tasklist)

			if self.options.verbose > 0: print separator
			for n,efrl in enumerate(self.config.eFEROLs):
				utils.sendSimpleCmdToApp(efrl, 'pt::frl::Application',
					                     'Enable',
					                     verbose=self.options.verbose,
					                     dry=self.options.dry)
			sleep(2, self.options.verbose, self.options.dry)

			## Set fragment size for eFEROLs
			if self.options.verbose > 0: print separator
			for n,efrl in enumerate(self.config.eFEROLs):
				if self.config.useEvB or self.options.useLogNormal:
					utils.setParam(efrl, 'evb::test::DummyFEROL', 'fedSize',
						           'unsignedInt', fragSize,
						           verbose=self.options.verbose,
						           dry=self.options.dry)
				else:
					utils.setParam(efrl, 'Client', 'currentSize',
						           'unsignedLong', fragSize,
						           verbose=self.options.verbose,
						           dry=self.options.dry)


			## Set lognormal rms for eFEROLs
			## (when running with --useLogNormal)
			if self.options.useLogNormal:
				if self.options.verbose > 0: print separator
				for n,efrl in enumerate(self.config.eFEROLs):
					utils.setParam(efrl, 'evb::test::DummyFEROL',
						           'fedSizeStdDev', 'unsignedInt',
						           int(fragSizeRMS),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					utils.setParam(efrl, 'evb::test::DummyFEROL',
						           'useLogNormal', 'boolean', 'true',
						           verbose=self.options.verbose,
						           dry=self.options.dry)

			## Set super-fragment size for BUs
			if not self.config.useEvB:
				if self.options.verbose > 0: print separator
				for n,bu in enumerate(self.config.BUs):
					utils.setParam(bu, 'gevb2g::BU',
						           'currentSize', 'unsignedLong',
						           self.config.nStreams*int(fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
				if not self.options.dry:
					for bu in self.config.BUs:
						print ("%s dummyFedPayloadSize %d " %
						       (bu.name, int(utils.getParam(bu,
						      	                  'gevb2g::BU',
						      	                  'currentSize',
						      	                  'xsd:unsignedLong'))))

			if self.options.verbose > 0: print separator

			if self.config.useEvB or self.options.useLogNormal:
				for n,efrl in enumerate(self.config.eFEROLs):
					utils.sendSimpleCmdToApp(efrl, 'evb::test::DummyFEROL',
						                     'Configure',
						                     verbose=self.options.verbose,
						                     dry=self.options.dry)

			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToRUEVMBU('Enable')

			if self.options.verbose > 0: print separator
			## Enable eFEROL clients
			for n,efrl in enumerate(self.config.eFEROLs):
				if self.config.useEvB or self.options.useLogNormal:
					utils.sendSimpleCmdToApp(efrl, 'evb::test::DummyFEROL',
						                     'Enable',
						                     verbose=self.options.verbose,
						                     dry=self.options.dry)
				else:
					utils.sendSimpleCmdToApp(efrl, 'Client', 'start',
						                     verbose=self.options.verbose,
						                     dry=self.options.dry)

			return

		## In case of mstreamio configurations:
		elif self.config.useMSIO:
			for n,ru in enumerate(self.config.RUs):
				utils.setParam(ru, 'Client',
					           'currentSize', 'unsignedLong',
					           fragSize,
					           verbose=self.options.verbose,
					           dry=self.options.dry)
			for n,bu in enumerate(self.config.BUs):
				utils.setParam(bu, 'Server',
					           'currentSize', 'unsignedLong',
					           fragSize,
					           verbose=self.options.verbose,
					           dry=self.options.dry)

		## In case of gevb2g InputEmulator configurations:
		elif self.config.useInputEmulator and not self.config.useEvB:
			for n,ru in enumerate(self.config.RUs):
				utils.setParam(ru, 'gevb2g::InputEmulator',
					           'Mean', 'unsignedLong',
					           fragSize,
					           verbose=self.options.verbose,
					           dry=self.options.dry)
				utils.setParam(ru, 'gevb2g::InputEmulator',
					           'StdDev', 'unsignedLong',
					           int(fragSizeRMS),
					           verbose=self.options.verbose,
					           dry=self.options.dry)
			for n,bu in enumerate(self.config.BUs):
				utils.setParam(bu, 'gevb2g::BU',
					           'currentSize', 'unsignedLong',
					           fragSize,
					           verbose=self.options.verbose,
					           dry=self.options.dry)
		## In case of EvB InputEmulator configurations:
		elif self.config.useInputEmulator and self.config.useEvB:
			for n,ru in enumerate(self.config.RUs):
				classname = 'RU'
				if n==0:
					classname = 'EVM'
					## Set a separate, smaller size for the EVM
					utils.setParam(ru, 'evb::%s'%classname,
						           'dummyFedSize', 'unsignedInt',
						           1024,
						           verbose=self.options.verbose,
						           dry=self.options.dry)
				else:
					utils.setParam(ru, 'evb::%s'%classname,
						           'dummyFedSize', 'unsignedInt',
						           int(fragSize),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
					if fragSizeRMS>0:
						utils.setParam(ru, 'evb::%s'%classname,
							           'dummyFedSizeStdDev',
							           'unsignedInt',
							           int(fragSizeRMS),
							           verbose=self.options.verbose,
							           dry=self.options.dry)
						utils.setParam(ru, 'evb::%s'%classname,
							           'useLogNormal',
							           'boolean',
							           'true',
							           verbose=self.options.verbose,
							           dry=self.options.dry)
				if self.options.useRate != 'max':
					utils.setParam(ru, 'evb::%s'%classname,
						           'maxTriggerRate', 'unsignedInt',
						           int(self.options.useRate),
						           verbose=self.options.verbose,
						           dry=self.options.dry)
	def changeSize(self, fragSize, fragSizeRMS=0, rate='max'):
		## --stopRestart option or eFEROLs:
		##   stop everything, set new size, start again
		if ((hasattr(self.options, 'stopRestart') and
			 self.options.stopRestart) or
		     len(self.config.eFEROLs) > 0):
			utils.stopXDAQs(self.symbolMap,
				            verbose=self.options.verbose,
				            dry=self.options.dry)
			sleep(2, self.options.verbose, self.options.dry)
			self.start(fragSize, fragSizeRMS=fragSizeRMS, rate=rate)
			return

		if self.options.verbose > 0:
			print separator
		if self.options.verbose > 0:
			print ("Changing fragment size to %5d bytes +- %5d at %s rate" %
				                         (fragSize, fragSizeRMS, str(rate)))
		self.setCurrentSize(fragSize, fragSizeRMS, rate)

		## Pause GTPe
		if self.config.useGTPe:
			gtpe = self.symbolMap('GTPE0')
			utils.sendSimpleCmdToApp(gtpe, 'd2s::GTPeController',
				                     "Pause",
				                     verbose=self.options.verbose,
				                     dry=self.options.dry)

		## For eFEDs:
		if len(self.config.eFEDs) > 0:
			## Stop and Halt FEDEmulator
			self.sendCmdToEFEDs('Stop')
			self.sendCmdToEFEDs('Halt')
			# sleep(2, self.options.verbose, self.options.dry)

			## Set fragment size on eFEDs
			self.setSizeEFEDs(fragSize, fragSizeRMS)

			# ## Set trigger rate at GTPe
			# ## This doesn't work yet?
			# if self.config.useGTPe:
			# 	gtpe = self.symbolMap('GTPE0')
			# 	if rate == 'max':
			# 		printError('Failed to specify a rate when '
			# 			       'running with GTPe.', self)
			# 		raise RuntimeError('Failed to specify a rate '
			# 			               'when running with GTPe.')
			# 	utils.setParam(gtpe,
			# 		           'd2s::GTPeController',
			# 		           'triggerRate', 'double',
			# 		           str(float(rate)*1000),
			# 		           verbose=self.options.verbose,
			# 		           dry=self.options.dry)

			## Configure and Enable FEDEmulator
			self.sendCmdToEFEDs('Configure')
			# sleep(2, self.options.verbose, self.options.dry)
			self.sendCmdToEFEDs('Enable')

		## For FEROLs and without eFEDs: pause, change size, resume
		elif len(self.config.FEROLs) > 0 and len(self.config.eFEDs) == 0:
			## Pause FEROLs
			self.sendCmdToFEROLs('Pause')

			## Change fragment size and delay for FEROLs:
			self.setSizeFEROLs(fragSize, fragSizeRMS, rate)

			## Halt EVM/RUs/BUs
			self.sendCmdToEVMRUBU('Halt')
			sleep(2, self.options.verbose, self.options.dry)

			## Change super-fragment size for BUs
			if self.options.verbose > 0: print separator
			for bu in self.config.BUs:
				utils.setParam(bu, 'gevb2g::BU',
					           'currentSize', 'unsignedLong',
					           self.config.nStreams*int(fragSize),
					           verbose=self.options.verbose,
					           dry=self.options.dry)
			if self.options.verbose > 0: print separator
			for bu in self.config.BUs:
				if not self.options.dry:
					print ("%s dummyFedPayloadSize %d " %
					      (bu.name, int(utils.getParam(bu,
					      	                  'gevb2g::BU',
					      	                  'currentSize',
					      	                  'xsd:unsignedLong'))))

			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToRUEVMBU('Enable')
			self.sendCmdToFEROLs('SetupEVG')
			self.sendCmdToFEROLs('Resume')

		## Resume GTPe
		if self.config.useGTPe:
			gtpe = self.symbolMap('GTPE0')
			utils.sendSimpleCmdToApp(gtpe, 'd2s::GTPeController',
				                     "Resume",
				                     verbose=self.options.verbose,
				                     dry=self.options.dry)

		return

	def getSizeRateFromBU(self):
		"""Get the average event rate and size from the BUs
		and multiply them to get throughput.
		Unit is MB/s.
		"""
		sizes, rates = [],[]
		for bu in self.config.BUs:
			sizes.append(int(utils.getParam(bu, 'evb::BU',
				                            'eventSize', 'xsd:unsignedInt')))
			rates.append(int(utils.getParam(bu, 'evb::BU',
				                            'eventRate', 'xsd:unsignedInt')))
		av_size = reduce(lambda a,b:a+b, sizes)/len(sizes) ## in bytes
		av_rate = reduce(lambda a,b:a+b, rates) ## sum up the BUs
		return av_size, av_rate
	def getResultsEvB(self, duration, interval=5):
		"""
		Python implementation of testRubuilder.pl script
		This will get the parameter RATE from the BU after
		an interval time for a total duration.
		"""
		if self.options.dry: return
		if self.config.useEvB:
			sufragsize = (self.config.nStreams/len(self.config.RUs)
						              * self.currentFragSize)
			ratesamples = []
			bu_sizes = []
			starttime = time.time()
			if self.options.verbose>1:
				stdout.write('Rate samples (ev/s @ RU (MB/s @ RU)):\n')
			while(time.time() < starttime+duration):
				time.sleep(interval)
				ru_rate = int(utils.getParam(self.config.RUs[0],
				                            'evb::EVM',
				                            'eventRate',
				                            'xsd:unsignedInt'))

				bu_size, bu_rate = self.getSizeRateFromBU()
				bu_sizes.append(bu_size)
				bu_tp = bu_size*bu_rate/(len(self.config.RUs)*1e6)

				ratesamples.append(ru_rate)
				if self.options.verbose > 0:
					if self.options.verbose>1:
						stdout.write("%d (%7.2f) " % (ru_rate, bu_tp))
						stdout.flush()
					pass
			if self.options.verbose>1:
				stdout.write("\n")

			bu_av_size = sum(bu_sizes)/len(bu_sizes) # Event size
			bu_sufrag_size = bu_av_size/len(self.config.RUs)

			with open(self._outputDir+'/server.csv', 'a') as outfile:
				if self.options.verbose > 0:
					print 'Saving output to', self._outputDir+'server.csv'
				outfile.write("%d, "%sufragsize)
				outfile.write("%d: "%bu_sufrag_size)
				for n,rate in enumerate(ratesamples):
					if n < (len(ratesamples)-1):
						outfile.write('%d, '%rate)
					if n == len(ratesamples)-1:
						outfile.write('%d'%rate)
				outfile.write('\n')

		else:
			printError("getResultsEvB() only works when running with "
				       "the EvB, try getResults()", instance=self)
			return
	def downloadMeasurements(self, url, target):
		if self.options.dry:
			print 'curl -o', target, url
			return
		subprocess.check_call(['curl', '-o', target, url])
	def getResults(self):
		"""
		Download results for each BU, concatenate them, and store them
		in server.csv. Only works for the gevb2g!
		"""
		if self.options.dry: return

		if not self.config.useEvB:
			outputfiles = []
			for n,h in enumerate(self.config.BUs):
				outputfile = '%s/server%d.csv' % (self._outputDir, n)

				if not self.config.useMSIO:
					url =  'http://%s:%d/urn:xdaq-application:'
					url += 'class=%s,instance=%d/downloadMeasurements'
					url = url % (h.host, int(h.port), 'gevb2g::BU', int(n))

				else:
					url = 'http://%s:%d/urn:xdaq-application:'
					url += 'lid=%d/downloadMeasurements'
					## TODO: Extract lid from somewhere?
					url = url % (h.host, int(h.port), 11)

				self.downloadMeasurements(url, outputfile)
				outputfiles.append(outputfile)

			## Concatenate output files
			with open(self._outputDir+'/server.csv', 'a') as outfile:
				if self.options.verbose > 0:
					print 'Saving output to', self._outputDir+'server.csv'
				for fname in outputfiles:
					with open(fname, 'r') as infile:
						outfile.write(infile.read())
						outfile.write('\n')

			## For mstreamIO get the client measurements
			outputfiles = []
			if self.config.useMSIO:
				for n,h in enumerate(self.config.RUs):
					outputfile = '%s/client%d.csv' % (self._outputDir, n)

					url =  'http://%s:%d/urn:xdaq-application:'
					url += 'lid=%d/downloadMeasurements'
					## TODO: Extract lid from somewhere?
					url = url % (h.host, int(h.port), 10)

					self.downloadMeasurements(url, outputfile)
					outputfiles.append(outputfile)

				## Concatenate output files
				with open(self._outputDir+'/client.csv', 'a') as outfile:
					if self.options.verbose > 0:
						print 'Saving output to', self._outputDir+'client.csv'
					for fname in outputfiles:
						with open(fname, 'r') as infile:
							outfile.write(infile.read())
							outfile.write('\n')
		else:
			printError("getResults() only works when running with the "
				       "gevb2g, try getResultsEvB()", instance=self)
			return
	def getResultsFromIfstat(self, duration, delay=2):
		throughput = utils.getIfStatThroughput(self.config.RUs[0].host,
			                                   duration, delay=delay,
			                                   verbose=self.options.verbose,
			                                   interface='p2p1',
			                                   dry=self.options.dry)
		sufragsize = (self.config.nStreams/len(self.config.RUs)
			                                   * self.currentFragSize)
		with open(self._outputDir+'/server.csv', 'a') as outfile:
			if self.options.verbose > 0:
				print 'Saving output to', self._outputDir+'server.csv'
			outfile.write(str(sufragsize))
			outfile.write(', ')
			outfile.write(str(throughput))
			outfile.write('\n')

	def saveFEROLInfoSpaces(self):
		if self.options.verbose > 0:
			print ('Dumping FEROL infospaces into %sinfospaces/' %
				                                     self._outputDir)
		for frl in self.config.FEROLs:
			outputfile = ('%s/infospaces/%s_%d.json' %
				                    (self._outputDir, frl.name,
				                     self.currentFragSize))
			self.saveFEROLInfoSpace(frl, outputfile)
	def saveFEROLInfoSpace(self, host, outputfile):
		url = ('http://%s:%d/urn:xdaq-application:lid=109/infospaces' %
			                                          (host.host, host.port))
		if self.options.dry:
			print 'curl -o', outputfile, url
			return
		else:
			subprocess.check_call(['curl', '-o', outputfile, url])

		# print url
		# items = utils.loadMonitoringItemsFromURL(url)
		# bifi_fed0 = items["BIFI_FED0"] ##.split("&")[0]
		# print bifi_fed0

	def webPingXDAQ(self):
		print separator
		print "Checking availability of relevant hosts"
		for host in self.config.hosts:
			stdout.write(" ... checking %25s:%-5d \t\t ... " %
				                                  (host.host, host.port))
			stdout.flush()
			if (self.options.dry or
				utils.tryWebPing(host.host, host.port) == 0):
				stdout.write("OK\n")
				stdout.flush()
			else:
				stdout.write("FAILED\n")
				stdout.flush()
				return False
		return True
	def dropBUCaches(self):
		if self.options.verbose > 0:
 			print separator
 			print 'Dropping caches in the BUs'
 		cmd = 'echo 3 | sudo tee /proc/sys/vm/drop_caches'
		utils.sendToHostListInParallel2(self.config.BUs,
			                           utils.sendSSHCommandPacked,
			                           [cmd,
			                            self.options.verbose,
			                            self.options.dry])
		# for bu in self.config.BUs:
		# 	utils.sendSSHCommand(bu.host,'whoami',
		# 		                 verbose=self.options.verbose,
		# 		                 dry=self.options.dry)


