#! /usr/bin/env python
def createDir(directory):
	from os import path
	from subprocess import check_call
	if not directory.endswith('/'): directory+='/'
	if path.isdir(directory): return directory
	check_call(['mkdir', '-p', directory])
	return directory

def makeStandardPlots(rootfile, outDir):
	rootfile_clean = rootfile.replace('.root', '_clean.root')
	from plotData import makeMultiPlot
	outputdir = createDir(outDir)

	#### FEROLs:
	prefix = 'data/Aug13/FEROLs/gevb2g/'
	outputdir = createDir(outDir+'FEROLs/gevb2g/Aug13/')
	list_8s8fx1x2   = [ prefix + x for x in ['8s8fx1x2_ptfrl', '8s8fx1x2_RMS_0.5', '8s8fx1x2_RMS_1', '8s8fx1x2_RMS_2']]
	list_16s8fx1x2  = [ prefix + x for x in ['16s8fx1x2_RMS_0', '16s8fx1x2_RMS_0.5', '16s8fx1x2_RMS_1', '16s8fx1x2_RMS_2']]
	list_16s16fx2x2 = [ prefix + x for x in ['16s16fx2x2_RMS_0', '16s16fx2x2_RMS_0.5', '16s16fx2x2_RMS_1', '16s16fx2x2_RMS_2']]
	list_32s16fx4x4 = [ prefix + x for x in ['32s16fx4x4_c6220_RMS_0', '32s16fx4x4_c6220_RMS_0.5', '32s16fx4x4_c6220_RMS_1', '32s16fx4x4_c6220_RMS_2']]

	legends = ['RMS 0.0, OFED-v1.5.3-3', 'RMS 0.5, OFED-v1.5.3-3', 'RMS 1.0, OFED-v1.5.3-3', 'RMS 2.0, OFED-v1.5.3-3']
	makeMultiPlot(rootfile, list_8s8fx1x2,   oname=outputdir+'8s8fx1x2_lognormals_gevb2g_ofed1533',   tag='FEROL:gevb2g', legends=map(lambda x:'8s8fx1x2 '+x, legends))
	makeMultiPlot(rootfile, list_16s8fx1x2,  oname=outputdir+'16s8fx1x2_lognormals_gevb2g_ofed1533',  tag='FEROL:gevb2g', legends=map(lambda x:'16s8fx1x2 '+x, legends))
	makeMultiPlot(rootfile, list_16s16fx2x2, oname=outputdir+'16s16fx2x2_lognormals_gevb2g_ofed1533', tag='FEROL:gevb2g', legends=map(lambda x:'16s16fx2x2 '+x, legends))
	makeMultiPlot(rootfile, list_32s16fx4x4, oname=outputdir+'32s16fx4x4_lognormals_gevb2g_ofed1533', tag='FEROL:gevb2g', legends=map(lambda x:'32s16fx4x4 '+x, legends))

	prefix = 'data/Aug15/FEROLs/gevb2g/'
	outputdir = createDir(outDir+'FEROLs/gevb2g/Aug15/')
	list_16s16fx2x2 = [ prefix + x for x in ['16s16fx2x2', '16s16fx2x2_RMS_0.5', '16s16fx2x2_RMS_1', '16s16fx2x2_RMS_2']]
	legends = ['RMS 0.0, OFED-v1.5.3-4', 'RMS 0.5, OFED-v1.5.3-4', 'RMS 1.0, OFED-v1.5.3-4', 'RMS 2.0, OFED-v1.5.3-4']
	makeMultiPlot(rootfile, list_16s16fx2x2, oname=outputdir+'16s16fx2x2_lognormals_gevb2g_ofed1534', tag='FEROL:gevb2g', legends=map(lambda x:'16s16fx2x2 '+x, legends))

	prefix = 'data/%s/FEROLs/gevb2g/'
	list_16s16fx2x2 =  [ prefix%'Aug15' + '16s16fx2x2']
	list_16s16fx2x2 += [ prefix%'Aug13' + '16s16fx2x2_RMS_0']
	list_16s16fx2x2 += [ prefix%'Aug15' + '16s16fx2x2_RMS_1']
	list_16s16fx2x2 += [ prefix%'Aug13' + '16s16fx2x2_RMS_1']
	legends = ['RMS 0.0, OFED-v1.5.3-4', 'RMS 0.0, OFED-v1.5.3-3', 'RMS 1.0, OFED-v1.5.3-4', 'RMS 1.0, OFED-v1.5.3-3']
	makeMultiPlot(rootfile, list_16s16fx2x2, oname=outputdir+'16s16fx2x2_lognormals_gevb2g', tag='FEROL:gevb2g', legends=map(lambda x:'16s16fx2x2 '+x, legends))

	prefix = 'data/%s/FEROLs/gevb2g/'
	outputdir = createDir(outDir+'FEROLs/gevb2g/Aug19/')
	list_12s12fx1x2 =  [ prefix%'Aug19' + '12s12fx1x2_RMS_0.0']
	list_12s12fx1x2 += [ prefix%'Aug19' + '12s12fx1x2_RMS_0.5']
	list_12s12fx1x2 += [ prefix%'Aug19' + '12s12fx1x2_RMS_1.0']
	list_12s12fx1x2 += [ prefix%'Aug19' + '12s12fx1x2_RMS_2.0']
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']
	makeMultiPlot(rootfile, list_12s12fx1x2, oname=outputdir+'12s12fx1x2_lognormals_gevb2g', tag='FEROL:gevb2g', legends=map(lambda x:'12s12fx1x2, '+x, legends))

	prefix = 'data/%s/FEROLs/gevb2g/'
	list_24s12fx1x2 =  [ prefix%'Aug19' + '24s12fx1x2_RMS_0.0']
	list_24s12fx1x2 += [ prefix%'Aug19' + '24s12fx1x2_RMS_0.5']
	list_24s12fx1x2 += [ prefix%'Aug19' + '24s12fx1x2_RMS_1.0']
	list_24s12fx1x2 += [ prefix%'Aug19' + '24s12fx1x2_RMS_2.0']
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']
	makeMultiPlot(rootfile, list_24s12fx1x2, oname=outputdir+'24s12fx1x2_lognormals_gevb2g', tag='FEROL:gevb2g', legends=map(lambda x:'24s12fx1x2, '+x, legends))

	prefix = 'data/%s/FEROLs/EvB/'
	list_8s8fx1x4 =  [ prefix%'Aug19' + '8s8fx1x4_RMS_0.0']
	list_8s8fx1x4 += [ prefix%'Aug19' + '8s8fx1x4_RMS_0.5']
	list_8s8fx1x4 += [ prefix%'Aug19' + '8s8fx1x4_RMS_1.0']
	list_8s8fx1x4 += [ prefix%'Aug19' + '8s8fx1x4_RMS_2.0']
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']
	makeMultiPlot(rootfile, list_8s8fx1x4, oname=outputdir+'8s8fx1x4_lognormals_EvB', tag='FEROL:EvB', legends=map(lambda x:'8s8fx1x4, '+x, legends))

	list_16s8fx1x4 =  [ prefix%'Aug19' + '16s8fx1x4_RMS_0.0']
	list_16s8fx1x4 += [ prefix%'Aug19' + '16s8fx1x4_RMS_0.5']
	list_16s8fx1x4 += [ prefix%'Aug19' + '16s8fx1x4_RMS_1.0']
	list_16s8fx1x4 += [ prefix%'Aug19' + '16s8fx1x4_RMS_2.0']
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']
	makeMultiPlot(rootfile, list_16s8fx1x4, oname=outputdir+'16s8fx1x4_lognormals_EvB', tag='FEROL:EvB', legends=map(lambda x:'16s8fx1x4, '+x, legends))

	prefix = 'data/%s/FEROLs/EvB/'
	outputdir = createDir(outDir+'FEROLs/EvB/Aug21/')
	list_12s12fx1x4_r720 =  [ prefix%'Aug21' + '12s12fx1x4_RMS_0.0']
	list_12s12fx1x4_r720 += [ prefix%'Aug21' + '12s12fx1x4_RMS_0.5']
	list_12s12fx1x4_r720 += [ prefix%'Aug21' + '12s12fx1x4_RMS_1.0']
	list_12s12fx1x4_r720 += [ prefix%'Aug21' + '12s12fx1x4_RMS_2.0']
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']
	makeMultiPlot(rootfile, list_12s12fx1x4_r720, oname=outputdir+'12s12fx1x4_lognormals_EvB', tag='FEROL:EvB', legends=map(lambda x:'12s12fx1x4, '+x, legends))

	prefix = 'data/%s/FEROLs/%s/'
	list_12s_evb_gevb  = [prefix %('Aug21','EvB')    + '12s12fx1x4_RMS_0.0']
	list_12s_evb_gevb += [prefix %('Aug19','gevb2g') + '12s12fx1x2_RMS_0.0']
	list_12s_evb_gevb += [prefix %('Aug21','EvB')    + '12s12fx1x4_RMS_1.0']
	list_12s_evb_gevb += [prefix %('Aug19','gevb2g') + '12s12fx1x2_RMS_1.0']
	legends = ['12s12fx1x4, RMS 0.0, EvB', '12s12fx1x2, RMS 0.0, gevb2g', '12s12fx1x4, RMS 1.0, EvB', '12s12fx1x2, RMS 1.0, gevb2g']
	makeMultiPlot(rootfile, list_12s_evb_gevb, oname=outputdir+'12s12fx1x2,4_lognormals_EvBvsgevb2g', tag='FEROL:EvB/gevb2g', legends=legends)

	prefix = 'data/%s/FEROLs/EvB/'
	outputdir = createDir(outDir+'FEROLs/EvB/Aug23/')
	list_12s12fx1x4_r620  = [prefix % 'Aug23' + '12s12fx1x4_RMS_0.0']
	list_12s12fx1x4_r620 += [prefix % 'Aug23' + '12s12fx1x4_RMS_0.5']
	list_12s12fx1x4_r620 += [prefix % 'Aug23' + '12s12fx1x4_RMS_1.0']
	list_12s12fx1x4_r620 += [prefix % 'Aug23' + '12s12fx1x4_RMS_2.0']
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']
	makeMultiPlot(rootfile, list_12s12fx1x4_r620, oname=outputdir+'12s12fx1x4_R620', tag='FEROL:EvB:R620', legends=map(lambda x:'12s12fx1x4, ' + x + ', R620', legends))
	makeMultiPlot(rootfile, list_12s12fx1x4_r720, oname=outputdir+'12s12fx1x4_R720', tag='FEROL:EvB:R720', legends=map(lambda x:'12s12fx1x4, ' + x + ', R720', legends))

	r6720_list = [list_12s12fx1x4_r620[0], list_12s12fx1x4_r720[0], list_12s12fx1x4_r620[2], list_12s12fx1x4_r720[2]]
	legends = ['RMS 0.0, R620', 'RMS 0.0, R720', 'RMS 1.0, R620', 'RMS 1.0, R720']
	makeMultiPlot(rootfile, r6720_list, oname=outputdir+'12s12fx1x4_R620_R720', tag='FEROL:EvB', legends=map(lambda x:'12s12fx1x4, ' + x, legends))

	prefix = 'data/%s/FEROLs/EvB/'
	outputdir = createDir(outDir+'FEROLs/EvB/Aug25/')
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']

	list_16s8fx1x4  = [prefix % 'Aug25' + '16s8fx1x4_RMS_0.0']
	list_16s8fx1x4 += [prefix % 'Aug25' + '16s8fx1x4_RMS_0.5']
	list_16s8fx1x4 += [prefix % 'Aug25' + '16s8fx1x4_RMS_1.0']
	list_16s8fx1x4 += [prefix % 'Aug25' + '16s8fx1x4_RMS_2.0']
	makeMultiPlot(rootfile, list_16s8fx1x4, oname=outputdir+'16s8fx1x4', tag='FEROL:EvB', legends=map(lambda x:'16s8fx1x4, ' + x, legends))

	list_16s16fx2x4  = [prefix % 'Aug25' + '16s16fx2x4_RMS_0.0']
	list_16s16fx2x4 += [prefix % 'Aug25' + '16s16fx2x4_RMS_0.5']
	list_16s16fx2x4 += [prefix % 'Aug25' + '16s16fx2x4_RMS_1.0']
	list_16s16fx2x4 += [prefix % 'Aug25' + '16s16fx2x4_RMS_2.0']
	makeMultiPlot(rootfile, list_16s16fx2x4, oname=outputdir+'16s16fx2x4', tag='FEROL:EvB', legends=map(lambda x:'16s16fx2x4, ' + x, legends))

	list_24s12fx1x4  = [prefix % 'Aug25' + '24s12fx1x4_RMS_0.0']
	list_24s12fx1x4 += [prefix % 'Aug25' + '24s12fx1x4_RMS_0.5']
	list_24s12fx1x4 += [prefix % 'Aug25' + '24s12fx1x4_RMS_1.0']
	list_24s12fx1x4 += [prefix % 'Aug25' + '24s12fx1x4_RMS_2.0']
	makeMultiPlot(rootfile, list_24s12fx1x4, oname=outputdir+'24s12fx1x4', tag='FEROL:EvB', legends=map(lambda x:'24s12fx1x4, ' + x, legends))

	list_32s16fx2x4  = [prefix % 'Aug25' + '32s16fx2x4_RMS_0.0']
	list_32s16fx2x4 += [prefix % 'Aug25' + '32s16fx2x4_RMS_0.5']
	list_32s16fx2x4 += [prefix % 'Aug25' + '32s16fx2x4_RMS_1.0']
	list_32s16fx2x4 += [prefix % 'Aug25' + '32s16fx2x4_RMS_2.0']
	makeMultiPlot(rootfile, list_32s16fx2x4, oname=outputdir+'32s16fx2x4', tag='FEROL:EvB', legends=map(lambda x:'32s16fx2x4, ' + x, legends))

	prefix = 'data/%s/FEROLs/EvB/'
	outputdir = createDir(outDir+'FEROLs/EvB/Aug26/')
	legends = ['Try 1', 'Try 2', 'Try 3']

	list_16s16fx2x4  = [prefix % 'Aug26' + '16s16fx2x4_RMS_0.0_1']
	list_16s16fx2x4 += [prefix % 'Aug26' + '16s16fx2x4_RMS_0.0_2']
	list_16s16fx2x4 += [prefix % 'Aug26' + '16s16fx2x4_RMS_0.0_3']
	makeMultiPlot(rootfile, list_16s16fx2x4, rangex=(3500, 9000), rangey=(3000,5500), oname=outputdir+'16s16fx2x4_segment', tag='FEROL:EvB', legends=map(lambda x:'16s16fx2x4, RMS 0.0, ' + x, legends))

	prefix = 'data/%s/FEROLs/gevb2g/'
	outputdir = createDir(outDir+'FEROLs/gevb2g/Aug29/')
	list_16s8fx1x2  = [prefix % 'Aug29' + '16s8fx1x2_RMS_0.0']
	list_16s8fx1x2 += [prefix % 'Aug29' + '16s8fx1x2_RMS_0.0_old']
	makeMultiPlot(rootfile, list_16s8fx1x2, oname=outputdir+'16s8fx1x2_RMS_0.0', tag='FEROL:gevb2g', legends=['16s8fx1x2, RMS 0.0', '16s8fx1x2, RMS 0.0 (old pt::frl)'])

	prefix = 'data/%s/FEROLs/gevb2g/'
	outputdir = createDir(outDir+'FEROLs/gevb2g/Sep2/')
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']

	list_16s8fx1x2  = [prefix % 'Sep2' + '16s8fx1x2_RMS_0.0']
	list_16s8fx1x2 += [prefix % 'Sep2' + '16s8fx1x2_RMS_0.5']
	list_16s8fx1x2 += [prefix % 'Sep2' + '16s8fx1x2_RMS_1.0']
	list_16s8fx1x2 += [prefix % 'Sep2' + '16s8fx1x2_RMS_2.0']
	makeMultiPlot(rootfile, list_16s8fx1x2, oname=outputdir+'16s8fx1x2_newR620', tag='FEROL:gevb2g', legends=map(lambda x:'16s8fx1x2, ' + x + ' (new R620)', legends))

	templist  = [prefix % 'Sep2' + '16s8fx1x2_RMS_0.0']
	templist += [prefix % 'Sep2' + '16s8fx1x2_RMS_0.0_try2']
	makeMultiPlot(rootfile, templist, oname=outputdir+'16s8fx1x2_newR620_RMS0', tag='FEROL:gevb2g', legends=['16s8fx1x2, RMS 0.0 (try 1)', '16s8fx1x2, RMS 0.0 (try 2)'])
	templist  = [prefix % 'Sep2' + '16s8fx1x2_RMS_0.5']
	templist += [prefix % 'Sep2' + '16s8fx1x2_RMS_0.5_try2']
	makeMultiPlot(rootfile, templist, oname=outputdir+'16s8fx1x2_newR620_RMS0.5', tag='FEROL:gevb2g', legends=['16s8fx1x2, RMS 0.5 (try 1)', '16s8fx1x2, RMS 0.5 (try 2)'])
	templist  = [prefix % 'Sep2' + '16s8fx1x2_RMS_1.0']
	templist += [prefix % 'Sep2' + '16s8fx1x2_RMS_1.0_try2']
	makeMultiPlot(rootfile, templist, oname=outputdir+'16s8fx1x2_newR620_RMS1.0', tag='FEROL:gevb2g', legends=['16s8fx1x2, RMS 1.0 (try 1)', '16s8fx1x2, RMS 1.0 (try 2)'])

	list_12s12fx1x2  = [prefix % 'Sep2' + '12s12fx1x2_RMS_0.0']
	list_12s12fx1x2 += [prefix % 'Sep2' + '12s12fx1x2_RMS_0.5']
	list_12s12fx1x2 += [prefix % 'Sep2' + '12s12fx1x2_RMS_1.0']
	list_12s12fx1x2 += [prefix % 'Sep2' + '12s12fx1x2_RMS_2.0']
	makeMultiPlot(rootfile, list_24s12fx1x2, oname=outputdir+'12s12fx1x2_newR620', tag='FEROL:gevb2g', legends=map(lambda x:'12s12fx1x2, ' + x + ' (new R620)', legends))

	list_24s12fx1x2  = [prefix % 'Sep2' + '24s12fx1x2_RMS_0.0']
	list_24s12fx1x2 += [prefix % 'Sep2' + '24s12fx1x2_RMS_0.5']
	list_24s12fx1x2 += [prefix % 'Sep2' + '24s12fx1x2_RMS_1.0']
	list_24s12fx1x2 += [prefix % 'Sep2' + '24s12fx1x2_RMS_2.0']
	makeMultiPlot(rootfile, list_24s12fx1x2, oname=outputdir+'24s12fx1x2_newR620', tag='FEROL:gevb2g', legends=map(lambda x:'24s12fx1x2, ' + x + ' (new R620)', legends))


	#### eFEROLs:
	prefix = 'data/Aug13/eFEROLs/'
	list_8x1x2_lognormals_gevb2g  = [ prefix + 'gevb2g/dummyFerol/' + x for x in ['8x1x2_RMS_0_useLogNormal_false', '8x1x2_RMS_0.5_useLogNormal_true', '8x1x2_RMS_1_useLogNormal_true', '8x1x2_RMS_2_useLogNormal_true']]
	list_16x1x2_lognormals_gevb2g = [ prefix + 'gevb2g/dummyFerol/' + x for x in ['16x1x2_RMS_0_useLogNormal_false', '16x1x2_RMS_0.5_useLogNormal_true', '16x1x2_RMS_1_useLogNormal_true', '16x1x2_RMS_2_useLogNormal_true']]
	list_x1x2_lognormals_gevb2g   = [ prefix + 'gevb2g/dummyFerol/' + x for x in ['8x1x2_RMS_0_useLogNormal_false', '8x1x2_RMS_1_useLogNormal_true', '16x1x2_RMS_0_useLogNormal_false', '16x1x2_RMS_1_useLogNormal_true']]
	list_8x1x4_lognormals_EvB     = [ prefix + 'EvB/' + x for x in ['8x1x4_RMS_0_useLogNormal_false',  '8x1x4_RMS_0.5_useLogNormal_true',  '8x1x4_RMS_1_useLogNormal_true',  '8x1x4_RMS_2_useLogNormal_true']]
	list_12x1x4_lognormals_EvB    = [ prefix + 'EvB/' + x for x in ['12x1x4_RMS_0_useLogNormal_false', '12x1x4_RMS_0.5_useLogNormal_true', '12x1x4_RMS_1_useLogNormal_true', '12x1x4_RMS_2_useLogNormal_true']]
	list_16x1x4_lognormals_EvB    = [ prefix + 'EvB/' + x for x in ['16x1x4_RMS_0_useLogNormal_false', '16x1x4_RMS_0.5_useLogNormal_true', '16x1x4_RMS_1_useLogNormal_true', '16x1x4_RMS_2_useLogNormal_true']]
	list_16x2x4_lognormals_EvB    = [ prefix + 'EvB/' + x for x in ['16x2x4_RMS_0_useLogNormal_false', '16x2x4_RMS_0.5_useLogNormal_true', '16x2x4_RMS_1_useLogNormal_true', '16x2x4_RMS_2_useLogNormal_true']]
	list_32x2x4_lognormals_EvB    = [ prefix + 'EvB/' + x for x in ['32x2x4_RMS_0_useLogNormal_false', '32x2x4_RMS_0.5_useLogNormal_true', '32x2x4_RMS_1_useLogNormal_true', '32x2x4_RMS_2_useLogNormal_true']]
	list_x1x4_lognormals_EvB      = [ prefix + 'EvB/' + x for x in ['8x1x4_RMS_0_useLogNormal_false',  '8x1x4_RMS_1_useLogNormal_true',    '16x1x4_RMS_0_useLogNormal_false', '16x1x4_RMS_1_useLogNormal_true']]

	outputdir = createDir(outDir+'eFEROLs/gevb2g/Aug13/')
	makeMultiPlot(rootfile_clean, list_8x1x2_lognormals_gevb2g,  oname=outputdir+'8x1x2_lognormals_gevb2g.pdf',  tag='eFEROL:gevb2g')
	makeMultiPlot(rootfile_clean, list_16x1x2_lognormals_gevb2g, oname=outputdir+'16x1x2_lognormals_gevb2g.pdf', tag='eFEROL:gevb2g')
	makeMultiPlot(rootfile_clean, list_x1x2_lognormals_gevb2g,   oname=outputdir+'x1x2_lognormals_gevb2g.pdf',   tag='eFEROL:gevb2g')
	makeMultiPlot(rootfile_clean, list_x1x2_lognormals_gevb2g,   rangex=(1500, 150000), oname=outputdir+'x1x2_lognormals_gevb2g_sufrag.pdf', frag=False, tag='eFEROL:gevb2g')

	outputdir = createDir(outDir+'eFEROLs/EvB/Aug13/')
	makeMultiPlot(rootfile_clean, list_x1x4_lognormals_EvB,      oname=outputdir+'x1x4_lognormals_EvB.pdf',      tag='eFEROL:EvB')
	makeMultiPlot(rootfile_clean, list_8x1x4_lognormals_EvB,     oname=outputdir+'8x1x4_lognormals_EvB.pdf',     tag="eFEROL:EvB")
	makeMultiPlot(rootfile_clean, list_12x1x4_lognormals_EvB,    oname=outputdir+'12x1x4_lognormals_EvB.pdf',    tag="eFEROL:EvB")
	makeMultiPlot(rootfile_clean, list_16x1x4_lognormals_EvB,    oname=outputdir+'16x1x4_lognormals_EvB.pdf',    tag="eFEROL:EvB")
	makeMultiPlot(rootfile_clean, list_16x2x4_lognormals_EvB,    oname=outputdir+'16x2x4_lognormals_EvB.pdf',    tag="eFEROL:EvB")
	makeMultiPlot(rootfile_clean, list_32x2x4_lognormals_EvB,    oname=outputdir+'32x2x4_lognormals_EvB.pdf',    tag="eFEROL:EvB")
	makeMultiPlot(rootfile_clean, list_x1x4_lognormals_EvB,      rangex=(1500, 150000), oname=outputdir+'x1x4_lognormals_EvB_sufrag.pdf',    frag=False, tag='eFEROL:EvB')


	prefix = 'data/%s/eFEROLs/EvB/'
	outputdir = createDir(outDir+'eFEROLs/EvB/Aug28/')
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']

	list_32x4x4_c6220  = [prefix % 'Aug28' + '32x4x4_RMS_0.0_c6220']
	list_32x4x4_c6220 += [prefix % 'Aug28' + '32x4x4_RMS_0.5_c6220']
	list_32x4x4_c6220 += [prefix % 'Aug28' + '32x4x4_RMS_1.0_c6220']
	list_32x4x4_c6220 += [prefix % 'Aug28' + '32x4x4_RMS_2.0_c6220']
	makeMultiPlot(rootfile, list_32x4x4_c6220, oname=outputdir+'32x4x4_c6220.pdf', tag='eFEROL:EvB', legends=map(lambda x:'32x4x4 (C6220), ' + x, legends))

	prefix = 'data/%s/eFEROLs/gevb2g/'
	outputdir = createDir(outDir+'eFEROLs/gevb2g/Aug29/')
	legends = ['RMS 0.0', 'RMS 0.5', 'RMS 1.0', 'RMS 2.0']

	list_32x4x4_c6220  = [prefix % 'Aug29' + '32x4x4_RMS_0.0_c6220']
	list_32x4x4_c6220 += [prefix % 'Aug29' + '32x4x4_RMS_0.5_c6220']
	list_32x4x4_c6220 += [prefix % 'Aug29' + '32x4x4_RMS_1.0_c6220']
	list_32x4x4_c6220 += [prefix % 'Aug29' + '32x4x4_RMS_2.0_c6220']
	makeMultiPlot(rootfile, list_32x4x4_c6220, oname=outputdir+'32x4x4_c6220.pdf', tag='eFEROL:gevb2g', legends=map(lambda x:'32x4x4 (C6220), ' + x, legends))


##---------------------------------------------------------------------------------
## User interface
if __name__ == "__main__":
	from optparse import OptionParser
	usage = """
	Use to create a batch of standard plots:
	%prog  --outDir plots/ data.root
	"""

	parser = OptionParser(usage=usage)
	parser.add_option("-o", "--outDir", default="plots/", action="store", type="string", dest="outDir",
	                  help="Output directory for the plots [default: %default]")
	# parser.add_option("--makePNGs",     default=True,     action="store_true", dest="makePNGs",
	#                   help="Produce also .png files [default: %default]")


	(options, args) = parser.parse_args()

	if len(args) > 0:
		makeStandardPlots(args[0], outDir=options.outDir)
		exit(0)

	makeStandardPlots('data.root', outDir=options.outDir)
	exit(0)

	# parser.print_help()
	# exit(-1)



