#! /usr/bin/env python
import os

##---------------------------------------------------------------------------------
## Cleaning of outliers in a data set
def cleanData(data, step=1, length=4, cutoff=3, quality=0.05):
	from numpy import mean,std,seterr
	# 1. find a stretch of data where the std is less than X% of the mean, store that mean/std
	# 2. loop on the data and replace values more than 10% off with the mean of the clean stretch
	seterr(invalid='raise')
	found_clean_stretch = False

	if mean(data) < 0.01 or std(data)/mean(data) < quality: return data

	pos, stretch = 0, data[:length]
	try:
		# while mean(stretch) == 0 or mean(stretch) > 0 and std(stretch)/mean(stretch) > quality and pos+length < len(data):
		while mean(stretch) == 0 or mean(stretch) > 0 and std(stretch)/mean(stretch) > quality and pos+length < len(data):
			if args.verbose > 4: print stretch
			if args.verbose > 4: print pos, pos+length, std(stretch)/mean(stretch)
			pos += step
			stretch = data[pos:length+pos]
	except FloatingPointError, KeyError:
		# print "Didn't find a clean stretch in:"
		# print data
		return data

	if not std(stretch)/mean(stretch) <= quality: return data

	clean_data = []
	for r in data:
		if abs(r-mean(stretch)) > cutoff*std(stretch):
			clean_data.append(mean(stretch))
		else: clean_data.append(r)

	return clean_data
def metaCleaning(data, maxlength=15, minlength=4, cutoff=3, quality=0.05):
	from numpy import mean,std,seterr

	## Skip empty data:
	if abs(mean(data)) < 0.01 and abs(std(data)) < 0.01: return data

	seterr(invalid='raise')
	length = maxlength

	try:
		while std(data)/mean(data) > quality and length >= minlength:
			data = cleanData(data, step=1, length=length, cutoff=cutoff, quality=quality)
			length -= 1

	except FloatingPointError, KeyError:
		print "Didn't find a clean stretch in:", data
		return data
	return data
def cleanFile(filename):
	with open(filename, 'r') as f, open(filename.replace('.csv','')+'_clean.csv', 'w') as o:
		for line in f:
			if len(line.strip()) == 0 or line.strip()[0] == '#':
				o.write(line)
				continue
			spline = line.strip('\n').split(',')
			data = map(lambda x: int(float(x)), spline[1:])
			o.write(spline[0])
			o.write(',')
			cleandata = metaCleaning(data)
			# cleandata = cleanData(data)
			cleandata = map(int, cleandata)
			newline = reduce(lambda x,y: str(x)+','+str(y), cleandata)
			o.write(newline)
			o.write('\n')
		f.close()
		o.close()
def cleanFilesInDir(subdir):
	if not os.path.isdir(subdir): return
	if not os.path.exists(subdir+'/server.csv'):
		print "  could not locate", directory+subdir+'/server.csv', "... skipping"
		return
	cleanFile(subdir+'/server.csv')
