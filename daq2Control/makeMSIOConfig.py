#! /usr/bin/env python
import os
from daq2MSIOConfigurator import daq2MSIOConfigurator
from daq2Utils import getConfig, printWarningWithWait, printError

def addConfiguratorOption(parser):
	parser.add_option("-d", "--setDynamicIBVConfig", default=False,
		              action="store_true", dest="setDynamicIBVConfig",
		              help="Set the senderPoolSize, receiverPoolSize, "
		                   "completionQueueSize, sendQueuePairSize, "
		                   "and recvQueuePairSize parameters of the "
		                   "pt::ibv::Application dynamically according "
		                   "to Andys algorithm. If not set, take "
		                   "everything from fragment.")
	parser.add_option("--cP", "--clientSendPoolSize", default=None,
		              action="store", type="int", dest="clientSendPoolSize",
		              help="Set the sendPoolSize parameter on the MStreamIO "
		                   "client (in MBytes, default: %default)")
	parser.add_option("--cQ", "--clientSendQPSize", default=None,
		              action="store", type="int", dest="clientSendQPSize",
		              help="Set the sendQueuePairSize parameter on the "
		                   "MStreamIO client [default %default]")
	parser.add_option("--cCQ", "--clientComplQPSize", default=None,
		              action="store", type="int", dest="clientComplQPSize",
		              help="Set the complQueuePairSize parameter on the "
		                   "MStreamIO client [default %default]")
	parser.add_option("--sP", "--serverRecvPoolSize", default=None,
		              action="store", type="int", dest="serverRecvPoolSize",
		              help="Set the recvPoolSize parameter on the MStreamIO "
		                   "server (in MBytes, default: %default)")
	parser.add_option("--sQ", "--serverRecvQPSize", default=None,
		              action="store", type="int", dest="serverRecvQPSize",
		              help="Set the recvQueuePairSize parameter on the "
		                   "MStreamIO server [default %default]")
	parser.add_option("--sCQ", "--serverComplQPSize", default=None,
		              action="store", type="int", dest="serverComplQPSize",
		              help="Set the complQueuePairSize parameter on the "
		                   "MStreamIO server [default %default]")
	parser.add_option("--useGevb2g", default=False, action="store_true",
		              dest="useGevb2g",
		              help="Use gevb2g for event building (instead of EvB)")
	parser.add_option("--fragmentDir", default='', action="store",
		              type="string", dest="fragmentDir",
		              help=("Use config fragments from a directory other "
		                    "than the default"))
	parser.add_option("-v", "--verbose", default=1, action="store",
		              type='int', dest="verbose",
		              help=("Set the verbose level, [default: %default "
		              		"(semi-quiet)]"))
	parser.add_option("-o", "--output", default='', action="store",
		              type='string', dest="output",
		              help="Where to put the output file")

def getMSIOConfig(string=""):
	"""Extract number of streams, readout units, builder units, and RMS
	   from strings such as	8x1x2 or 16s8fx2x4_RMS_0.5
	   (i.e 8,1,2,None in the first case, 16,2,4,0.5 in the second)
	"""
	try:
		nClie, nServ = tuple([int(x) for x in string.split('x')])
		return nClie, nServ
	except:
		print "There was an error?"



def main(options, args):
	nClients, nServers = getMSIOConfig(args[0])

	if len(options.fragmentDir) == 0:
		# By default take the config_fragments dir from the current release
		workingdir = os.path.dirname(os.path.realpath(__file__))
		options.fragmentDir = os.path.join(workingdir,'config_fragments')

	configurator = daq2MSIOConfigurator(options.fragmentDir,
		                                verbose=options.verbose)

	configurator.evbns = 'msio'
	if options.useGevb2g: configurator.evbns = 'gevb2g'

	## Pass options
	configurator.clientSendPoolSize = options.clientSendPoolSize
	configurator.clientSendQPSize   = options.clientSendQPSize
	configurator.clientComplQPSize  = options.clientComplQPSize
	configurator.serverRecvPoolSize = options.serverRecvPoolSize
	configurator.serverRecvQPSize   = options.serverRecvQPSize
	configurator.serverComplQPSize  = options.serverComplQPSize

	configurator.setDynamicIBVConfig = options.setDynamicIBVConfig

	## Construct output name
	output = args[0]
	if not options.useGevb2g:
		output += '_msio'
	else:
		output += '_gevb2g'
	output+='_ibv'
	output+='.xml'

	if len(options.output)>0:
		name, ext = os.path.splitext(options.output)
		if not os.path.dirname(name) == '':
			try:
				os.makedirs(os.path.dirname(name))
			except OSError as e:
				if not 'File exists' in str(e):
					raise e

		if ext == '.xml':
			# Take exactly what's given in the option
			output = options.output
		elif ext == '':
			output = os.path.join(name, output)

	configurator.makeMSIOConfig(nClients, nServers, output)

	return True

if __name__ == "__main__":
	from optparse import OptionParser
	usage = """
	%prog [options] topology
	where topology is in the format of nClients x nServers,
	e.g. 4x2

	Examples:
	%prog --useGevb2g 4x4
	%prog 2x4 --fragmentDir fragments/ -o 2x4_special.xml
	"""
	parser = OptionParser()
	parser.usage = usage
	addConfiguratorOption(parser)
	(options, args) = parser.parse_args()

	if len(args) > 0:
		if main(options, args):
			exit(0)
		else:
			printError("Something went wrong.")

	parser.print_help()
	exit(-1)

