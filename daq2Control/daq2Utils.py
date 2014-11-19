#! /usr/bin/env python
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
	 1 : (64000, 32768),  # merging by  1
	 4 : (32000, 32768),  # merging by  4
	 8 : (32000, 32768),  # merging by  8
	12 : (21000, 32768),  # merging by 12
	16 : (16000,  8192),  # merging by 16
	20 : (12800,  6400),  # merging by 20
	24 : (10500,  5120),  # merging by 24
	32 : ( 8000,  4096)   # merging by 32
}
def checkMaxSize(maxsize, mergingby):
	try:
		return maxsize == SIZE_LIMIT_TABLE[mergingby][0]
	except KeyError:
		printWarningWithWait("Don't know maximum size for merging by %d. "
			                 "Continuing..." %mergingby, waittime=0)
		return True
def checkScanLimit(scanlimit, mergingby):
	try:
		## don't want to scan further than the limit
		return scanlimit <= SIZE_LIMIT_TABLE[mergingby][1]
	except KeyError:
		printWarningWithWait("Don't know scan limit for merging by %d. "
			                 "Continuing..." %mergingby, waittime=0)
		return True
def getSizeProfile(meansize, nstreams, profile):
	if profile == 'flat':
		return nstreams*[meansize]
	if nstreams < 2:
		raise RuntimeError('Need at least two streams to make meaningful '
			               'profile')
	if profile == 'spike' or profile == 'spike05':
		sizeprofile = [0.5*meansize * nstreams]
		for i in xrange(nstreams-1):
			sizeprofile.append(0.5*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike025':
		sizeprofile = [0.25*meansize * nstreams]
		for i in xrange(nstreams-1):
			sizeprofile.append(0.75*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike075':
		sizeprofile = [0.75*meansize * nstreams]
		for i in xrange(nstreams-1):
			sizeprofile.append(0.25*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike08':
		sizeprofile = [0.8*meansize * nstreams]
		for i in xrange(nstreams-1):
			sizeprofile.append(0.2*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike09':
		sizeprofile = [0.9*meansize * nstreams]
		for i in xrange(nstreams-1):
			sizeprofile.append(0.1*meansize * nstreams/(nstreams-1))
		return sizeprofile
	if profile == 'spike095':
		sizeprofile = [0.95*meansize * nstreams]
		for i in xrange(nstreams-1):
			sizeprofile.append(0.05*meansize * nstreams/(nstreams-1))
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
		size_list = [spikesize]+(nstreams-1)/2*[pedestalsize]
		size_list += [spikesize]+(nstreams-1)/2*[pedestalsize]
		return size_list
	else:
		raise RuntimeError("Unknown size profile!")

def testBuilding(d2c, minevents=1000, waittime=15, verbose=1, dry=False):
	if verbose > 0: print separator
	if verbose > 0: print 'Testing event building for', waittime, 'seconds...'
	sleep(waittime, verbose, dry)
	if dry: return True
	eventCounter = []
	events = []
	if not d2c.config.useMSIO:
		for n,bu in enumerate(d2c.config.BUs):
			if d2c.config.useEvB:
				nEvts = getParam(bu.host, bu.port, d2c.config.namespace+'BU',
					             str(n), 'nbEventsBuilt', 'xsd:unsignedLong',
					             verbose=verbose, dry=dry)
			else:
				nEvts = getParam(bu.host, bu.port, d2c.config.namespace+'BU',
					             str(n), 'eventCounter',  'xsd:unsignedLong',
					             verbose=verbose, dry=dry)
			events.append((bu.name, nEvts))
	else: ## mstreamio
		for n,bu in enumerate(d2c.config.BUs):
			nEvts = getParam(bu.host, bu.port, 'Server',
				             str(n), 'counter',  'xsd:unsignedLong',
				             verbose=verbose, dry=dry)
			events.append((bu.name, nEvts))

	for name,nEvts in events:
		try:
			eventCounter.append(int(nEvts))
		except ValueError:
			printError('Error getting number of events built.'
				       'Message was:\n%s'%nEvts)
			return False
		if verbose > 1:
			print name, 'number of events built: ', int(nEvts)

	if verbose > 1: print separator


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
		'Content-Location: urn:xdaq-application:class=CLASSNAME,
		                                        instance=INSTANCE'
		and command could be a file:
		configure.cmd.xml
		or a simple command like:
		'Configure'
	"""
	cmd = ("curl --stderr /dev/null -H \"Content-Type: text/xml\" "
	       "-H \"Content-Description: SOAP Message\" "
	       "-H \"%s\" http://%s:%d -d %s")

	# 'SOAPAction: urn:xdaq-application:lid=0' ## ??

	if 'SOAPAction' in message:
		## Want to send a command file, i.e. need to prepend a \@
		## before the filename
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
	return sendCmdFileToExecutive(host, port, cmdfile,
		                          verbose=verbose, dry=dry)
def sendCmdFileToExecutive(host, port, cmdfile, verbose=0, dry=False):
	if dry:
		if verbose > 1:
			print '%-18s %25s:%-5d %-35s' % ('sendCmdFileToExecutive',
				                             host, port, cmdfile)
		return 0

	if not os.path.exists(cmdfile):
		raise IOError('File '+cmdfile+' not found')
	print 'Sending command file to executive %s:%d ...' % (host, port)
	message = 'SOAPAction: urn:xdaq-application:lid=0'
	n_retries = 0
	while (sendSOAPMessage(host, port, message, cmdfile) != 0
		   and n_retries < 3):
		print '  retrying %s:%d ...' % (host, port)
		n_retries += 1

	if n_retries == 3:
		raise RuntimeError('Failed to send configure command to %s:%d!' % (
			                                                   host, port))
	return 0
def sendCmdFileToApp(host, port, classname, instance, cmdFile,
                     verbose=0, dry=False): ## UNTESTED
	"""Sends a SOAP message contained in cmdfile to the application
with classname and instance on host:port"""
	if dry:
		if verbose > 1:
			print '%-18s %25s:%-5d %25s %1s:\n%s' % (
				  'sendCmdToApp', host, port, classname, instance, cmdFile)
		return

	message = 'SOAPAction: urn:xdaq-application:class=%s,instance=%d' % (
		                                             classname, instance)
	command = '`cat %s`' % cmdfile
	return sendSOAPMessage(host, port, message, command)

	if not dry:
		return subprocess.check_call(['sendCmdFileToApp', host, str(port),
			                           classname, str(instance), cmdFile])
def sendCmdToApp(host, port, classname, instance, command,
	             verbose=0, dry=False):
	"""Sends a simple command via SOAP to the application with classname
and instance on host:port"""
	if dry:
		if verbose > 1:
			print '%-18s %25s:%-5d %25s %1s:\n%s' % (
				  'sendCmdToApp', host, port, classname, instance, command)
		return 0
	message = 'Content-Location: urn:xdaq-application:class=%s,instance=%d'%(
		                                            classname, int(instance))
	return sendSOAPMessage(host, port, message, command)
def writeItem(host, port, classname, instance, item, data, offset=0,
	          verbose=0, dry=False):
	body = ('<xdaq:WriteItem xmlns:xdaq="urn:xdaq-soap:3.0" offset="%s"  '
		    'item="%s" data="%s"/>' % (str(offset), item, str(data)))
	cmd = SOAPEnvelope % body
	cmd = cmd.replace('\"','\\\"') ## escape the quotes when passing as arg
	return sendCmdToApp(host, port, classname, str(instance), cmd,
	                    verbose=verbose, dry=dry)
def tryWebPing(host, port, verbose=0, dry=False):
	if dry:
		print '%-18s %25s:%-5d' % ('webPing', host, port)
		return 0
	cmd = ("wget -o /dev/null -O /dev/null --timeout=30 "
	       "http://%s:%d/urn:xdaq-application:lid=3" % (host,int(port)))
	if verbose>0: print 'Checking %25s:%-5d' % (host,int(port))
	return subprocess.call(shlex.split(cmd))

def checkApplicationState(host, classname, instance, statename, dry=False):
	## Special case until stateName is added to the application infospace
	## in the FerolController
	if dry: return True
	if host.type == 'FEROLCONTROLLER':
		url = 'http://%s:%d/urn:xdaq-application:lid=109' % (
			                            host.host, host.port)
		items = loadMonitoringItemsFromURL(url)
		state = items['stateName']
		if not state == statename:
			stdout.write('\n')
			printError('Application %s, instance %d, on host %s:%-d, did '
				       'not return state "%s", instead was "%s".' %(
				       	classname, instance, host.host, host.port,
				       	statename, state))
			return False
		return True

	## Normal case
	state = getParam(host.host, host.port, classname, instance,
		             'stateName', 'xsd:string')
	state = state.strip('\n') ## remove trailing newlines
	if not state == statename:
		stdout.write('\n')
		printError('Application %s, instance %d, on host %s:%-d, did not '
			       'return state "%s", instead was "%s".' % (
			       	classname, instance, host.host, host.port,
			       	statename, state))
		return False
	return True

def checkStates(hosts, statename, verbose=0, dry=False):
	"""Checks a fixed list of applications on hosts to be in statename"""
	applications_to_check = {
		'FEROLCONTROLLER' : ['ferol::FerolController'],
		'FEROL'           : ['Client', 'evb::test::DummyFEROL'],
		'RU'              : ['evb::EVM', 'evb::RU', 'gevb2g::RU'],
		'BU'              : ['evb::BU', 'gevb2g::BU'],
		'EFED'            : ['d2s::FEDEmulator'],
		'GTPE'            : ['d2s::GTPeController'],
		'FMM'             : ['tts::FMMController']}
	for host in hosts:
		for app,inst in host.applications:
			if not app in applications_to_check[host.type]: continue

			if verbose > 0:
				stdout.write('Checking whether application %s(%d) on '
					         '%s:%d is in state "%s" ... ' % (
					         app, inst, host.host, host.port, statename))
			if not checkApplicationState(host, app, inst, statename,
				                         dry=dry):
				if verbose > 0: stdout.write(' FAILED\n')
				return False
			if verbose > 0: stdout.write(' OK\n')
	return True

def stopXDAQPacked(packedargs):
	(host, verbose, dry) = packedargs
	stopXDAQ(host, verbose, dry)
def stopXDAQ(host, verbose=0, dry=False):
	if dry:
		if verbose > 0: print 'Stopping %25s:%-5d' % (host.host, host.lport)
		return

	iterations = 0
	while tryWebPing(host.host, host.port) == 0:
		sendCmdToLauncher(host.host, host.lport, 'STOPXDAQ',
			              verbose=verbose, dry=dry)
		iterations += 1
		if iterations > 1 and iterations < 3:
			print " repeating %s:%-d" % (host.host, host.port)
		if iterations > 2:
			break

def stopXDAQs(symbolMap, verbose=0, dry=False):
	"""Sends a 'STOPXDAQ' cmd to all SOAP hosts defined in the symbolmap
that respond to a tryWebPing call"""
	if verbose > 0: print separator
	if verbose > 0: print "Stopping XDAQs"
	pauseGTPe(symbolMap, verbose=verbose, dry=dry)
	from multiprocessing import Pool
	pool = Pool(len(symbolMap.allHosts))
	pool.map(stopXDAQPacked,
		     [(h, verbose, dry) for h in symbolMap.allHosts])
def pauseGTPe(symbolMap, verbose=0, dry=False):
	if dry: return
	try:
		gtpe = symbolMap("GTPE0")
		if tryWebPing(gtpe.host, gtpe.port) == 0:
			if verbose>1: print 'Trying to pause GTPe.'
			sendSimpleCmdToApp(gtpe.host, gtpe.port, 'd2s::GTPeController',
				               '0', 'Pause', verbose=verbose, dry=dry)
			sleep(2, verbose=0, dry=dry)
		else:
			if verbose>1: print 'GTPe not running.'
	except KeyError: ## no GTPe defined in symbolmap
		pass

## Wrappers for existing perl scripts
def sendSimpleCmdToAppPacked(packedargs):
	(host, port, classname, instance, cmdName, verbose, dry) = packedargs
	return sendSimpleCmdToApp(host, port, classname, instance, cmdName,
		                      verbose, dry)
def sendSimpleCmdToApp(host, port, classname, instance, cmdName,
	                   verbose=0, dry=False):
	if verbose > 1 and dry:
		print '%-18s %25s:%-5d %25s %1s\t%-12s' % (
			  'sendSimpleCmdToApp', host, port, classname, instance, cmdName)
	if not dry:
		return subprocess.check_call(['sendSimpleCmdToApp', host, str(port),
			                             classname, str(instance), cmdName])
def sendCmdToLauncher(host, port, cmd, verbose=0, dry=False):
	if verbose > 1 and dry:
		print '%-18s %25s:%-5d %-15s'%('sendCmdToLauncher', host, port, cmd)
	if not dry:
		return subprocess.call(['sendCmdToLauncher', host, str(port), cmd])
def setParam(host, port, classname, instance, paramName, paramType,
	         paramValue, verbose=0, dry=False):
	if verbose > 1 and dry:
		print '%-18s %25s:%-5d %25s %1s\t%-25s %12s %6s' % (
			           'setParam', host, port, classname, instance,
			           paramName, paramType, paramValue)
	if not dry:
		return subprocess.check_call(['setParam', host, str(port), classname,
			                          str(instance), paramName, paramType,
			                          str(paramValue)])
def getParam(host, port, classname, instance, paramName, paramType,
	         verbose=0, dry=False):
	if verbose > 1 and dry:
		print '%-18s %25s:%-5d %25s %1s\t%-25s %12s' % (
			            'getParam', host, port, classname, instance,
			            paramName, paramType)
	if not dry:
		call = subprocess.Popen(['getParam', host, str(port), classname,
			                     str(instance), paramName, paramType],
			                     stdout=subprocess.PIPE)
		out,err = call.communicate()
		return out

def getIfStatThroughput(host, duration, delay=5, verbose=0, interface='p2p1',
	                    dry=False):
	"""Use Petr's ifstat script to get the throughput every [delay] seconds
for a total duration of [duration]"""
	if verbose > 1 and dry:
		print '%-18s %25s' % ('getIfStatThroughput', host)
	if not dry:
		sshCmd = "ssh -x -n " + host
		count = int(duration/delay) ## calculate number of counts
		cmd = sshCmd
		cmd += " \'/nfshome0/pzejdl/scripts/ifstat -b -i %s %d %d\'" % (
			                                        interface, delay, count)
		if verbose>2: print 'ifstat command:', cmd
		call = subprocess.Popen(cmd, stdout=subprocess.PIPE,
			                         stderr=subprocess.PIPE, shell=True)
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
		if verbose>1:
			print 'Average throughput on %s: %6.2f Gbps'%(host, average/1e6)
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
def printProgress(step, total, customstr=''):
	stdout.write("\r%s[%3d %%]" % (customstr, 100*float(step+1)/float(total)) )
	stdout.flush()


def sendSSHCommandPacked(packedargs):
	host,_,cmd,verbose,dry = packedargs
	return sendSSHCommand(host,cmd,verbose=verbose,dry=dry)
def sendSSHCommand(host,cmd,verbose=1,dry=False):
	cmd = 'ssh %s "%s"' % (host,cmd)
	if dry:
		if verbose>0: print cmd
		return
	call = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
	out,err = call.communicate()
	if verbose>3:
		print out.strip()
	return out


def printError(message, instance=None):
	errordelim = 40*'>>'
	print errordelim
	if instance != None:
		print ">> %s >> %s" % (instance.__class__.__name__, message)
	else:
		print ">> %s" % (message)
	print errordelim
def printWarningWithWait(message, waitfunc=sleep, waittime=10,
	                     instance=None):
	errordelim = 40*'>>'
	print errordelim
	if instance != None: print ">> %s >>" % (instance.__class__.__name__)
	print message
	if waittime > 0:
		if waitfunc==None:
			from time import sleep
			sleep(waittime)
		else: waitfunc(waittime)
	print errordelim

def sendToHostListInParallel2(hostlist, func, commonargs):
	tasklist = [(host.host, host.port,)+tuple(commonargs)
	                                   for host in hostlist]

	from multiprocessing import Pool
	pool = Pool(len(hostlist))
	try:
		pool.map(func, tasklist)
		return True
	except RuntimeError:
		return False

def sendToHostListInParallel(hostlist, func, individualargs, commonargs):
	if not len(hostlist) == len(individualargs):
		printWarningWithWait("sendToHostListInParallel: Different length of "
			       "hostlist and argument list!", waittime=1)
	hostarglist = zip(hostlist, individualargs)
	tasklist = [(host.host, host.port, iarg)+tuple(commonargs)
	                                   for host,iarg in hostarglist]

	from multiprocessing import Pool
	pool = Pool(len(hostlist))
	try:
		pool.map(func, tasklist)
		return True
	except RuntimeError:
		return False


def getFerolDelay(fragSize, rate='max'):
	"""Calculates the Event_Delay_ns parameter for the FEROLs, for a given
size and rate
  - rate='max' will return 20
  - the minimum return value is 20
"""
	if rate == 'max': return 20
	else:
		################################################
		delay = int(1000000.0 / rate - fragSize/8.0*6.4)
		################################################
		if delay < 20:
			printWarningWithWait("Delay for %d size and %.0f kHz rate would "
				                 "be below 20 ns (%.0f). Setting it to 20 "
				                 "ns instead." %(fragSize,rate,delay),
				                 waittime=0)
			return 20
		return delay

def getConfig(string=""):
	"""Extract number of streams, readout units, builder units, and RMS from
strings such as	8x1x2 or 16s8fx2x4_RMS_0.5 (i.e 8,1,2,None in the first
case, 16,2,4,0.5 in the second)
	"""
	string = string.split('_')
	case = string[0].split('x')
	rms = None
	strperfrl = 1
	pattern = re.compile(r'([0-9]+)s([0-9]+)f')
	if pattern.match(case[0]):
		nstreams = int(pattern.match(case[0]).group(1))
		if nstreams > int(pattern.match(case[0]).group(2)): strperfrl = 2

	else: nstreams = int(case[0])
	nrus = int(case[1]) ## Introduces notation: no _ before the trailing tags
	nbus = int(case[2])

	for i in xrange(len(string)):
		if string[i] == 'RMS':
			try:
				rms = float(string[i+1])
			except ValueError, StopIteration:
				print 'RMS needs to be a floating point number'
				rms = None

	return nstreams, nrus, nbus, rms, strperfrl

def getGitHashTag():
	"""Returns the git hash of the current commit in the scripts
repository"""
	## this will be /nfshome0/.../daq2val/daq2Control/
	gitwd = os.path.dirname(os.path.realpath(__file__))
	cmd = r"git log --pretty=format:'%H' -n 1"
	try:
		call = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE,
			                    cwd=gitwd)
		out,err = call.communicate()
		return out
	except OSError:
		return '???'

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

## Returns a dictionary with FEROL monitoring items.
## It is read from a json url
def loadMonitoringItemsFromURL(url):
	import urllib2
	opener = urllib2.urlopen(url + "/infospaces")
	items = parseMonitoringJsonFile(opener)
	opener.close()
	return items

