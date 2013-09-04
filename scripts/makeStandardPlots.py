#! /usr/bin/env python
from plotData import makeMultiPlot

def createDir(directory):
	from os import path
	from subprocess import check_call
	if not directory.endswith('/'): directory+='/'
	if path.isdir(directory): return directory
	check_call(['mkdir', '-p', directory])
	return directory

def processRMSScan(date, casename, prefix, outdir, rootfile, legends=[], tag='', rmslist=[], oname=''):
	outputdir = createDir(outdir+(prefix%date)[5:])
	if len(rmslist) == 0: rmslist = ['RMS_0.0', 'RMS_0.5', 'RMS_1.0', 'RMS_2.0']
	if len(tag)     == 0: tag = prefix.split('/')[1]+':'+prefix.split('/')[2]
	if len(legends) == 0: legends = [casename + ', ' + x.replace('_',' ') for x in rmslist]
	if len(oname)   == 0: oname = outputdir+casename
	else: oname = outputdir + oname

	caselist = []
	for x in rmslist:
		if len(x) > 0: caselist.append(prefix%date + casename + '_' + x)
		else:          caselist.append(prefix%date + casename)

	makeMultiPlot(rootfile, caselist, oname=oname, tag=tag, legends=legends)

def makeStandardPlots(rootfile, outdir):
	rootfile_clean = rootfile.replace('.root', '_clean.root')
	outputdir = createDir(outdir)

	prefix = 'data/FEROLs/gevb2g/%s/'
	processRMSScan('Sep4', '32s16fx2x2', prefix, outdir, rootfile)

	# #### FEROLs:
	# ## gevb2g
	# prefix = 'data/FEROLs/gevb2g/%s/'

	# ## Aug13
	# legends = ['RMS 0.0, OFED-v1.5.3-3', 'RMS 0.5, OFED-v1.5.3-3', 'RMS 1.0, OFED-v1.5.3-3', 'RMS 2.0, OFED-v1.5.3-3']
	# processRMSScan('Aug13', '8s8fx1x2',         prefix, outdir, rootfile, rmslist=['ptfrl', 'RMS_0.5', 'RMS_1', 'RMS_2'], oname='8s8fx1x2_lognormals_gevb2g_ofed1533',   legends=map(lambda x:'8s8fx1x2 '  +x, legends))
	# processRMSScan('Aug13', '16s8fx1x2',        prefix, outdir, rootfile, rmslist=['RMS_0', 'RMS_0.5', 'RMS_1', 'RMS_2'], oname='16s8fx1x2_lognormals_gevb2g_ofed1533',  legends=map(lambda x:'16s8fx1x2 ' +x, legends))
	# processRMSScan('Aug13', '16s16fx2x2',       prefix, outdir, rootfile, rmslist=['RMS_0', 'RMS_0.5', 'RMS_1', 'RMS_2'], oname='16s16fx1x2_lognormals_gevb2g_ofed1533', legends=map(lambda x:'16s16fx1x2 '+x, legends))
	# processRMSScan('Aug13', '32s16fx4x4_c6220', prefix, outdir, rootfile, rmslist=['RMS_0', 'RMS_0.5', 'RMS_1', 'RMS_2'], oname='32s16fx4x4_lognormals_gevb2g_ofed1533', legends=map(lambda x:'32s16fx4x4 '+x, legends))

	# ## Aug15
	# legends = ['RMS 0.0, OFED-v1.5.3-4', 'RMS 0.5, OFED-v1.5.3-4', 'RMS 1.0, OFED-v1.5.3-4', 'RMS 2.0, OFED-v1.5.3-4']
	# processRMSScan('Aug15', '16s16fx2x2', prefix, outdir, rootfile, rmslist=['', 'RMS_0.5', 'RMS_1', 'RMS_2'], oname='16s16fx2x2_lognormals_gevb2g_ofed1534', legends=map(lambda x:'16s16fx2x2 '+x, legends))

	# outputdir = createDir(outdir+'FEROLs/gevb2g/Aug15/')
	# caselist =  [ prefix%'Aug15' + '16s16fx2x2', prefix%'Aug13' + '16s16fx2x2_RMS_0', prefix%'Aug15' + '16s16fx2x2_RMS_1', prefix%'Aug13' + '16s16fx2x2_RMS_1']
	# legends = ['RMS 0.0, OFED-v1.5.3-4', 'RMS 0.0, OFED-v1.5.3-3', 'RMS 1.0, OFED-v1.5.3-4', 'RMS 1.0, OFED-v1.5.3-3']
	# makeMultiPlot(rootfile, caselist, oname=outputdir+'16s16fx2x2_lognormals_gevb2g', tag='FEROL:gevb2g', legends=map(lambda x:'16s16fx2x2 '+x, legends))


	# ## Aug19
	# processRMSScan('Aug19', '12s12fx1x2', prefix, outdir, rootfile, oname='12s12fx1x2_lognormals_gevb2g')
	# processRMSScan('Aug19', '24s12fx1x2', prefix, outdir, rootfile, oname='24s12fx1x2_lognormals_gevb2g')

	# ## Aug29
	# processRMSScan('Aug29', '16s8fx1x2', prefix, outdir, rootfile, oname='16s8fx1x2_RMS_0.0', rmslist=['RMS_0.0', 'RMS_0.0_old'], legends=['16s8fx1x2, RMS 0.0', '16s8fx1x2, RMS 0.0 (old pt::frl)'])

	# ## Sep2
	# processRMSScan('Sep2', '16s8fx1x2',  prefix, outdir, rootfile, oname='16s8fx1x2_newR620', tag='FEROL:gevb2g (new R620)')
	# processRMSScan('Sep2', '16s8fx1x2',  prefix, outdir, rootfile, rmslist=['RMS_0.0', 'RMS_0.0_try2'], oname='16s8fx1x2_newR620_RMS0.0', tag='FEROL:gevb2g (new R620)', legends=['16s8fx1x2, RMS 0.0 (try 1)', '16s8fx1x2, RMS 0.0 (try 2)'])
	# processRMSScan('Sep2', '16s8fx1x2',  prefix, outdir, rootfile, rmslist=['RMS_0.5', 'RMS_0.5_try2'], oname='16s8fx1x2_newR620_RMS0.5', tag='FEROL:gevb2g (new R620)', legends=['16s8fx1x2, RMS 0.5 (try 1)', '16s8fx1x2, RMS 0.5 (try 2)'])
	# processRMSScan('Sep2', '16s8fx1x2',  prefix, outdir, rootfile, rmslist=['RMS_1.0', 'RMS_1.0_try2'], oname='16s8fx1x2_newR620_RMS1.0', tag='FEROL:gevb2g (new R620)', legends=['16s8fx1x2, RMS 1.0 (try 1)', '16s8fx1x2, RMS 1.0 (try 2)'])
	# processRMSScan('Sep2', '12s12fx1x2', prefix, outdir, rootfile, oname='12s12fx1x2_newR620', tag='FEROL:gevb2g (new R620)')
	# processRMSScan('Sep2', '24s12fx1x2', prefix, outdir, rootfile, oname='24s12fx1x2_newR620', tag='FEROL:gevb2g (new R620)')

	# ## Sep4
	# processRMSScan('Sep4', '24s12fx2x2', prefix, outdir, rootfile)
	# processRMSScan('Sep4', '8s8fx1x2',   prefix, outdir, rootfile)
	# processRMSScan('Sep4', '32s16fx2x2', prefix, outdir, rootfile)

	# ## EvB
	# prefix = 'data/FEROLs/EvB/%s/'

	# ## Aug19
	# processRMSScan('Aug19', '8s8fx1x4', prefix, outdir, rootfile_clean, tag='FEROL:EvB (cleaned)')
	# processRMSScan('Aug19', '16s8fx1x4', prefix, outdir, rootfile_clean, tag='FEROL:EvB (cleaned)')

	# ## Aug21
	# processRMSScan('Aug21', '12s12fx1x4', prefix, outdir, rootfile, oname='12s12fx1x4_R720', tag='FEROL:EvB (R720)')

	# ## Aug23
	# processRMSScan('Aug23', '12s12fx1x4', prefix, outdir, rootfile, oname='12s12fx1x4_R620', tag='FEROL:EvB (R620)')

	# outputdir = createDir(outdir+'FEROLs/EvB/Aug23/')
	# r6720_list = [prefix % 'Aug23' + '12s12fx1x4_RMS_0.0', prefix % 'Aug21' + '12s12fx1x4_RMS_0.0', prefix % 'Aug23' + '12s12fx1x4_RMS_1.0', prefix % 'Aug21' + '12s12fx1x4_RMS_1.0']
	# legends = ['RMS 0.0, R620', 'RMS 0.0, R720', 'RMS 1.0, R620', 'RMS 1.0, R720']
	# makeMultiPlot(rootfile, r6720_list, oname=outputdir+'12s12fx1x4_R620_R720', tag='FEROL:EvB', legends=map(lambda x:'12s12fx1x4, ' + x, legends))

	# ## Aug25
	# processRMSScan('Aug25', '16s8fx1x4',  prefix, outdir, rootfile)
	# processRMSScan('Aug25', '16s16fx2x4', prefix, outdir, rootfile)
	# processRMSScan('Aug25', '24s12fx1x4', prefix, outdir, rootfile)
	# processRMSScan('Aug25', '32s16fx2x4', prefix, outdir, rootfile)

	## Aug26
	# outputdir = createDir(outdir+'FEROLs/EvB/Aug26/')
	# legends = ['Try 1', 'Try 2', 'Try 3']
	# list_16s16fx2x4  = [prefix % 'Aug26' + '16s16fx2x4_RMS_0.0_1']
	# list_16s16fx2x4 += [prefix % 'Aug26' + '16s16fx2x4_RMS_0.0_2']
	# list_16s16fx2x4 += [prefix % 'Aug26' + '16s16fx2x4_RMS_0.0_3']
	# makeMultiPlot(rootfile, list_16s16fx2x4, rangex=(3500, 9000), rangey=(3000,5500), oname=outputdir+'16s16fx2x4_segment', tag='FEROL:EvB', legends=map(lambda x:'16s16fx2x4, RMS 0.0, ' + x, legends))

	# ## mixed
	# prefix = 'data/FEROLs/%s/%s/'
	# list_12s_evb_gevb  = [prefix %('EvB'   ,'Aug21')    + '12s12fx1x4_RMS_0.0']
	# list_12s_evb_gevb += [prefix %('gevb2g','Aug19') + '12s12fx1x2_RMS_0.0']
	# list_12s_evb_gevb += [prefix %('EvB'   ,'Aug21')    + '12s12fx1x4_RMS_1.0']
	# list_12s_evb_gevb += [prefix %('gevb2g','Aug19') + '12s12fx1x2_RMS_1.0']
	# legends = ['12s12fx1x4, RMS 0.0, EvB', '12s12fx1x2, RMS 0.0, gevb2g', '12s12fx1x4, RMS 1.0, EvB', '12s12fx1x2, RMS 1.0, gevb2g']
	# makeMultiPlot(rootfile, list_12s_evb_gevb, oname=outputdir+'12s12fx1x2,4_lognormals_EvBvsgevb2g', tag='FEROL:EvB/gevb2g', legends=legends)


	#### eFEROLs:
	# prefix = 'data/eFEROLs/%s/Aug13/'
	# list_8x1x2_lognormals_gevb2g  = [ prefix % 'gevb2g/dummyFerol' + x for x in ['8x1x2_RMS_0_useLogNormal_false', '8x1x2_RMS_0.5_useLogNormal_true', '8x1x2_RMS_1_useLogNormal_true', '8x1x2_RMS_2_useLogNormal_true']]
	# list_16x1x2_lognormals_gevb2g = [ prefix % 'gevb2g/dummyFerol' + x for x in ['16x1x2_RMS_0_useLogNormal_false', '16x1x2_RMS_0.5_useLogNormal_true', '16x1x2_RMS_1_useLogNormal_true', '16x1x2_RMS_2_useLogNormal_true']]
	# list_x1x2_lognormals_gevb2g   = [ prefix % 'gevb2g/dummyFerol' + x for x in ['8x1x2_RMS_0_useLogNormal_false', '8x1x2_RMS_1_useLogNormal_true', '16x1x2_RMS_0_useLogNormal_false', '16x1x2_RMS_1_useLogNormal_true']]
	# list_8x1x4_lognormals_EvB     = [ prefix % 'EvB'               + x for x in ['8x1x4_RMS_0_useLogNormal_false',  '8x1x4_RMS_0.5_useLogNormal_true',  '8x1x4_RMS_1_useLogNormal_true',  '8x1x4_RMS_2_useLogNormal_true']]
	# list_12x1x4_lognormals_EvB    = [ prefix % 'EvB'               + x for x in ['12x1x4_RMS_0_useLogNormal_false', '12x1x4_RMS_0.5_useLogNormal_true', '12x1x4_RMS_1_useLogNormal_true', '12x1x4_RMS_2_useLogNormal_true']]
	# list_16x1x4_lognormals_EvB    = [ prefix % 'EvB'               + x for x in ['16x1x4_RMS_0_useLogNormal_false', '16x1x4_RMS_0.5_useLogNormal_true', '16x1x4_RMS_1_useLogNormal_true', '16x1x4_RMS_2_useLogNormal_true']]
	# list_16x2x4_lognormals_EvB    = [ prefix % 'EvB'               + x for x in ['16x2x4_RMS_0_useLogNormal_false', '16x2x4_RMS_0.5_useLogNormal_true', '16x2x4_RMS_1_useLogNormal_true', '16x2x4_RMS_2_useLogNormal_true']]
	# list_32x2x4_lognormals_EvB    = [ prefix % 'EvB'               + x for x in ['32x2x4_RMS_0_useLogNormal_false', '32x2x4_RMS_0.5_useLogNormal_true', '32x2x4_RMS_1_useLogNormal_true', '32x2x4_RMS_2_useLogNormal_true']]
	# list_x1x4_lognormals_EvB      = [ prefix % 'EvB'               + x for x in ['8x1x4_RMS_0_useLogNormal_false',  '8x1x4_RMS_1_useLogNormal_true',    '16x1x4_RMS_0_useLogNormal_false', '16x1x4_RMS_1_useLogNormal_true']]

	# outputdir = createDir(outdir+'eFEROLs/gevb2g/Aug13/')
	# makeMultiPlot(rootfile_clean, list_8x1x2_lognormals_gevb2g,  oname=outputdir+'8x1x2_lognormals_gevb2g.pdf',  tag='eFEROL:gevb2g')
	# makeMultiPlot(rootfile_clean, list_16x1x2_lognormals_gevb2g, oname=outputdir+'16x1x2_lognormals_gevb2g.pdf', tag='eFEROL:gevb2g')
	# makeMultiPlot(rootfile_clean, list_x1x2_lognormals_gevb2g,   oname=outputdir+'x1x2_lognormals_gevb2g.pdf',   tag='eFEROL:gevb2g')
	# makeMultiPlot(rootfile_clean, list_x1x2_lognormals_gevb2g,   rangex=(1500, 150000), oname=outputdir+'x1x2_lognormals_gevb2g_sufrag.pdf', frag=False, tag='eFEROL:gevb2g')

	# outputdir = createDir(outdir+'eFEROLs/EvB/Aug13/')
	# makeMultiPlot(rootfile_clean, list_x1x4_lognormals_EvB,      oname=outputdir+'x1x4_lognormals_EvB.pdf',      tag='eFEROL:EvB')
	# makeMultiPlot(rootfile_clean, list_8x1x4_lognormals_EvB,     oname=outputdir+'8x1x4_lognormals_EvB.pdf',     tag="eFEROL:EvB")
	# makeMultiPlot(rootfile_clean, list_12x1x4_lognormals_EvB,    oname=outputdir+'12x1x4_lognormals_EvB.pdf',    tag="eFEROL:EvB")
	# makeMultiPlot(rootfile_clean, list_16x1x4_lognormals_EvB,    oname=outputdir+'16x1x4_lognormals_EvB.pdf',    tag="eFEROL:EvB")
	# makeMultiPlot(rootfile_clean, list_16x2x4_lognormals_EvB,    oname=outputdir+'16x2x4_lognormals_EvB.pdf',    tag="eFEROL:EvB")
	# makeMultiPlot(rootfile_clean, list_32x2x4_lognormals_EvB,    oname=outputdir+'32x2x4_lognormals_EvB.pdf',    tag="eFEROL:EvB")
	# makeMultiPlot(rootfile_clean, list_x1x4_lognormals_EvB,      rangex=(1500, 150000), oname=outputdir+'x1x4_lognormals_EvB_sufrag.pdf',    frag=False, tag='eFEROL:EvB')


	# prefix = 'data/eFEROLs/EvB/%s/'
	# processRMSScan('Aug28', '32x4x4', prefix, outdir, rootfile, oname='32x4x4_c6220', rmslist=['RMS_0.0_c6220', 'RMS_0.5_c6220', 'RMS_1.0_c6220', 'RMS_2.0_c6220'], tag='eFEROL:EvB (c6220)')

	# prefix = 'data/eFEROLs/gevb2g/%s/'
	# processRMSScan('Aug29', '32x4x4', prefix, outdir, rootfile, oname='32x4x4_c6220', rmslist=['RMS_0.0_c6220', 'RMS_0.5_c6220', 'RMS_1.0_c6220', 'RMS_2.0_c6220'], tag='eFEROL:gevb2g (c6220)')


##---------------------------------------------------------------------------------
## User interface
if __name__ == "__main__":
	from optparse import OptionParser
	usage = """
	Use to create a batch of standard plots:
	%prog  --outdir plots/ data.root
	"""

	parser = OptionParser(usage=usage)
	parser.add_option("-o", "--outdir", default="plots/", action="store", type="string", dest="outdir",
	                  help="Output directory for the plots [default: %default]")
	# parser.add_option("--makePNGs",     default=True,     action="store_true", dest="makePNGs",
	#                   help="Produce also .png files [default: %default]")


	(options, args) = parser.parse_args()

	if len(args) > 0:
		makeStandardPlots(args[0], outdir=options.outdir)
		exit(0)

	makeStandardPlots('data.root', outdir=options.outdir)
	exit(0)

	# parser.print_help()
	# exit(-1)



