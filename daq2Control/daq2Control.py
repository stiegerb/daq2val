#! /usr/bin/env python
######################################################################
#  For now we assume that we either run with FEROLs or eFEROLs,      #
#  never with both!                                                  #
#                                                                    #
#  ToDo-List:                                                        #
#   - Output naming for --runScan? Why no _RMS_X.X behind name?      #
#   - Automatize the number of samples, depending on duration        #
#   - Add option to use dummyFerol                                   #
#   - Testing testing testing                                        #
######################################################################

import subprocess
import re, os, shlex
import time
from sys import stdout

separator = 70*'-'

from daq2Config import daq2Config, host, FEROL, SIZE_LIMIT_TABLE
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
		self.config.printHosts()

		self._runDir    = self._testDir + '/' + self._platform + '/'
		self._runDir   += self.config.testCaseShort
		self._outputDir = self._testDir + '/data/'

		self._testEnv   = ""
		if len(self._testType) > 0: self._testEnv = "-"+self._testType

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
			utils.sendSimpleCmdToApp(frl.host, frl.port, 'ferol::FerolController', 0, cmd)
	def setSizeFEROLs(self, fragSize, fragSizeRMS, rate='max'):
		if self.options.verbose > 0: print separator
		delay = utils.getFerolDelay(fragSize, rate)

		for frl in self.config.FEROLs:
			if frl.enableStream0:
				utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED0',       'unsignedInt', int(fragSize),    verbose=self.options.verbose, dry=self.options.dry)
				utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED0', 'unsignedInt', int(fragSizeRMS), verbose=self.options.verbose, dry=self.options.dry)
				utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED0',           'unsignedInt', int(delay),       verbose=self.options.verbose, dry=self.options.dry)
			if frl.enableStream1:
				utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_bytes_FED1',       'unsignedInt', int(fragSize),    verbose=self.options.verbose, dry=self.options.dry)
				utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Length_Stdev_bytes_FED1', 'unsignedInt', int(fragSizeRMS), verbose=self.options.verbose, dry=self.options.dry)
				utils.setParam(frl.host, frl.port, 'ferol::FerolController', 0, 'Event_Delay_ns_FED1',           'unsignedInt', int(delay),       verbose=self.options.verbose, dry=self.options.dry)

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
	def start(self, fragSize, fragSizeRMS=0, rate='max'):
		"""Start all XDAQ processes, set configuration for fragSize and start running"""
		self.currentFragSize = fragSize
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Starting XDAQ processes"
		for h in self.config.hosts:
			utils.sendCmdToLauncher(h.host, h.lport, 'STARTXDAQ'+str(h.port), verbose=self.options.verbose, dry=self.options.dry)
		sleep(2, self.options.verbose, self.options.dry)

		if not self.webPingXDAQ():
			if self.options.verbose > 0: print separator
			if self.options.verbose > 0: print 'Waiting 3 seconds and checking again...'
			sleep(3, self.options.verbose, self.options.dry)
			if not self.webPingXDAQ():
				raise RuntimeError('Not all hosts ready!')

		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Configuring XDAQ processes"
		utils.sendToHostListInParallel(self.config.hosts, utils.sendCmdFileToExecutiveMulti, (self._runDir+'/configure.cmd.xml', self.options.verbose, self.options.dry))

		sleep(2, self.options.verbose, self.options.dry)
		self.setSize(fragSize, fragSizeRMS, rate=rate)
		sleep(5, self.options.verbose, self.options.dry)
		# self.sendCmdToRUEVMBU('Enable')
		self.sendCmdToFEROLs('Enable')
	def setSize(self, fragSize, fragSizeRMS=0, rate='max'):
		## This is supposed to work both for eFEROLs and FEROLS!
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print "Setting fragment size to %5d bytes +- %-5d at %s kHz rate" % (fragSize, fragSizeRMS, str(rate))

		## In case of FEROLs:
		if len(self.config.FEROLs) > 0:
			## Set fragment size and delay for FEROLs:
			self.setSizeFEROLs(fragSize, fragSizeRMS, rate)
			self.currentFragSize = fragSize

			## Set super-fragment size for BUs
			if not self.config.useEvB:
				if self.options.verbose > 0: print separator
				for n,bu in enumerate(self.config.BUs):
					utils.setParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'unsignedLong', self.config.nStreams*int(fragSize), verbose=self.options.verbose, dry=self.options.dry)
				if not self.options.dry:
					for n,bu in enumerate(self.config.BUs):
						print bu.name, 'dummyFedPayloadSize', int(utils.getParam(bu.host, bu.port, 'gevb2g::BU', str(n), 'currentSize', 'xsd:unsignedLong'))

			self.sendCmdToFEROLs('Configure')
			sleep(5, self.options.verbose, self.options.dry)

			self.sendCmdToEVMRUBU('Configure')
			self.sendCmdToRUEVMBU('Enable') ## Have to enable RUs/EVM/BUs here?
			return

		## In case of eFEROLs:
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
			self.currentFragSize = fragSize


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
		## For FEROLs: pause, change size, resume
		if len(self.config.FEROLs) > 0 and not self.config.useEvB and not self.options.stopRestart:
			if self.options.verbose > 0: print separator
			if self.options.verbose > 0: print "Changing fragment size to %5d bytes +- %5d at %s rate" % (fragSize, fragSizeRMS, str(rate))

			## Pause FEROLs
			self.sendCmdToFEROLs('Pause')

			## Change fragment size and delay for FEROLs:
			self.setSizeFEROLs(fragSize, fragSizeRMS, rate)
			self.currentFragSize = fragSize

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
			return

		## For eFEROLs: stop everything, set new size, start again
		elif len(self.config.eFEROLs) > 0 or self.config.useEvB or self.options.stopRestart:
			utils.stopXDAQs(self.symbolMap, verbose=self.options.verbose, dry=self.options.dry)
			sleep(5, self.options.verbose, self.options.dry)
			self.start(fragSize, fragSizeRMS=fragSizeRMS, rate=rate)
			return

		else: return

	def prepareOutputDir(self):
		import glob
		self._outputDir += self.config.testCase
		if self.options.useLogNormal: self._outputDir += '_RMS_%3.1f/' % float(self.options.relRMS)
		if not self._outputDir.endswith('/'): self._outputDir += '/'
		if self.options.verbose > 0: print separator
		if self.options.verbose > 0: print 'Storing output in:', self._outputDir
		if self.options.dry: return

		## Save previous measurements:
		if os.path.exists(self._outputDir):
			newdir = self._outputDir + 'previous/' + time.strftime('%b%d-%H%M%S')
			os.makedirs(newdir)
			if len(glob.glob(self._outputDir+'*.csv')) > 0:
				subprocess.check_call(['mv'] + glob.glob(self._outputDir+'*.csv') + [newdir])
		else:
			os.makedirs(self._outputDir)

		## Prepare output file:
		with open(self._outputDir+'/server.csv', 'a') as outfile:
			outfile.write('## Testcase: %s\n' % self.config.testCase)
			if self.options.useLogNormal: outfile.write('## useLogNormal = True, RMS = %5.2f\n' % float(self.options.relRMS) )
			outfile.write('## %s\n' % time.strftime('%a %b %d, %Y / %H:%M:%S'))
			outfile.write('\n')
			outfile.close()
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


