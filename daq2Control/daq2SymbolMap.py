import re, os, time
from daq2Utils import printError

######################################################################
class daq2SymbolMap(object):
	'''
---------------------------------------------------------------------
  class daq2SymbolMap

 - Reads the symbolmap and fills dictionaries for each host
 - Can be called with the keys directly, or with the host keys, i.e.:
   >>> sm = daq2SymbolMap(file)
   >>> sm('GTPE0_SOAP_HOST_NAME')  ##> 'dvfmmpc-C2F31-06-01.cms'
   or:
   >>> h = sm('GTPE0')
   >>> h.host  ##> 'dvfmmpc-C2F31-06-01.cms'
   etc.
---------------------------------------------------------------------
'''
	def __init__(self, symbolMapFile=''):
		if len(symbolMapFile) == 0:
			try:
				self._symbolMapFile = os.environ['TESTS_SYMBOL_MAP']
			except KeyError as e:
				printError('Need to provide an input file somehow! Forgot to source setenv-COL.sh?', self)
				raise e
		else: self._symbolMapFile = symbolMapFile

		self._symbolMap, self._hostMap, self.allHosts = self.fillSymbolMap(self._symbolMapFile)

	def __call__(self, key):
		try:
			return self._symbolMap[key]
		except KeyError:
			return self._hostMap[key]

	def keys(self):
		return self._symbolMap.keys()

	def fillSymbolMap(self, symbolMapFile):
		from daq2Config import host
		symbolMap = {}
		hostMap = {}
		allhosts = []
		with open(symbolMapFile, 'r') as file:
		    for line in file:
				if line.startswith('#') or len(line.strip())==0: continue
				key,value = line.split()
				symbolMap[key] = value

				match = re.match(r'([A-Z_0-9]*?[A-Z]*)([0-9]+)_SOAP_HOST_NAME$',key)
				## matches a NAME23_SOAP_HOST_NAME structure for the 'NAME' and '23'
				if match:
					hosttype, index = (match.group(1), match.group(2))
					name = hosttype+index
					soaphost = value
					ho = host(name, int(index), hosttype, soaphost=soaphost, soapport=0)
					allhosts.append(ho)

		try:
			soap_base_port     = int(symbolMap['SOAP_BASE_PORT'])
			frl_base_port      = int(symbolMap['FRL_BASE_PORT'])
			launcher_base_port = int(symbolMap['LAUNCHER_BASE_PORT'])
			i2o_base_port      = int(symbolMap['I2O_BASE_PORT'])

			for n,h in enumerate(allhosts):
				symbolMap[h.name+'_SOAP_PORT']     = soap_base_port     + n
				symbolMap[h.name+'_FRL_PORT']      = frl_base_port      + n
				symbolMap[h.name+'_LAUNCHER_PORT'] = launcher_base_port + n
				symbolMap[h.name+'_I2O_PORT']      = i2o_base_port      + n
				allhosts[n].port  = int(soap_base_port + n)
				allhosts[n].lport = int(launcher_base_port + n)
		except KeyError as e:
			printError(self, 'Not all base ports defined (SOAP, FRL, LAUNCHER, I2O), check your symbolmap! Aborting.')
			raise e
		for h in allhosts:
			hostMap[h.name] = h
		return symbolMap, hostMap, allhosts
	def __str__(self):
		output = ''
		output += 20*'-' + '\n'
		for key in sorted(self._symbolMap.keys()):
			output += '%-35s%-35s\n' % (key, self._symbolMap[key])
		return output

	def fillTemplate(self, filename):
		with open(filename, 'r') as ifile:
			template = ifile.read()
			filled = template
			for key in self._symbolMap.keys():
				filled = filled.replace(str(key), str(self._symbolMap[key]))
		return filled


