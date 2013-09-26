#! /usr/bin/env python

import os, time, subprocess
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import printError, sendCmdToLauncher, sleep

def stopXDAQLaunchers(symbolMap, options):
	"""Kills the xdaqLauncher process on all the SOAP hosts defined in the symbolmap"""
	for host in symbolMap.allHosts:
		if options.verbose > 1: print "Stopping xdaqLauncher for %-20s on %s:%d" % (host.name, host.host, host.port)
		sendCmdToLauncher(host.host, host.lport, 'STOPLAUNCHER')

def getXDAQLauncherStatus(symbolMap, options):
	"""Kills the xdaqLauncher process on all the SOAP hosts defined in the symbolmap"""
	for host in symbolMap.allHosts:
		sendCmdToLauncher(host.host, host.lport, 'GETXDAQSTATUS')

def startXDAQLauncher(host, port, logfile, options):
	"""Start a single xdaqLauncher process on host:port"""
	try:
		testDir  = os.environ['RUB_TESTER_HOME']
		testType = os.environ['TEST_TYPE']
		user     = os.environ['USER']
	except KeyError as e:
		printError('Environment missing, did you forget to source setenv-COL.sh? Aborting.')
		raise e
	testEnv   = ""
	if len(testType) > 0: testEnv = "-"+testType

	sshCmd      = "ssh -x -n " + host
	launcherCmd = '"cd /tmp && sudo rm -f /tmp/core.* && source %s/setenv%s.sh && xdaqLauncher %d"' % (testDir, testEnv, port)
	awkCmd      = "awk '{print \"%s:%d \" $0}'" % (host, port)
	cmd         = sshCmd + " \"sudo -u %s sh -c \\"%user + launcherCmd +"\\\" | " +  awkCmd + " &"
	return subprocess.call(cmd, stderr=logfile, stdout=logfile, shell=True)

def startXDAQLaunchers(logfile, symbolMap, options):
	"""Starts an xdaqLauncher process on all the SOAP hosts defined in the symbolmap"""
	for host in symbolMap.allHosts:
		message = "Starting xdaqLauncher for %-20s on %s:%d(LAUNCHER):%d(SOAP)" % (host.name, host.host, host.lport, host.port)
		logfile.write(message + '\n')
		if options.verbose > 0: print message
		startXDAQLauncher(host.host,host.lport,logfile, options)
		sleep(0.2)

if __name__ == "__main__":
	from optparse import OptionParser
	parser = OptionParser()
	parser.add_option("--stop",   default=False, action="store_true", dest="stop",   help="Stop all the XDAQ launchers and exit")
	parser.add_option("--start",  default=False, action="store_true", dest="start",  help="Start all the XDAQ launchers and exit")
	parser.add_option("--status", default=False, action="store_true", dest="status", help="Get the status of all XDAQ launchers")
	parser.add_option("-v", "--verbose", default=1, action="store", type='int',       dest="verbose",        help="Set the verbose level, [default: %default (semi-quiet)]")
	parser.add_option("-l", "--logFile", default='launcherLog.txt', action="store",  type='string', dest="logFile", help="Store stdout and stderr output of XDAQ launchers in this file, [default: %default]")

	(options, args) = parser.parse_args()

	sm = daq2SymbolMap()

	if options.stop:
		stopXDAQLaunchers(sm, options)
		exit(0)
	if options.status:
		getXDAQLauncherStatus(sm, options)
		exit(0)
	if options.start:
		with open(options.logFile, 'w') as logfile:
			length = 120
			logfile.write(length*'#' + '\n')
			logfile.write(length*'#' + '\n')
			logfile.write('\n')
			logfile.write('  Starting launchers at %s \n' % time.strftime('%a %b %d, %Y / %H:%M:%S'))
			logfile.write('\n')
			logfile.write(length*'#' + '\n')
			logfile.write(length*'#' + '\n')
			startXDAQLaunchers(logfile, sm, options)
			logfile.write(length*'#' + '\n')
			logfile.write(length*'#' + '\n')
			logfile.write('\n')
		exit(0)
	parser.print_help()
	exit(-1)
