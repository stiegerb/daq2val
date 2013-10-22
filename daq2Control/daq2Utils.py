#! /usr/bin/env python
######################################################################
#  ToDo-List:                                                        #
#   - Fix order of stopping xdaqs to prevent log spamming            #
######################################################################

import os, subprocess, shlex, re
from sys import stdout

separator = 70*'-'
SOAPEnvelope = '''<SOAP-ENV:Envelope
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

SIZE_LIMIT_TABLE = {
     # max size, scan until
	 1 : (64000, 16000),  # merging by  1
	 4 : (32000, 16000),  # merging by  4
	 8 : (32000, 16000),  # merging by  8
	12 : (21000, 10240),  # merging by 12
	16 : (16000,  8192),  # merging by 16
	20 : (12800,  6400),  # merging by 20
	24 : (10500,  5120),  # merging by 24
	32 : ( 8000,  4096)   # merging by 32
}
def checkMaxSize(maxsize, mergingby):
	try:
		return maxsize == SIZE_LIMIT_TABLE[mergingby][0]
	except KeyError:
		printWarningWithWait("Don't know maximum size for merging by %d. Continuing..." %mergingby, waittime=0)
		return True
def checkScanLimit(scanlimit, mergingby):
	try:
		return scanlimit <= SIZE_LIMIT_TABLE[mergingby][1] ## don't want to scan further than the limit
	except KeyError:
		printWarningWithWait("Don't know scan limit for merging by %d. Continuing..." %mergingby, waittime=0)
		return True
def getSizeProfile(meansize, nstreams, profile):
	if profile == 'flat':
		return nstreams*[meansize]
	if nstreams < 2:
		raise RuntimeError('Need at least two streams to make meaningful profile')
	if profile == 'spike' or profile == 'spike05':
		sizeprofile = [0.5*meansize * nstreams]
		for i in xrange(nstreams-1): sizeprofile.append(0.5*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike025':
		sizeprofile = [0.25*meansize * nstreams]
		for i in xrange(nstreams-1): sizeprofile.append(0.75*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike075':
		sizeprofile = [0.75*meansize * nstreams]
		for i in xrange(nstreams-1): sizeprofile.append(0.25*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike08':
		sizeprofile = [0.8*meansize * nstreams]
		for i in xrange(nstreams-1): sizeprofile.append(0.2*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike09':
		sizeprofile = [0.9*meansize * nstreams]
		for i in xrange(nstreams-1): sizeprofile.append(0.1*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike095':
		sizeprofile = [0.95*meansize * nstreams]
		for i in xrange(nstreams-1): sizeprofile.append(0.05*meansize * nstreams/(nstreams-1))
		return sizeprofile

	if profile == 'sawtooth':
		sizes = [1.75, 1.25, 0.75, 0.25]
		sizeprofile = [sizes[i%4]*meansize for i in xrange(nstreams)]
		## need to correct so the sum is still equal to nstreams * meansize
		if nstreams%4 == 1: ## make last one = 1
			sizeprofile[-1] = meansize
		if nstreams%4 == 2: ## make last two 1.5 and 0.5
			sizeprofile[-2] = 1.5*meansize
			sizeprofile[-1] = 0.5*meansize
		if nstreams%4 == 3: ## make last three 1.5, 1.0, and 0.5
			sizeprofile[-3] = 1.5*meansize
			sizeprofile[-2] = 1.0*meansize
			sizeprofile[-1] = 0.5*meansize
		return sizeprofile

	if profile == 'doublespike':
		spikesize    = 0.25*meansize * nstreams
		pedestalsize = 0.5*meansize * nstreams/(nstreams-2)
		return [spikesize]+(nstreams-1)/2*[pedestalsize] + [spikesize]+(nstreams-1)/2*[pedestalsize]
	else:
		raise RuntimeError("Unknown size profile!")

def testBuilding(d2c, minevents=1000, waittime=15, verbose=1, dry=False):
	if verbose > 0: print separator
	if verbose > 0: print 'Testing event building for', waittime, 'seconds...'
	sleep(waittime, verbose, dry)
	if dry: return True
	eventCounter = []
	for n,bu in enumerate(d2c.config.BUs):
		if d2c.config.useEvB: nEvts = getParam(bu.host, bu.port, d2c.config.namespace+'BU', str(n), 'nbEventsBuilt', 'xsd:unsignedInt',  verbose=verbose, dry=dry)
		else:                 nEvts = getParam(bu.host, bu.port, d2c.config.namespace+'BU', str(n), 'eventCounter',  'xsd:unsignedLong', verbose=verbose, dry=dry)
		try:
			eventCounter.append(int(nEvts))
		except ValueError:
			printError('Error getting number of events built. Message was:\n%s'%nEvts)
			return False
		if verbose > 1: print bu.name, 'number of events built: ', int(nEvts)
	print separator

	totEvents = 0
	for evtCount in eventCounter:
		if evtCount < minevents:
			return False
		else:
			totEvents += evtCount
	return True

def sendSOAPMessage(host, port, message, command):
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

def sendCmdFileToExecutivePacked(packedargs):
	(host, port, cmdfile, verbose, dry) = packedargs
	return sendCmdFileToExecutive(host, port, cmdfile, verbose=verbose, dry=dry)
def sendCmdFileToExecutive(host, port, cmdfile, verbose=0, dry=False):
	if dry:
		if verbose > 1: print '%-18s %25s:%-5d %-35s' % ('sendCmdFileToExecutive', host, port, cmdfile)
		return 0

	if not os.path.exists(cmdfile):
		raise IOError('File '+cmdfile+' not found')
	print 'Sending command file to executive %s:%d ...' % (host, port)
	message = 'SOAPAction: urn:xdaq-application:lid=0'
	# if sendSOAPMessage(host, port, message, cmdfile) != 0:
	# 	raise RuntimeError('Failed to send configure command to %s:%d!' % (host, port))
	n_retries = 0
	while sendSOAPMessage(host, port, message, cmdfile) != 0 and n_retries < 3:
		print '  retrying %s:%d ...' % (host, port)
		n_retries += 1

	if n_retries == 3: raise RuntimeError('Failed to send configure command to %s:%d!' % (host, port))
	return 0

def sendCmdFileToApp(host, port, classname, instance, cmdFile, verbose=0, dry=False): ## UNTESTED
	"""Sends a SOAP message contained in cmdfile to the application with classname and instance on host:port"""
	if dry:
		if verbose > 1: print '%-18s %25s:%-5d %25s %1s:\n%s' % ('sendCmdToApp', host, port, classname, instance, cmdFile)
		return

	message = 'SOAPAction: urn:xdaq-application:class=%s,instance=%d' % (classname, instance)
	command = '`cat %s`' % cmdfile
	return sendSOAPMessage(host, port, message, command)

	if not dry: return subprocess.check_call(['sendCmdFileToApp', host, str(port), classname, str(instance), cmdFile])

def sendCmdToApp(host, port, classname, instance, command, verbose=0, dry=False):
	"""Sends a simple command via SOAP to the application with classname and instance on host:port"""
	if dry:
		if verbose > 1: print '%-18s %25s:%-5d %25s %1s:\n%s' % ('sendCmdToApp', host, port, classname, instance, command)
		return 0
	message = 'Content-Location: urn:xdaq-application:class=%s,instance=%d' % (classname, int(instance))
	return sendSOAPMessage(host, port, message, command)

def downloadMeasurements(host, port, classname, instance, outputfile, verbose=0, dry=False):
	if verbose > 1: print separator
	url = 'http://%s:%d/urn:xdaq-application:class=%s,instance=%d/downloadMeasurements'
	url = url % (host, int(port), classname, int(instance))
	if dry: print 'curl -o', outputfile, url
	else: subprocess.check_call(['curl', '-o', outputfile, url])

def tryWebPing(host, port, verbose=0, dry=False):
	if dry:
		print '%-18s %25s:%-5d' % ('webPing', host, port)
		return 0
	cmd = "wget -o /dev/null -O /dev/null --timeout=30 http://%s:%d/urn:xdaq-application:lid=3" % (host,int(port))
	return subprocess.call(shlex.split(cmd))

def stopXDAQPacked(packedargs):
	(host, verbose, dry) = packedargs
	stopXDAQ(host, verbose, dry)
def stopXDAQ(host, verbose=0, dry=False):
	if dry:
		if verbose > 0: print 'Stopping %25s:%-5d' % (host.host, host.lport)
		return
	iterations = 0
	while tryWebPing(host.host, host.port) == 0:
		sendCmdToLauncher(host.host, host.lport, 'STOPXDAQ', verbose=verbose, dry=dry)
		iterations += 1
		if iterations > 1:
			print " repeating %s:%-d" % (host.host, host.port)

def stopXDAQs(symbolMap, verbose=0, dry=False):
	"""Sends a 'STOPXDAQ' cmd to all SOAP hosts defined in the symbolmap that respond to a tryWebPing call"""
	if verbose > 0: print separator
	if verbose > 0: print "Stopping XDAQs"
	from multiprocessing import Pool
	pool = Pool(len(symbolMap.allHosts))
	pool.map(stopXDAQPacked	, [(h, verbose, dry) for h in symbolMap.allHosts])

## Wrappers for existing perl scripts
def sendSimpleCmdToAppPacked(packedargs):
	(host, port, classname, instance, cmdName, verbose, dry) = packedargs
	return sendSimpleCmdToApp(host, port, classname, instance, cmdName, verbose, dry)
def sendSimpleCmdToApp(host, port, classname, instance, cmdName, verbose=0, dry=False):
	if verbose > 1 and dry: print '%-18s %25s:%-5d %25s %1s\t%-12s' % ('sendSimpleCmdToApp', host, port, classname, instance, cmdName)
	if not dry: return subprocess.check_call(['sendSimpleCmdToApp', host, str(port), classname, str(instance), cmdName])

def sendCmdToLauncher(host, port, cmd, verbose=0, dry=False):
	if verbose > 1 and dry: print '%-18s %25s:%-5d %-15s' % ('sendCmdToLauncher', host, port, cmd)
	if not dry: return subprocess.call(['sendCmdToLauncher', host, str(port), cmd])

def setParam(host, port, classname, instance, paramName, paramType, paramValue, verbose=0, dry=False):
	if verbose > 1 and dry: print '%-18s %25s:%-5d %25s %1s\t%-25s %12s %6s' % ('setParam', host, port, classname, instance, paramName, paramType, paramValue)
	if not dry: return subprocess.check_call(['setParam', host, str(port), classname, str(instance), paramName, paramType, str(paramValue)])

def getParam(host, port, classname, instance, paramName, paramType, verbose=0, dry=False):
	if verbose > 1 and dry: print '%-18s %25s:%-5d %25s %1s\t%-25s %12s' % ('getParam', host, port, classname, instance, paramName, paramType)
	if not dry:
		call = subprocess.Popen(['getParam', host, str(port), classname, str(instance), paramName, paramType], stdout=subprocess.PIPE)
		out,err = call.communicate()
		return out

def writeItem(host, port, classname, instance, item, data, offset=0, verbose=0, dry=False):
	body = '<xdaq:WriteItem xmlns:xdaq="urn:xdaq-soap:3.0" offset="%s"  item="%s" data="%s"/>' % (str(offset), item, str(data))
	cmd = SOAPEnvelope % body
	cmd = cmd.replace('\"','\\\"') ## need to escape the quotes when passing as argument
	return sendCmdToApp(host, port, classname, str(instance), cmd)

def getIfStatThroughput(host, duration, delay=5, verbose=0, interface='p2p1', dry=False):
	"""Use Petr's ifstat script to get the throughput every [delay] seconds for a total duration of [duration]"""
	if verbose > 1 and dry: print '%-18s %25s' % ('getIfStatThroughput', host)
	if not dry:
		sshCmd = "ssh -x -n " + host
		count = int(duration/delay) ## calculate number of counts
		cmd  = sshCmd + " \'/nfshome0/pzejdl/scripts/ifstat -b -i %s %d %d\'" % (interface, delay, count)
		if verbose>2: print 'ifstat command:', cmd
		call = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
		sleep(duration+1, verbose=0) ## wait until call should be finished
		call.terminate()
		out,err = call.communicate() ## get output

		samples = []
		for line in out.split('\n')[2:]:
			if len(line) == 0: continue
			samples.append(float(line.split()[0]))

		if verbose>2: print [ '%8.5f'% (x/1e6) for x in samples ]

		total = reduce(lambda x,y:x+y, samples)
		average = float(total/len(samples))
		if verbose>1: print 'Average throughput on %s: %6.2f Gbps' % (host, average/1e6)
		return average
	return None

## Common utilities
def sleep(naptime=0.5,verbose=1,dry=False):
	import time
	from sys import stdout
	if dry:
		if verbose > 0: print 'sleep', naptime
		return

	barlength = len(separator)-1
	starttime = time.time()
	if verbose > 0 and naptime > 0.5:
		stdout.write(''+barlength*' '+'-')
		stdout.write('\r')
		stdout.flush()
	while(time.time() < starttime+naptime):
		time.sleep(naptime/float(barlength))
		if verbose > 0 and naptime > 0.5:
			stdout.write('-')
			stdout.flush()
	if verbose > 0 and naptime > 0.5:
		stdout.write('-')
		stdout.flush()
		stdout.write('\r' + (barlength+5)*' ')
		stdout.write('\r')
		stdout.flush()

def printError(message, instance=None):
	errordelim = 40*'>>'
	print errordelim
	if instance != None:
		print ">> %s >> %s" % (instance.__class__.__name__, message)
	else:
		print ">> %s" % (message)
	print errordelim

def printWarningWithWait(message, waitfunc=sleep, waittime=10, instance=None):
	errordelim = 40*'>>'
	print errordelim
	if instance != None: print ">> %s >>" % (instance.__class__.__name__)
	print message
	if waittime > 0:
		print " will wait for you to read this for", waittime ,"s and then continue..."
		if waitfunc==None:
			from time import sleep
			sleep(waittime)
		else: waitfunc(waittime)
	print errordelim

def sendToHostListInParallel(hostlist, func, commonargs):
	tasklist = [(host.host, host.port,)+tuple(commonargs) for host in hostlist]

	from multiprocessing import Pool
	pool = Pool(len(hostlist))
	try:
		pool.map(func, tasklist)
		return True
	except RuntimeError:
		return False


def getFerolDelay(fragSize, rate='max'):
	"""Calculates the Event_Delay_ns parameter for the FEROLs, for a given size and rate
  - rate='max' will return 20
  - the minimum return value is 20
"""
	if rate == 'max': return 20
	else:
		################################################
		delay = int(1000000.0 / rate - fragSize/8.0*6.4)
		################################################
		if delay < 20:
			printWarningWithWait("Delay for %d size and %.0f kHz rate would be below 20 ns (%.0f). Setting it to 20 ns instead." %(fragSize,rate,delay), waittime=0)
			return 20
		return delay



##########################################
## From Petr's FEROL.py ##################
##########################################
## Parse json file with FEROL monitoring variables and returns a dictionary
def parseMonitoringJsonFile(jsonFile):
	d = dict()
	for line in jsonFile.readlines():
		mo = re.match(r".*\"name\":\"(.*)\",.*\"value\":\"(.*)\".*", line)
		if mo:
			d[mo.group(1)] = mo.group(2)
	return d

## Returns a dictionary with FEROL monitoring items. It is read from a json url
def loadMonitoringItemsFromURL(url):
	import urllib2
	opener = urllib2.urlopen(url + "/infospaces")
	items = parseMonitoringJsonFile(opener)
	opener.close()
	return items

