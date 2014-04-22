#! /usr/bin/env python
import shlex
import subprocess
from daq2SymbolMap import daq2SymbolMap
from daq2Utils import sleep
from os.path import expanduser
import sys

def getIP(hostname):
	digcall = subprocess.Popen(['dig', '+short', hostname], stdout=subprocess.PIPE)
	ip,_ = digcall.communicate()
	return ip.strip()

def clearSSHKey(hostname, dry=False):
	ip = getIP(hostname)
	hostname = hostname.strip()
	print '  Clearing', hostname
	if dry:
		print 'ssh-keygen -R %s' % hostname
		print 'ssh-keygen -R %s' % ip
		return
	else:
		call = subprocess.Popen(['ssh-keygen', '-R', ip])
		call = subprocess.Popen(['ssh-keygen', '-R', hostname])

def getSSHKey(sshfile, hostname, dry=False):
	ip = getIP(hostname)
	hostname = hostname.strip()
	print '  Adding', hostname
	if dry:
		print 'ssh-keyscan -H %s >> %s' % (ip, sshfile.name)
		print 'ssh-keyscan -H %s >> %s' % (hostname, sshfile.name)
		return
	else:
		call = subprocess.Popen(['ssh-keyscan', '-H', ip], stdout=sshfile)
		call = subprocess.Popen(['ssh-keyscan', '-H', hostname], stdout=sshfile)

if __name__ == "__main__":
	from optparse import OptionParser
	usage = """"""
	parser = OptionParser(usage=usage)
	parser.add_option("-d", "--dry", default=False,
		               action="store_true", dest="dry",
		               help=("Dry running [default: %default]"))
	(opt, args) = parser.parse_args()

	sm = daq2SymbolMap(args[0])
	sshfilename = expanduser('~/.ssh/known_hosts')
	with open(sshfilename, 'a') as sshfile:
		for key in sm.keys():
			if not 'SOAP_HOST_NAME' in key: continue
			getSSHKey(sshfile, sm(key), dry=opt.dry)

	sleep(1)
	# print 'Clearing duplicate entries'
	# for key in sm.keys():
	# 	if not 'SOAP_HOST_NAME' in key: continue
	# 	clearSSHKey(sm(key), dry=opt.dry)

	# sleep(1)
	print '=== DONE ==='

	exit(0)
