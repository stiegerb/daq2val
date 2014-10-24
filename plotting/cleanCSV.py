#! /usr/bin/env python
from os import path
def stripTrailingZeros(filename, removeAlsoLeading=False, inPlace=False):
	from subprocess import call
	print '... processing', filename
	if inPlace:
		call(['cp', filename, filename.replace('.csv', '_original.csv')])
	with open(filename, 'r') as f, \
	     open(filename.replace('.csv','_stripped.csv'), 'w') as o:
		for line in f:
			if len(line.strip()) == 0 or line.strip()[0] == '#':
				o.write(line)
				continue
			line = line.strip('\n')

			try: ## EvB with size from BU (size, busize : rate, rate, rate, ...)
				size,rates = line.split(':')
				size += ':'
				rates = rates.split(',')
			except ValueError, e: ## Bare size as first entry (size, rate, rate, rate, ...)
				if "need more than" in e.errstr:
					spline = line.split(',')
					size,rates = spline[0], spline[1:]
					size += ','
				else:
					raise e

			if len(rates) > 1 and rates[1] != '':
				data = map(lambda x: int(float(x)), rates[1:])
				o.write(size)
				for x in reversed(data):
					if x == 0: data.pop()
					else: break # stop as soon as one isn't 0

				# print data
				if removeAlsoLeading:
					data.reverse() # 0's now at the end
					               # can use same code as above
					for x in reversed(data):
						if x == 0: data.pop()
						else: break
					data.reverse() # reverse back

				data = map(int, data)
				newline = ','.join([str(_) for _ in data])
				o.write(newline)
				o.write('\n')
		f.close()
		o.close()
	if inPlace:
		call(['mv', filename.replace('.csv', '_stripped.csv'), filename])

def truncatePoints(filename, firstN, lastN=None, inPlace=False):
	from subprocess import call
	print '... processing', filename
	if inPlace:
		call(['cp', filename, filename.replace('.csv', '_original.csv')])
	with open(filename, 'r') as f, \
	     open(filename.replace('.csv','_trunc.csv'), 'w') as o:
		for line in f:
			if len(line.strip()) == 0 or line.strip()[0] == '#':
				o.write(line)
				continue
			spline = line.strip('\n').split(',')
			if len(spline) > 1 and spline[1] != '':
				data = map(lambda x: int(float(x)), spline[1:])
				o.write(spline[0])
				o.write(',')

				data.reverse() # can use same code as above
				for n,x in enumerate(reversed(data)):
					if n < firstN: data.pop()
					else: break
				data.reverse() # reverse back

				if not lastN==None:
					for n,x in enumerate(reversed(data)):
						if n < lastN: data.pop()
						else: break


				data = map(int, data)
				newline = ','.join([str(_) for _ in data])
				o.write(newline)
				o.write('\n')
		f.close()
		o.close()
	if inPlace:
		call(['mv', filename.replace('.csv', '_trunc.csv'), filename])


##---------------------------------------------------------------------------
## User interface
if __name__ == "__main__":
	from optparse import OptionParser
	usage = """
	Use to create a batch of standard plots:
	%prog  --outDir plots/ data.root
	"""
	parser = OptionParser(usage=usage)
	parser.add_option("-t", "--truncate", type='string', default='',
		              action="store", dest="truncate",
		              help=("Remove n leading entries, m trailing entries "
		                    "[default: %default]"))
	parser.add_option("-l", "--removeAlsoLeading", default=False,
		              action="store_true", dest="removeAlsoLeading",
		              help="Remove also leading zeros [default: %default]")
	parser.add_option("-i", "--inPlace", default=False,
		              action="store_true", dest="inPlace",
		              help=("Move original file to filename_original.csv, "
		              	    "and store output in filename.csv "
		              	    "[default: %default]"))
	(options, args) = parser.parse_args()

	if len(args) > 0:
		for filename in args:
			if options.truncate:
				if ',' in options.truncate:
					firstN, lastN = options.truncate.split(',')
					firstN, lastN = int(firstN), int(lastN)
				else:
					firstN = int(options.truncate)
					lastN = None
				truncatePoints(filename, firstN=firstN, lastN=lastN,
					           inPlace=options.inPlace)
			else:
				stripTrailingZeros(filename,
				               removeAlsoLeading=options.removeAlsoLeading,
				               inPlace=options.inPlace)
		exit(0)

	parser.print_help()
	exit(-1)



