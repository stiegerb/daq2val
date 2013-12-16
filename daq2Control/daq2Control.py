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

separator = 70*'-'

from daq2Config import daq2Config, host, FEROL
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import printError, printWarningWithWait, sleep
import daq2Utils as utils

######################################################################
class daq2Control(object):
	'''
---------------------------------------------------------------------
  class daq2Control

 - Takes a daq2Config and a daq2SymbolMap to setup
 - Sets up and starts a FRL/eFRL x RU x BU system
 - Replaces the previous control scripts
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
			printError('Environment missing, did you forget to source setenv-COL.sh? Aborting.', self)
			raise e

		self.options = options
		if len(options.symbolMap)>0:
			self.symbolMap = daq2SymbolMap(options.symbolMap)
		else:
			self.symbolMap = daq2SymbolMap() ## will take it from the environment

		self.config = daq2Config(configFile)
		self.config.fillFromSymbolMap(self.symbolMap)
		if self.options.verbose>1: self.config.printHosts()

		self.__RETRY_COUNTER = 0

		# if self.config.useGTPe and self.config.useEvB:
		# 	printError("Don't know about GTPe with EvB yet. Aborting...", self)
		# 	raise RuntimeError

		if self.config.useGTPe and self.options.useRate == 'max':
			printWarningWithWait("Failed to specify rate for GTPe. Setting it to 100 kHz.", waittime=0, instance=self)
			self.options.useRate = 100

		self._runDir    = self._testDir + '/' + self._platform + '/'
		self._runDir   += self.config.testCaseShort
		if self.options.outputDir:
			if self.options.outputDir.endswith('/'): self.options.outputDir = self.options.outputDir[:-1]
			if self.options.outputTag:
				self._outputDir = self.options.outputDir+'_'+self.options.outputTag
			else:
				self._outputDir = self.options.outputDir
		else:
			self._outputDir = self._testDir + '/data/'

		self._testEnv   = ""
		if len(self._testType) > 0: self._testEnv = "-"+self._testType

	def reset(self):
		"""Reset counters."""
		self.__RETRY_COUNTER = 0

	## Multi-commands
	def sendCmdToEVMRUBU(self, cmd): ## ordering for configure
		if self.options.verbose > 0: print separator
		for n,evm in enumerate(self.config.EVM):
			utils.sendSimpleCmdToApp(evm.host, evm.port, self.config.namespace+'EVM', str(n), cmd, verbose=self.options.verbose, dry=self.options.dry)
		for n,ru in enumerate(self.config.RUs):
			classname = 'RU'
			if self.config.useEvB and n==0: classname = 'EVM'
			utils.sendSimpleCmdToApp(ru.host, ru.port, self.config.namespace+classname, str(n), cmd, verbose=self.options.verbose, dry=self.options.dry)
		for n,bu in enumerate(self.config.BUs):
			utils.sendSimpleCmdToApp(bu.host, bu.port, self.config.namespace+'BU', str(n), cmd, verbose=self.options.verbose, dry=self.options.dry)
	def sendCmdToRUEVMBU(self, cmd): ## ordering for enable
		if self.options.verbose > 0: print separator
		for n,ru in enumerate(self.config.RUs):
			classname = 'RU'
			if self.config.useEvB and n==0: classname = 'EVM'
			utils.sendSimpleCmdToApp(ru.host, ru.port, self.config.namespace+classname, str(n), cmd, verbose=self.options.verbose, dry=self.options.dry)
		for n,evm in enumerate(self.config.EVM):
			utils.sendSimpleCmdToApp(evm.host, evm.port, self.config.namespace+'EVM', str(n), cmd, verbose=self.options.verbose, dry=self.options.dry)
		for n,bu in enumerate(self.config.BUs):
			utils.sendSimpleCmdToApp(bu.host, bu.port, self.config.namespace+'BU', str(n), cmd, verbose=self.options.verbose, dry=self.options.dry)
	def sendCmdToFEROLs(self, cmd):
		if self.options.verbose > 0: print separator
		for frl in self.config.FEROLs:
			utils.sendSimpleCmdToApp(frl.host, frl.port, 'ferol::FerolController', 0, cmd, verbose=self.options.verbose, dry=self.options.dry)
	def sendCmdToEFEDs(self, cmd):
		if self.options.verbose > 0: print separator
		for efed in self.config.eFEDs:
			for instance,_,_ in efed.streams:
				utils.sendSimpleCmdToApp(efed.host, efed.port, 'd2s::FEDEmulator', instance, cmd, verbose=self.options.verbose, dry=self.options.dry)
	def sendCmdToGTPeFMM(self, cmd, invert=False):
		try:
			gtpe = self.symbolMap('GTPE0')
			fmm  = self.symbolMap('FMM0')
			if not invert:
				utils.sendSimpleCmdToApp(gtpe.host, gtpe.port, 'd2s::GTPeController', '0', str(cmd), verbose=self.options.verbose, dry=self.options.dry)
				utils.sendSimpleCmdToApp(fmm.host, fmm.port,   'tts::FMMController',  '0', str(cmd), verbose=self.options.verbose, dry=self.options.dry)
				return
			else:
				utils.sendSimpleCmdToApp(fmm.host, fmm.port,   'tts::FMMController',  '0', str(cmd), verbose=self.options.verbose, dry=self.options.dry)
				utils.sendSimpleCmdToApp(gtpe.host, gtpe.port, 'd2s::GTPeController', '0', str(cmd), verbose=self.options.verbose, dry=self.options.dry)
				return
		except KeyError as e:
			if not self.config.useGTPe:
				printError("You're trying to send a command to a non-existing GTPe...", self)
				raise RuntimeError('Addressing GTPe in non-GTPe running mode')
			raise e
	def sendCmdToFMM(self, cmd):
		try:
			fmm = self.symbolMap('FMM0')
			utils.sendSimpleCmdToApp(fmm.host, fmm.port, 'tts::FMMController', '0', cmd, verbose=self.options.verbose, dry=self.options.dry)
		except KeyError as e:
			printWarningWithWait('No FMM found in symbol map, aborting.', waittime=0, instance=self)
			raise e
	def sendCmdToGTPe(self, cmd):
		try:
			gtpe = self.symbolMap('GTPE0')
			utils.sendSimpleCmdToApp(gtpe.host, gtpe.port, 'd2s::GTPeController', '0', cmd, verbose=self.options.verbose, dry=self.options.dry)
		except KeyError as e:
			printWarningWithWait('No GTPe found in symbol map, aborting.', waittime=0, instance=self)
			pass


	def setSizeFEROLs(self, fragSize, fragSizeRMS, rate='max'):
		if self.options.verbose > 0: print separator

		## Flat profile (i.e. each stream has the same size)
		if self.options.sizeProfile == 'flat':
			delay = utils.getFerolDelay(fragSize, rate)

			## Max rate when running with GTPe?
			if self.config.useGTPe: delay = 20

			for frl in self.config.FEROLs:
				if frl.enableStream0:
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED0',       'unsignedInt', int(fragSize),    verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED0', 'unsignedInt', int(fragSizeRMS), verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED0',           'unsignedInt', int(delay),       verbose=self.options.verbose, dry=self.options.dry)
				if frl.enableStream1:
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED1',       'unsignedInt', int(fragSize),    verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED1', 'unsignedInt', int(fragSizeRMS), verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED1',           'unsignedInt', int(delay),       verbose=self.options.verbose, dry=self.options.dry)
		else:
			if not self.options.profilePerFRL: ## same size for both streams of each FEROL!
				sizeProfile = utils.getSizeProfile(fragSize, len(self.config.FEROLs), self.options.sizeProfile)
				delayProfile = [utils.getFerolDelay(size, rate) for size in sizeProfile]
				relRMS = fragSizeRMS/fragSize

				## Max rate when running with GTPe?
				if self.config.useGTPe: delayProfile = len(self.config.FEROLs)*[20]

				for fragSize,delay,frl in itertools.izip(sizeProfile, delayProfile, self.config.FEROLs):
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED0',       'unsignedInt', int(fragSize),        verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED0', 'unsignedInt', int(relRMS*fragSize), verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED0',           'unsignedInt', int(delay),           verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED1',       'unsignedInt', int(fragSize),        verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED1', 'unsignedInt', int(relRMS*fragSize), verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED1',           'unsignedInt', int(delay),           verbose=self.options.verbose, dry=self.options.dry)
			else: ## profile applied to the two FEROL streams
				sizeProfile = utils.getSizeProfile(fragSize, 2, self.options.sizeProfile)
				delayProfile = [utils.getFerolDelay(size, rate) for size in sizeProfile]
				relRMS = fragSizeRMS/fragSize

				## Max rate when running with GTPe?
				if self.config.useGTPe: delayProfile = 2*[20]

				for frl in self.config.FEROLs:
					if frl.enableStream0:
						utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED0',       'unsignedInt', int(sizeProfile[0]),        verbose=self.options.verbose, dry=self.options.dry)
						utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED0', 'unsignedInt', int(relRMS*sizeProfile[0]), verbose=self.options.verbose, dry=self.options.dry)
						utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED0',           'unsignedInt', int(delayProfile[0]),       verbose=self.options.verbose, dry=self.options.dry)
					if frl.enableStream1:
						utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED1',       'unsignedInt', int(sizeProfile[1]),        verbose=self.options.verbose, dry=self.options.dry)
						utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED1', 'unsignedInt', int(relRMS*sizeProfile[1]), verbose=self.options.verbose, dry=self.options.dry)
						utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED1',           'unsignedInt', int(delayProfile[0]),       verbose=self.options.verbose, dry=self.options.dry)
	def setSizeEFEDs(self, fragSize, fragSizeRMS):
		if self.options.verbose > 0: print separator

		## Flat profile (i.e. each stream has the same size)
		if self.options.sizeProfile == 'flat':
			for efed in self.config.eFEDs: ## loop on eFED machines
				for instance,fedid,_ in efed.streams: ## loop on applications for each eFED
					utils.setParam(efed.host, efed.port, 'd2s::FEDEmulator', instance, 'eventSize',       'unsignedInt', int(fragSize),    verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(efed.host, efed.port, 'd2s::FEDEmulator', instance, 'eventSizeStdDev', 'unsignedInt', int(fragSizeRMS), verbose=self.options.verbose, dry=self.options.dry)
		else: ## UNTESTED
			raise RuntimeError('not implemented yet!')
			sizeProfile = utils.getSizeProfile(fragSize, len(self.config.nStreams), self.options.sizeProfile)
			relRMS = fragSizeRMS/fragSize

			for fragSize,efed in zip(sizeProfile, self.config.eFEDs):
				utils.setParam(efed.host, efed.port, 'd2s::FEDEmulator', 0, 'eventSize',       'unsignedInt', int(fragSize),        verbose=self.options.verbose, dry=self.options.dry)
				utils.setParam(efed.host, efed.port, 'd2s::FEDEmulator', 0, 'eventSizeStdDev', 'unsignedInt', int(relRMS*fragSize), verbose=self.options.verbose, dry=self.options.dry)

	def setRunNumber(self, number=0):
		## Set Runnumber here:
		if number==0:
			number = time.strftime('%m%d%H%M%S')

		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Setting run number", number
		if self.options.verbose > 0: print separator

		for n,h in enumerate(self.config.FMM):
			utils.setParam(h.host, h.port, 'tts::FMMController',            str(n), 'runNumber', 'unsignedInt', number, verbose=self.options.verbose, dry=self.options.dry)
		for n,h in enumerate(self.config.RUs):
			classname = 'RU' if not self.config.useEvB or n>0 else 'EVM'
			utils.setParam(h.host, h.port, self.config.namespace+classname, str(n), 'runNumber', 'unsignedInt', number, verbose=self.options.verbose, dry=self.options.dry)
		for n,h in enumerate(self.config.EVM):
			utils.setParam(h.host, h.port, self.config.namespace+'EVM',     str(n), 'runNumber', 'unsignedInt', number, verbose=self.options.verbose, dry=self.options.dry)
		for n,h in enumerate(self.config.BUs):
			utils.setParam(h.host, h.port, self.config.namespace+'BU',      str(n), 'runNumber', 'unsignedInt', number, verbose=self.options.verbose, dry=self.options.dry)

	## Control methods
	def setup(self):
		"""Clean up and re-create run directory, fill config templates, create output directory"""
		if self.options.verbose > 0: print separator

		if self.options.relRMS and not self.options.useLogNormal:
			printWarningWithWait("  Non-zero rms value, but not --useLogNormal!\n  Most likely something went wrong somewhere.")

		## Cleanup run dir
		if not self.options.dry:
			subprocess.check_call(['rm', '-rf', self._runDir])
			subprocess.check_call(['mkdir', '-p', self._runDir])

		## Clean up and create output dir
		self.prepareOutputDir()

		## Fill configuration template
		if self.options.verbose > 0: print 'Filling configuration template in ' + self._runDir + '/configuration.xml'
		if not self.options.dry:
			filledconfig = self.symbolMap.fillTemplate(self.config.file)
			with open(self._runDir+'/configuration.xml', 'w') as file:
				file.write(filledconfig)

		## Produce configure command file
		if self.options.verbose > 0: print 'Producing configuration command file in ' + self._runDir + '/configure.cmd.xml'
		if not self.options.dry:
			with open(self._runDir+'/configure.cmd.xml', 'w') as file:
				configureBody = '<xdaq:Configure xmlns:xdaq=\"urn:xdaq-soap:3.0\">\n\n\n' + filledconfig + '\n\n\n</xdaq:Configure>\n'
				configureCmd = utils.SOAPEnvelope % configureBody
				file.write(configureCmd)
	def start(self, fragSize, fragSizeRMS=0, rate='max', onlyPrepare=False):
		"""Start all XDAQ processes, set configuration for fragSize and start running
			onlyPrepare=True will stop before configuring and enabling
		"""
		self.currentFragSize    = fragSize
		self.currentFragSizeRMS = fragSizeRMS
		self.currentRate        = rate

		## Start the xdaq processes from the launchers
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Starting XDAQ processes"
		for h in self.config.hosts:
			utils.sendCmdToLauncher(h.host, h.lport, 'STARTXDAQ'+str(h.port), verbose=self.options.verbose, dry=self.options.dry)
		sleep(2, self.options.verbose, self.options.dry)

		## Check availability of xdaq processes on relevant hosts
		if not self.webPingXDAQ():
			## Check again, maybe it needs more time to start?
			if self.options.verbose > 0: print separator
			if self.options.verbose > 0: print 'Waiting 5 seconds and checking again...'
			sleep(5, self.options.verbose, self.options.dry)
			if not self.webPingXDAQ():
				## Stop and restart the processes
				if self.options.verbose > 0: print separator
				if self.options.verbose > 0: print "Stopping and restarting XDAQ processes"
				utils.stopXDAQs(self.symbolMap, verbose=self.options.verbose, dry=self.options.dry)
				if self.options.verbose > 0: print separator
				if self.options.verbose > 0: print "Restarting XDAQ processes"
				for h in self.config.hosts:
					utils.sendCmdToLauncher(h.host, h.lport, 'STARTXDAQ'+str(h.port), verbose=self.options.verbose, dry=self.options.dry)
				sleep(2, self.options.verbose, self.options.dry)

				## Check one last time before giving up
				if not self.webPingXDAQ():
					raise RuntimeError('Not all hosts ready!')

		## Send the configuration file to each host
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Configuring XDAQ processes"
		if not utils.sendToHostListInParallel(self.config.hosts, utils.sendCmdFileToExecutivePacked, (self._runDir+'/configure.cmd.xml', self.options.verbose, self.options.dry)):
			## Stop and restart the processes
			if self.options.verbose > 0: print separator
			if self.options.verbose > 0: print "Stopping and restarting XDAQ processes"
			utils.stopXDAQs(self.symbolMap, verbose=self.options.verbose, dry=self.options.dry)
			if self.options.verbose > 0: print separator
			if self.options.verbose > 0: print "Restarting XDAQ processes"
			for h in self.config.hosts:
				utils.sendCmdToLauncher(h.host, h.lport, 'STARTXDAQ'+str(h.port), verbose=self.options.verbose, dry=self.options.dry)
			if self.options.verbose > 0: print separator
			sleep(2, self.options.verbose, self.options.dry)

			## Try again to send the command file
			if not utils.sendToHostListInParallel(self.config.hosts, utils.sendCmdFileToExecutivePacked, (self._runDir+'/configure.cmd.xml', self.options.verbose, self.options.dry)):
				raise RuntimeError('Failed to send command file to all hosts')
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
		to_be_checked = [(self.config.RUs[1:] + self.config.FEROLs, 'Configured'), ([self.config.RUs[0]] + self.config.BUs + self.config.EVM + self.config.eFEDs + self.config.GTPe, 'Ready')]
		if not self.config.useEvB:
			to_be_checked = [(self.config.RUs + self.config.FEROLs, 'Configured'), (self.config.BUs + self.config.EVM + self.config.eFEDs + self.config.GTPe, 'Ready')]

		for hostlist, state in to_be_checked:
			if utils.checkStates(hostlist, state, verbose=self.options.verbose, dry=self.options.dry): continue
			printWarningWithWait("Failed to reach 'Configured' state.", waittime=0, instance=self)
			return False
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print 'STOPPED'
		if self.options.verbose > 0: print separator
		return True

	def configure(self):
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Configuring"

		## In case of eFED:
		if len(self.config.eFEDs) > 0:
			self.sendCmdToGTPeFMM('Configure', invert=False)
			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToEFEDs('Configure')
			self.sendCmdToFEROLs('Configure')
			sleep(10, self.options.verbose, self.options.dry)
			if not self.checkConfigured():
				printWarningWithWait("Not everything configured. Waiting another 10s and checking again.", waittime=10, instance=self)
				if not self.checkConfigured():
					self.retry('Failed to configure.')
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
				printWarningWithWait("Not everything configured. Waiting another 10s and checking again.", waittime=10, instance=self)
				if not self.checkConfigured():
					self.retry('Failed to configure.')
			return

		printWarningWithWait("Doing nothing.", waittime=1, instance=self)
		return
	def checkConfigured(self):
		if self.options.verbose > 0: print separator
		## Check everything is 'Configured' or 'Ready'
		to_be_checked = [(self.config.RUs[1:] + self.config.FEROLs, 'Configured'), ([self.config.RUs[0]] + self.config.BUs + self.config.EVM + self.config.eFEDs + self.config.FMM + self.config.GTPe, 'Ready')]
		if not self.config.useEvB:
			to_be_checked = [(self.config.RUs + self.config.FEROLs, 'Configured'), (self.config.BUs + self.config.EVM + self.config.FMM + self.config.eFEDs + self.config.GTPe, 'Ready')]

		for hostlist, state in to_be_checked:
			if utils.checkStates(hostlist, state, verbose=self.options.verbose, dry=self.options.dry): continue
			printWarningWithWait('Configure failed for some machines.', waittime=0, instance=self)
			return False
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print 'CONFIGURED'
		if self.options.verbose > 0: print separator
		return True
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
			sleep(3, self.options.verbose, self.options.dry)

			## Enable FMM:
			if self.config.useGTPe:
				fmm = self.symbolMap('FMM0')
				utils.sendSimpleCmdToApp(fmm.host, fmm.port,   'tts::FMMController',  '0', 'Enable', verbose=self.options.verbose, dry=self.options.dry)

			self.sendCmdToEFEDs('Enable')

			if not self.checkEnabled():
				self.retry('Failed to enable all FEROLs and RUs.')


			## Enable GTPe:
			if self.config.useGTPe:
				gtpe = self.symbolMap('GTPE0')
				utils.sendSimpleCmdToApp(gtpe.host, gtpe.port, 'd2s::GTPeController', '0', 'Enable', verbose=self.options.verbose, dry=self.options.dry)

			sleep(2, self.options.verbose, self.options.dry)
			return

		printWarningWithWait("Doing nothing.", waittime=1, instance=self)
		return
	def checkEnabled(self):
		if self.options.verbose > 0: print separator

		## Check Status of FEROLs and EVM/RUs:
		if not utils.checkStates(self.config.FEROLs + self.config.RUs + self.config.BUs, 'Enabled', verbose=self.options.verbose, dry=self.options.dry):
			return False
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print 'ENABLED'
		if self.options.verbose > 0: print separator
		return True
	def retry(self, message):
		print " -- retry", self.__RETRY_COUNTER+1, "of", self.options.retries
		if self.__RETRY_COUNTER < self.options.retries:
			self.__RETRY_COUNTER += 1
			printWarningWithWait(message+' ... retrying', waittime=0, instance=self)
			utils.stopXDAQs(self.symbolMap, verbose=self.options.verbose, dry=self.options.dry)
			self.start(fragSize=self.currentFragSize, fragSizeRMS=self.currentFragSizeRMS, rate=self.currentRate)
		else:
			printError(message, instance=self)
			raise RuntimeError(message)

	def prepareOutputDir(self):
		import glob
		if not self.options.outputDir:
			self._outputDir += self.config.testCase
			if self.options.useLogNormal: self._outputDir += '_RMS_%3.1f' % float(self.options.relRMS)
			if self.options.outputTag:    self._outputDir += '_'+self.options.outputTag
		if not self._outputDir.endswith('/'): self._outputDir += '/'
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print 'Storing output in:', self._outputDir
		if self.options.dry: return

		## Create output directory
		try:
			os.makedirs(self._outputDir)
		except OSError: ## dir exists, save previous measurements:
			newdir = self._outputDir + 'previous/' + time.strftime('%b%d-%H%M%S')
			os.makedirs(newdir)
			if len(glob.glob(self._outputDir+'*.csv')) > 0:
				subprocess.check_call(['mv'] + glob.glob(self._outputDir+'*.csv') + [newdir])
			if os.path.exists(self._outputDir+'infospaces'): ## UNTESTED
				subprocess.check_call(['mv', self._outputDir+'infospaces', newdir])

		try:
			os.makedirs(self._outputDir + "infospaces")
		except OSError: pass ## dir exists already


		## Prepare output file:
		with open(self._outputDir+'/server.csv', 'a') as outfile:
			outfile.write('## Testcase: %s\n' % self.config.testCase)
			if self.options.useLogNormal: outfile.write('## useLogNormal = True, RMS = %5.2f\n' % float(self.options.relRMS) )
			outfile.write('## %s\n' % time.strftime('%a %b %d, %Y / %H:%M:%S'))
			outfile.write('\n##\n')
			self.config.printHosts(out=outfile, prepend='## ')
			outfile.write('\n\n')
			outfile.close()

	def setSize(self, fragSize, fragSizeRMS=0, rate='max'):
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Setting fragment size to %5d bytes +- %-5d at %s kHz rate" % (fragSize, fragSizeRMS, str(rate))
		self.currentFragSize    = fragSize
		self.currentFragSizeRMS = fragSizeRMS
		self.currentRate        = rate

		## In case of eFED:
		if len(self.config.eFEDs) > 0:
			## Set fragment size and delay for eFEDs:
			self.setSizeEFEDs(fragSize, fragSizeRMS)

			## Set trigger rate at GTPe
			try:
				gtpe = self.symbolMap('GTPE0')
				utils.setParam(gtpe.host, gtpe.port, 'd2s::GTPeController', '0', 'triggerRate', 'double', str(float(rate)*1000), verbose=self.options.verbose, dry=self.options.dry)
			except KeyError as e:
				message = "Need to use GTPe with eFEDs!"
				printError(message, self)
				raise e
			except ValueError as e:
				if rate == 'max': printError('Failed to specify a rate when running with GTPe. Use option --useRate', self)
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
					utils.setParam(gtpe.host, gtpe.port, 'd2s::GTPeController', '0', 'triggerRate', 'double', str(float(rate)*1000), verbose=self.options.verbose, dry=self.options.dry)
				except ValueError as e:
					if rate == 'max':
						printError('Failed to specify a rate when running with GTPe. Use option --useRate', self)
					raise e

			## Set super-fragment size for BUs
			if not self.config.useEvB:
				if self.options.verbose > 0: print separator
				for n,bu in enumerate(self.config.BUs):
					utils.setParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'unsignedLong', self.config.nStreams*int(fragSize), verbose=self.options.verbose, dry=self.options.dry)
				if not self.options.dry:
					for n,bu in enumerate(self.config.BUs):
						print bu.name, 'dummyFedPayloadSize', int(utils.getParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'xsd:unsignedLong'))

			return

		## In case of eFEROLs (also configure and enable in this case):
		elif len(self.config.eFEROLs) > 0:
			from multiprocessing import Pool
			pool = Pool(len(self.config.eFEROLs))

			## Configure and enable pt::frl application on eFEROLs:
			if self.options.verbose > 0: print separator
			tasklist = [(efrl.host, efrl.port, 'pt::frl::Application', n, 'Configure', self.options.verbose, self.options.dry) for n,efrl in enumerate(self.config.eFEROLs)]
			pool.map(utils.sendSimpleCmdToAppPacked, tasklist)

			# for n,efrl in enumerate(self.config.eFEROLs):
			# 	utils.sendSimpleCmdToApp(efrl.host, efrl.port, 'pt::frl::Application', n, 'Configure')

			if self.options.verbose > 0: print separator
			for n,efrl in enumerate(self.config.eFEROLs):
				utils.sendSimpleCmdToApp(efrl.host, efrl.port, 'pt::frl::Application', n, 'Enable')
			sleep(2, self.options.verbose, self.options.dry)

			## Set fragment size for eFEROLs
			if self.options.verbose > 0: print separator
			for n,efrl in enumerate(self.config.eFEROLs):
				if self.config.useEvB or self.options.useLogNormal: utils.setParam(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'fedSize',     'unsignedInt',  fragSize, verbose=self.options.verbose, dry=self.options.dry)
				else:                                               utils.setParam(efrl.host, efrl.port, 'Client',                n, 'currentSize', 'unsignedLong', fragSize, verbose=self.options.verbose, dry=self.options.dry)


			## Set lognormal rms for eFEROLs (when running with --useLogNormal)
			if self.options.useLogNormal:
				if self.options.verbose > 0: print separator
				for n,efrl in enumerate(self.config.eFEROLs):
					utils.setParam(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'fedSizeStdDev', 'unsignedInt', int(fragSizeRMS), verbose=self.options.verbose, dry=self.options.dry)
					utils.setParam(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'useLogNormal',  'boolean',     'true',           verbose=self.options.verbose, dry=self.options.dry)

			## Set super-fragment size for BUs
			if not self.config.useEvB:
				if self.options.verbose > 0: print separator
				for n,bu in enumerate(self.config.BUs):
					utils.setParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'unsignedLong', self.config.nStreams*int(fragSize), verbose=self.options.verbose, dry=self.options.dry)
				if not self.options.dry:
					for n,bu in enumerate(self.config.BUs):
						print bu.name, 'dummyFedPayloadSize', int(utils.getParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'xsd:unsignedLong'))

			if self.options.verbose > 0: print separator

			if self.config.useEvB or self.options.useLogNormal:
				for n,efrl in enumerate(self.config.eFEROLs):
					utils.sendSimpleCmdToApp(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'Configure')

			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToRUEVMBU('Enable')

			if self.options.verbose > 0: print separator
			## Enable eFEROL clients
			for n,efrl in enumerate(self.config.eFEROLs):
				if self.config.useEvB or self.options.useLogNormal: utils.sendSimpleCmdToApp(efrl.host, efrl.port, 'evb::test::DummyFEROL', n, 'Enable')
				else:                                               utils.sendSimpleCmdToApp(efrl.host, efrl.port, 'Client',                n, 'start')
			return
	def changeSize(self, fragSize, fragSizeRMS=0, rate='max'):
		## --stopRestart option or eFEROLs: stop everything, set new size, start again
		if (hasattr(self.options, 'stopRestart') and self.options.stopRestart) or len(self.config.eFEROLs) > 0:
			utils.stopXDAQs(self.symbolMap, verbose=self.options.verbose, dry=self.options.dry)
			sleep(2, self.options.verbose, self.options.dry)
			self.start(fragSize, fragSizeRMS=fragSizeRMS, rate=rate)
			return

		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Changing fragment size to %5d bytes +- %5d at %s rate" % (fragSize, fragSizeRMS, str(rate))
		self.currentFragSize    = fragSize
		self.currentFragSizeRMS = fragSizeRMS
		self.currentRate        = rate

		## Pause GTPe
		if self.config.useGTPe:
			gtpe = self.symbolMap('GTPE0')
			utils.sendSimpleCmdToApp(gtpe.host, gtpe.port, 'd2s::GTPeController', '0', "Pause", verbose=self.options.verbose, dry=self.options.dry)

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
			# 		printError('Failed to specify a rate when running with GTPe.', self)
			# 		raise RuntimeError('Failed to specify a rate when running with GTPe.')
			# 	utils.setParam(gtpe.host, gtpe.port, 'd2s::GTPeController', '0', 'triggerRate', 'double', str(float(rate)*1000), verbose=self.options.verbose, dry=self.options.dry)

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
			for n,bu in enumerate(self.config.BUs):
				utils.setParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'unsignedLong', self.config.nStreams*int(fragSize), verbose=self.options.verbose, dry=self.options.dry)
			if self.options.verbose > 0: print separator
			for n,bu in enumerate(self.config.BUs):
				if not self.options.dry: print bu.name, 'dummyFedPayloadSize', int(utils.getParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'xsd:unsignedLong'))

			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToRUEVMBU('Enable')
			self.sendCmdToFEROLs('SetupEVG')
			self.sendCmdToFEROLs('Resume')

		## Resume GTPe
		if self.config.useGTPe:
			gtpe = self.symbolMap('GTPE0')
			utils.sendSimpleCmdToApp(gtpe.host, gtpe.port, 'd2s::GTPeController', '0', "Resume", verbose=self.options.verbose, dry=self.options.dry)

		return

	def getResultsEvB(self, duration, interval=5):
		"""Python implementation of testRubuilder.pl script
		This will get the parameter RATE from the BU after an interval time for
		a total duration."""
		if self.options.dry: return
		if self.config.useEvB:
			sufragsize = self.config.nStreams/len(self.config.RUs) * self.currentFragSize
			ratesamples = []
			starttime = time.time()
			stdout.write('Rate samples: ')
			while(time.time() < starttime+duration):
				time.sleep(interval)
				sample = int(utils.getParam(self.config.RUs[0].host, self.config.RUs[0].port, 'evb::EVM', str(0), 'eventRate', 'xsd:unsignedInt'))
				ratesamples.append(sample)
				if self.options.verbose > 0:
					stdout.write(str(sample)+' ')
					stdout.flush()
			print '\n'

			with open(self._outputDir+'/server.csv', 'a') as outfile:
				if self.options.verbose > 0: print 'Saving output to', self._outputDir+'server.csv'
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
		if self.options.dry: return
		if not self.config.useEvB:
			outputfiles = []
			for n,h in enumerate(self.config.BUs):
				outputfile = '%s/server%d.csv' % (self._outputDir, n)
				utils.downloadMeasurements(h.host, h.port, self.config.namespace+'BU', n, outputfile) ## need namespace here? this only works for gevb2g anyway
				outputfiles.append(outputfile)

			## Concatenate output files
			with open(self._outputDir+'/server.csv', 'a') as outfile:
				if self.options.verbose > 0: print 'Saving output to', self._outputDir+'server.csv'
				for fname in outputfiles:
					with open(fname, 'r') as infile:
						outfile.write(infile.read())
						outfile.write('\n')
		else:
			print "getResults() only works when running with the gevb2g, try getResultsEvB()"
			return
	def getResultsFromIfstat(self, duration, delay=2):
		throughput = utils.getIfStatThroughput(self.config.RUs[0].host, duration, delay=delay, verbose=self.options.verbose, interface='p2p1', dry=self.options.dry)
		sufragsize = self.config.nStreams/len(self.config.RUs) * self.currentFragSize
		with open(self._outputDir+'/server.csv', 'a') as outfile:
			if self.options.verbose > 0: print 'Saving output to', self._outputDir+'server.csv'
			outfile.write(str(sufragsize))
			outfile.write(', ')
			outfile.write(str(throughput))
			outfile.write('\n')

	def saveFEROLInfoSpaces(self):
		if self.options.verbose > 0: print 'Dumping FEROL infospaces into %sinfospaces/' % self._outputDir
		for frl in self.config.FEROLs:
			outputfile = '%s/infospaces/%s_%d.json' % (self._outputDir, frl.name, self.currentFragSize)
			self.saveFEROLInfoSpace(frl, outputfile)
	def saveFEROLInfoSpace(self, host, outputfile):
		url = 'http://%s:%d/urn:xdaq-application:lid=109/infospaces' % (host.host, host.port)
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
			stdout.write(" ... checking %25s:%-5d \t\t ... " % (host.host, host.port))
			stdout.flush()
			if self.options.dry or utils.tryWebPing(host.host, host.port) == 0:
				stdout.write("OK\n")
				stdout.flush()
			else:
				stdout.write("FAILED\n")
				stdout.flush()
				return False
		return True


