#! /usr/bin/env python
from daq2Configurator import daq2Configurator
from daq2Utils import getConfig

if __name__ == "__main__":
	from optparse import OptionParser
	usage = """
	%prog [options] topology
	where topology is in the format of nStreams x nFerols x nRUs x nBUs, e.g. 16s8fx1x4

	Examples:
	%prog --useIBV 24s12fx2x4
	%prog --setCWND 135000 --disablePauseFrame 32s16fx2x4
	"""
	parser = OptionParser()
	parser.usage = usage
	parser.add_option("--setCWND",           default=-1,    action="store",      type='int', dest="setCWND",           help="Set the TCP_CWND_FEDX parameter in the FEROL config [default: take from config fragment]")
	parser.add_option("--disablePauseFrame", default=False, action="store_true",             dest="disablePauseFrame", help="Set the ENA_PAUSE_FRAME parameter in the FEROL config to 'false' [default: take from config fragment]")
	parser.add_option("--enablePauseFrame",  default=False, action="store_true",             dest="enablePauseFrame",  help="Set the ENA_PAUSE_FRAME parameter in the FEROL config to 'true'")
	parser.add_option("--useEvB",            default=False, action="store_true",             dest="useEvB",            help="Use EvB for event building (instead of gevb2g (default))")
	# parser.add_option("--useGev2g",          default=False, action="store_true",             dest="useGevb2g",         help="Use gevb2g for event building (instead of EvB)")
	parser.add_option("--useIBV",            default=False, action="store_true",             dest="useIBV",            help="Use IBV protocol for builder network peer transport (default)")
	parser.add_option("--useUDAPL",          default=False, action="store_true",             dest="useUDAPL",          help="Use UDAPL protocol for builder network peer transport")

	parser.add_option("-m", "--ferolMode",   default='ferol_emulator', action="store", type="string", dest="ferolMode",   help="Set ferol operation mode, can be either 'ferol_emulator', 'frl_autotrigger', 'frl_gtpe_trigger', or 'efed_slink_gtpe'")
	parser.add_option("--fragmentDir",       default='fragments/',     action="store", type="string", dest="fragmentDir", help="Use config fragments from a directory other than the default ('%default')")
	parser.add_option("-v", "--verbose",     default=1,                action="store", type='int',    dest="verbose",     help="Set the verbose level, [default: %default (semi-quiet)]")
	parser.add_option("-o", "--output",      default='configuration.template.xml', action="store", type='string', dest="output", help="Where to put the output file [default %default]")

	(options, args) = parser.parse_args()
	if len(args) > 0:
		nstreams, nrus, nbus, _, strperfrl = getConfig(args[0])
		nferols = nstreams//strperfrl

		configurator = daq2Configurator(options.fragmentDir, verbose=options.verbose)

		configurator.enablePauseFrame  = options.enablePauseFrame
		configurator.disablePauseFrame = options.disablePauseFrame ## in case both are true, they will be enabled
		configurator.setCWND           = options.setCWND ## -1 doesn't do anything
		configurator.evbns             = 'EvB' if options.useEvB else 'gevb2g'
		configurator.ptprot            = 'udapl' if options.useUDAPL and not options.useIBV else 'ibv'
		configurator.operation_mode    = options.ferolMode

		configurator.makeConfig(nferols,strperfrl,nrus,nbus,options.output)

		exit(0)

	parser.print_help()
	exit(-1)


