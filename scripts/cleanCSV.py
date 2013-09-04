#! /usr/bin/env python
def stripTrailingZeros(filename, removeAlsoLeading=False, inPlace=False):
	from subprocess import call
	if inPlace:
		call(['cp', filename, filename.replace('.csv', '_original.csv')])
	with open(filename, 'r') as f, open(filename.replace('.csv','_stripped.csv'), 'w') as o:
		for line in f:
			if len(line.strip()) == 0 or line.strip()[0] == '#':
				o.write(line)
				continue
			spline = line.strip('\n').split(',')
			data = map(lambda x: int(float(x)), spline[1:])
			o.write(spline[0])
			o.write(',')
			for x in reversed(data):
				if x == 0: data.pop()
				else: break # stop as soon as one isn't 0

			# print data
			if removeAlsoLeading:
				data.reverse() # 0's now at the end, can use same code as above
				for x in reversed(data):
					if x == 0: data.pop()
					else: break
				data.reverse() # reverse back

			data = map(int, data)
			newline = reduce(lambda x,y: str(x)+','+str(y), data)
			o.write(newline)
			o.write('\n')
		f.close()
		o.close()
	if inPlace:
		call(['mv', filename.replace('.csv', '_stripped.csv'), filename])


##---------------------------------------------------------------------------------
## User interface
if __name__ == "__main__":
	from optparse import OptionParser
	usage = """
	Use to create a batch of standard plots:
	%prog  --outDir plots/ data.root
	"""
	parser = OptionParser(usage=usage)
	# parser.add_option("-o", "--outDir", default="plots/", action="store", type="string", dest="outDir", help="Output directory for the plots [default: %default]")
	parser.add_option("--removeAlsoLeading", default=False, action="store_true", dest="removeAlsoLeading", help="Remove also leading zeros [default: %default]")
	parser.add_option("--inPlace", default=False, action="store_true", dest="inPlace", help="Move original file to filename_original.csv, and store output in filename.csv [default: %default]")
	(options, args) = parser.parse_args()

	if len(args) > 0:
		stripTrailingZeros(args[0], removeAlsoLeading=options.removeAlsoLeading, inPlace=options.inPlace)
		exit(0)

	parser.print_help()
	exit(-1)



