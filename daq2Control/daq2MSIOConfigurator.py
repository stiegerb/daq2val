import os
import subprocess
import re
import time
from copy import deepcopy

from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import QName as QN
from xml.parsers.expat import ExpatError

from daq2Utils import printError
from daq2Configurator import elementFromFile, addFragmentFromFile

######################################################################
from daq2Configurator import daq2Configurator
class daq2MSIOConfigurator(daq2Configurator):
	'''
---------------------------------------------------------------------
  class daq2MSIOConfigurator

---------------------------------------------------------------------
'''
	def __init__(self, fragmentdir, verbose=5):
		super(daq2MSIOConfigurator, self).__init__(fragmentdir,
			                                       verbose=verbose)

		self.evbns          = 'msio' ## 'msio' or 'gevb'
		self.ptprot         = 'ibv' ## or 'ibv' or 'udapl'

		self.useGTPe        = False
		self.useEFEDs       = False

		## These should be passed as arguments
		self.nclients = 1
		self.nservers = 1

	def addMSIOI2OProtocol(self):
		i2ons = "http://xdaq.web.cern.ch/xdaq/xsd/2004/I2OConfiguration-30"
		prot = Element(QN(i2ons, 'protocol').text)

		## Add Clients:
		cl_starting_tid = 20
		for n in xrange(self.nclients):
			prot.append(Element(QN(i2ons, 'target').text,
				                  {'class':'Client',
				                   'instance':"%d"%n,
				                   'tid':'%d'%(cl_starting_tid+n)}))
		## Add Servers:
		se_starting_tid = 50
		for n in xrange(self.nservers):
			prot.append(Element(QN(i2ons, 'target').text,
				                  {'class':'Server',
				                   'instance':"%d"%n,
				                   'tid':'%d'%(se_starting_tid+2*n)}))

		self.config.append(prot)

	def makeClient(self, index):
		fragmentname = 'msio/client_context.xml'
		ru_context = elementFromFile(os.path.join(self.fragmentdir,
			                                      fragmentname))

		## Add policy
		addFragmentFromFile(target=ru_context, filename=
			                os.path.join(self.fragmentdir,
			                	'msio/client_policy_%s.xml'% self.ptprot),
			                index=0)
		polns = "http://xdaq.web.cern.ch/xdaq/xsd/2013/XDAQPolicy-10"
		for element in ru_context.findall(QN(polns,"policy").text+'/'+
			                              QN(polns,"element").text):
			if 'RU%d' in element.get('pattern'):
				element.set('pattern',element.get('pattern').replace(
					                         'RU%d', 'RU%d'%(index)))
		## Add pt application
		addFragmentFromFile(target=ru_context, filename=
			                os.path.join(self.fragmentdir,
		                    'msio/client_%s_application.xml'% self.ptprot),
		                    index=2) ## add after policy and endpoint
		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		ru_context.insert(3,module)

		## Client application
		ru_app = elementFromFile(filename=os.path.join(self.fragmentdir,
			                     'msio/client_application.xml'))
		ru_context.insert(4,ru_app)
		ru_app.set('instance',str(index))

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		if self.evbns == 'msio':
			module.text = "$XDAQ_ROOT/lib/libmstreamio2g.so"
		ru_context.insert(5,module)

		## Set instance and url
		for app in ru_context.findall(QN(self.xdaqns, 'Endpoint').text):
			if 'RU%d' in app.attrib['hostname']:
				app.set('hostname', app.get('hostname')%index)
			if 'RU%d' in app.attrib['port']:
				app.set('port', app.get('port')%index)
		ru_context.set('url', ru_context.get('url')%(index, index))

		return ru_context
	def makeServer(self, index):
		fragmentname = 'msio/server_context.xml'
		bu_context = elementFromFile(os.path.join(self.fragmentdir,
			                                      fragmentname))

		## Add policy
		addFragmentFromFile(target=bu_context,
			                filename=os.path.join(self.fragmentdir,
			                	     'msio/server_policy_%s.xml'%(
			                	      self.ptprot)),
			                index=0)
		## Add pt application
		addFragmentFromFile(target=bu_context,
		                    filename=os.path.join(self.fragmentdir,
		                             'msio/server_%s_application.xml'%(
		                             self.ptprot)),
		                    index=2) ## add after the two endpoints
		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		module.text = "$XDAQ_ROOT/lib/libpt%s.so"%self.ptprot
		bu_context.insert(3,module)

		## Server application
		bu_app = elementFromFile(filename=os.path.join(self.fragmentdir,
			                     'msio/server_application.xml'))
		bu_context.insert(4,bu_app)
		bu_app.set('instance',str(index))

		## Add corresponding module
		module = Element(QN(self.xdaqns, 'Module').text)
		if self.evbns == 'msio':
			module.text = "$XDAQ_ROOT/lib/libmstreamio2g.so"
		bu_context.insert(5,module)

		## Set instance and url
		for app in bu_context.findall(QN(self.xdaqns, 'Endpoint').text):
			if 'BU%d' in app.attrib['hostname']:
				app.set('hostname', app.get('hostname')%index)
			if 'BU%d' in app.attrib['port']:
				app.set('port', app.get('port')%index)
		bu_context.set('url', bu_context.get('url')%(index, index))

		## Set instance and url
		for app in bu_context.findall(QN(self.xdaqns, 'Application').text):
			if app.attrib['class'] != "%s::BU"%self.evbns: continue
			app.set('instance', str(index))
			break

		return bu_context

	def makeMSIOConfig(self, nclients=1, nservers=1,
		           destination='configuration.template.xml'):
		self.nclients = nclients
		self.nservers = nservers

		##
		self.makeSkeleton()
		self.addMSIOI2OProtocol()

		for index in xrange(self.nclients):
			self.config.append(self.makeClient(index))

		for index in xrange(self.nservers):
			self.config.append(self.makeServer(index))

		self.writeConfig(destination)
		if self.verbose>0: print 70*'-'


