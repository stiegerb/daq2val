#! /usr/bin/env python
import re, os, socket
from optparse import OptionParser
from subprocess import call

def isComment(line):
	return line.strip().startswith('#') or len(line.strip())==0

def getEnv(line):
	env = re.findall(r'\s*env=(\s*[A-Z0-9]*)', line)
	if len(env) > 0:
		return env[0]
	else: return None

def getHosts(line):
	hosts = re.findall(r'\s*hosts=([^=]+)$', line)
	if len(hosts) > 0:
		hosts = hosts[0].split(',')
		hosts = map(lambda x:x.strip(), hosts)
		return hosts
	elif line.strip() == 'default':
		return ['default']
	else: return []

def getCores(line):
	cores = re.findall(r'\s*cores=([0-9,]+)$', line)
	if len(cores) > 0:
		return cores[0]
	else: return None

def getCPU(line):
	cpu = re.findall(r'cpu=([0-9])', line) ## cpu=N where N is a single digit number
	if len(cpu) > 0:
		return cpu[0]
	else: return None

def getNumaCtl(line):
	numactl = re.findall(r'\s*numactl=\s*(.*)\s*$', line)
	if len(numactl) > 0:
		return numactl[0]
	else: return None

def getNumaCommand(hostname, testtype, config='numactl.config'):
	error = 'numa control config for %s in test type %s not found' % (hostname, testtype)
	with open(config, 'r') as file:
		for line in file:
			if getEnv(line) != testtype: continue
			line = next(file, 'EOF') ## found the test type

			while hostname not in getHosts(line):
				if 'default' in getHosts(line): break
				if getEnv(line) is not None or line == 'EOF':
					print error
					return None

				line = next(file, 'EOF')

			line = next(file, 'EOF')
			numacmd = 'numactl'

			while True:
				if isComment(line):
					line = next(file, 'EOF')
					continue
				elif getCores(line):
					numacmd += ' --physcpubind=%s' % getCores(line)
					line = next(file, 'EOF')
				elif getCPU(line):
					numacmd += ' --membind=%s' % getCPU(line)
					line = next(file, 'EOF')
				elif getNumaCtl(line):
					numacmd = getNumaCtl(line)
					line = next(file, 'EOF')
				else: break

			if numacmd == 'numactl':
				print error
				return None
			return numacmd
	print error
	return None


if __name__ == "__main__":
	usage = """Usage: %prog

	Returns numactl command string for local hostname.
	Called without arguments it checks for TEST_TYPE environment variable
	and reads configurations from 'numactl.config'.
	"""
	parser = OptionParser(usage=usage)
	parser.add_option("-c", "--config", default="numactl.config",
	                  action="store", type="string", dest="config",
	                  help="Numa control config file [default: %default]")
	parser.add_option("-n", "--hostname",
	                  action="store", type="string", dest="hostname",
	                  help="Host name to be queried [default: local hostname]")
	parser.add_option("-t", "--testtype",
	                  action="store", type="string", dest="testtype",
	                  help="Test type, as defined in env=XYZ of numa control config [default: environment variable TEST_TYPE]")
	(options, args) = parser.parse_args()


	if not options.hostname:
		options.hostname = socket.gethostname()

	if not options.testtype:
		try:
			options.testtype = os.environ['TEST_TYPE']
		except KeyError:
			print 'Test type not found. Provide either -t argument or TEST_TYPE environment variable'
			exit(-1)


	print getNumaCommand(options.hostname, options.testtype, options.config)
