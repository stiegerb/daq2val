#! /usr/bin/env python
import sys, os
from subprocess import call

if __name__ == "__main__":
	if len(sys.argv) < 2: exit(-1)
	if os.path.isdir(sys.argv[1]):
		for subdir in os.listdir(sys.argv[1]):
			if not os.path.isdir(sys.argv[1]+subdir): continue
			# print 'Found case', subdir
			print 'cp', sys.argv[1]+subdir+'/configuration.template.xml', sys.argv[2]+subdir+'.xml'
			call(['cp', sys.argv[1]+subdir+'/configuration.template.xml', sys.argv[2]+subdir+'.xml'])
		exit(0)

