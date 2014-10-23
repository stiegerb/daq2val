#! /usr/bin/env python
import os
from daq2EvBIEConfigurator import daq2EvBIEConfigurator
from daq2Utils import getConfig, printWarningWithWait, printError

from makeDAQ2Config import getNxNConfig

def addConfiguratorOption(parser):
	parser.add_option("-d", "--setDynamicIBVConfig", default=False,
		              action="store_true", dest="setDynamicIBVConfig",
		              help="Set the senderPoolSize, receiverPoolSize, "
		                   "completionQueueSize, sendQueuePairSize, "
		                   "and recvQueuePairSize parameters of the "
		                   "pt::ibv::Application dynamically according "
		                   "to an algorithm. If not set, take everything "
		                   "from fragment.")
	parser.add_option("--mS", "--maxMessageSize", default=None,
		              action="store", type="int", dest="maxMessageSize",
		              help="Set the maxMessageSize parameter in the IBV "
		                   "configuration (in Bytes, default: 128kB)")
	parser.add_option("--cP", "--RUSendPoolSize", default=None,
		              action="store", type="int", dest="RUSendPoolSize",
		              help="Set the sendPoolSize parameter on the MStreamIO "
		                   "RU (in MBytes, default: %default)")
	parser.add_option("--cQ", "--RUSendQPSize", default=None,
		              action="store", type="int", dest="RUSendQPSize",
		              help="Set the sendQueuePairSize parameter on the "
		                   "MStreamIO RU [default %default]")
	parser.add_option("--cCQ", "--RUComplQPSize", default=None,
		              action="store", type="int", dest="RUComplQPSize",
		              help="Set the complQueuePairSize parameter on the "
		                   "MStreamIO RU [default %default]")
	parser.add_option("--sP", "--BURecvPoolSize", default=None,
		              action="store", type="int", dest="BURecvPoolSize",
		              help="Set the recvPoolSize parameter on the MStreamIO "
		                   "BU (in MBytes, default: %default)")
	parser.add_option("--sQ", "--BURecvQPSize", default=None,
		              action="store", type="int", dest="BURecvQPSize",
		              help="Set the recvQueuePairSize parameter on the "
		                   "MStreamIO BU [default %default]")
	parser.add_option("--sCQ", "--BUComplQPSize", default=None,
		              action="store", type="int", dest="BUComplQPSize",
		              help="Set the complQueuePairSize parameter on the "
		                   "MStreamIO BU [default %default]")
	parser.add_option("--maxEUC", "--maxEvtsUnderConstruction", default=None,
		              action="store", type="int", dest="maxEvtsUnderConstruction",
		              help="Set the maxEvtsUnderConstruction parameter on the "
		                   "EvB BU [default %default]")
	parser.add_option("--nBuilders", "--numberOfBuilders", default=None,
		              action="store", type="int", dest="numberOfBuilders",
		              help="Set the numberOfBuilders parameter on the "
		                   "EvB BU [default %default]")
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
	parser.add_option("-r", "--setRate", default=0,
		              action="store", type="int", dest="setRate",
		              help="Set maxTriggerRate parameter (in Hz) "
		                   "[default %default]")

def main(options, args):
	nRUs, nBUs = getNxNConfig(args[0])

	if len(options.fragmentDir) == 0:
		# By default take the config_fragments dir from the current release
		workingdir = os.path.dirname(os.path.realpath(__file__))
		options.fragmentDir = os.path.join(workingdir,'config_fragments')

	configurator = daq2EvBIEConfigurator(options.fragmentDir,
		                                verbose=options.verbose)

	configurator.evbns = 'evb'

	## Pass options
	configurator.RUSendPoolSize = options.RUSendPoolSize
	configurator.RUSendQPSize   = options.RUSendQPSize
	configurator.RUComplQPSize  = options.RUComplQPSize
	configurator.BURecvPoolSize = options.BURecvPoolSize
	configurator.BURecvQPSize   = options.BURecvQPSize
	configurator.BUComplQPSize  = options.BUComplQPSize

	configurator.maxEvtsUnderConstruction = options.maxEvtsUnderConstruction
	configurator.numberOfBuilders = options.numberOfBuilders
	configurator.setRate = options.setRate
	configurator.maxMessageSize = options.maxMessageSize

	configurator.setDynamicIBVConfig = options.setDynamicIBVConfig

	## Construct output name
	output = args[0]
	output += '_evb'
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

	configurator.makeEvBIEConfig(nRUs, nBUs, output)

	return True

if __name__ == "__main__":
	from optparse import OptionParser
	usage = """
	%prog [options] topology
	where topology is in the format of nRUs x nBUs,
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

