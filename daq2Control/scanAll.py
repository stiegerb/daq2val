#! /usr/bin/env python
import daq2Utils as utils
from os import path
from runDAQ2Scan import runScan
from daq2Utils import sleep, printError, printWarningWithWait

if __name__ == "__main__":
	from optparse import OptionParser
	from runDAQ2Test import addOptions
	from runDAQ2Scan import addScanningOptions
	usage = """
Wrapper for runDAQ2Scan.py script:

  > Give a list of input configuration files, and it will run a scan
    with the given options over all of them

%prog [options] config1.xml config2.xml config3.xml [relRMS]

Examples:
%prog --maxSize 16000 --stopRestart overnight/*.xml -o output/

Default output directory is 'output/' at location of the first config file
"""
	parser = OptionParser(usage=usage)
	addOptions(parser)
	addScanningOptions(parser)
	(options, args) = parser.parse_args()

	list_of_configs = []
	if path.exists(args[-1]) and args[-1].endswith('.xml'):
		options.relRMS = 0.0
		options.useLogNormal = False
		list_of_configs = [c for c in args]
	else:
		try:
			options.relRMS = float(args[-1])
			options.useLogNormal = True
			list_of_configs = [c for c in args[:-1]]
		except ValueError:
			printError('Could not convert argument to RMS value.')

	if options.outputDir is '':
		output_base = path.join(path.dirname(args[0]), 'output')
	else:
		output_base = options.outputDir

	print "----------------------------------------------------"
	print ("Will run a scan for the following %d configurations." % (
		                                         len(list_of_configs)))
	for config_file in list_of_configs:
		print config_file

	raw_input("Press Enter to continue...")

	for config_file in list_of_configs:
		newargs = [config_file]
		if options.useLogNormal:
			newargs.append(args[-1])

		output_dir = path.splitext(path.split(config_file)[1])[0]
		options.outputDir = path.join(output_base, output_dir)

		runScan(options, newargs)
		sleep(10)


	exit(0)

