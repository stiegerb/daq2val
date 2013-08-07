#!/usr/bin/env python

from math import exp, sqrt, log

try:
    # works on lxplus but not on cmsusr
    # (nor on the SLC6 nodes in daqval2)
    #
    # python2.7 has erf in the math module but
    # even SLC6 does not have python 2.7

    from scipy.special import erf
except ImportError,ex:

    # define erf ourselves.
    #
    # taken from http://stackoverflow.com/a/457805/288875
    # (with some modifications to get this to work in python2.6)
    def erf(x):

        import math
        # save the sign of x
        if x >= 0:
            sign = 1
        else:
            sign = -1

        x = abs(x)

        # constants
        a1 =  0.254829592
        a2 = -0.284496736
        a3 =  1.421413741
        a4 = -1.453152027
        a5 =  1.061405429
        p  =  0.3275911

        # A&S formula 7.1.26
        t = 1.0/(1.0 + p*x)
        y = 1.0 - (((((a5*t + a4)*t) + a3)*t + a2)*t + a1)*t*math.exp(-x*x)
        return sign*y # erf(-x) = -erf(x)

#----------------------------------------------------------------------

# indefinite integral of x * lognormal(normalMean,normalSigma)
def integFuncTimesX(x, normalMean, normalSigma):
    return -(exp(normalMean + normalSigma**2/2.) * \
      erf((normalMean + normalSigma**2 - log(x))/(sqrt(2)*normalSigma)))/2.

#----------------------------------------------------------------------

# indefinite integral of lognormal
def integLogNormal(x, normalMean, normalSigma):
    return -erf((normalMean - log(x))/(sqrt(2)*normalSigma))/2.


def logNormalCDF(x, normalMean, normalSigma):
    """ the cumulative density function (i.e. the integral
    with a constant added such that it is zero at x = 0)
    """

    return 0.5 * (1 + erf(
        (log(x) - normalMean)/(sqrt(2)*normalSigma)))

#----------------------------------------------------------------------

def calcNormalMeanAndSigma(mean, sigma):

    mean = float(mean)
    sigma = float(sigma)

    # taken from http://www.boost.org/doc/libs/1_ 41_ 0/libs/random/random-distributions.html# lognormal_distribution
    normalMean = log(mean**2 / sqrt(sigma**2 + mean**2))
    normalSigma = sqrt(log(1+sigma**2 / mean**2))

    return normalMean, normalSigma

#----------------------------------------------------------------------
# the function calculating the effective average fraction size
# after truncation
#----------------------------------------------------------------------

### def averageFractionSize(mean, sigma, lowerLimit, upperLimit):
###     """ note, this does NOT take into account any effect
###     of rounding the random value to the nearest integer
###     (which should however be a small effect, especially
###     at large means)
###     """
###
###     # convert from mean/sigma to normalMean / normalSigma
###     normalMean, normalSigma = calcNormalMeanAndSigma(mean, sigma)
###
###     # calculate average fragment size
###     numerator = integFuncTimesX(upperLimit, normalMean, normalSigma) - \
###                 integFuncTimesX(lowerLimit, normalMean, normalSigma)
###
###     # normalization term
###     denominator = integLogNormal(upperLimit, normalMean, normalSigma) - \
###                   integLogNormal(lowerLimit, normalMean, normalSigma)
###
###     return numerator / denominator
###

#----------------------------------------------------------------------
def averageFractionSize(mean, sigma, lowerLimit, upperLimit):
    """version which includes 'capping' of the fragment
    size at the lower and upper bound
    """

    # convert from mean/sigma to normalMean / normalSigma
    normalMean, normalSigma = calcNormalMeanAndSigma(mean, sigma)

    #----------

    # fraction of events below and above limits
    fracBelow = logNormalCDF(lowerLimit, normalMean, normalSigma)

    fracAbove = 1 - logNormalCDF(upperLimit, normalMean, normalSigma)

    # fraction of unmodified fragment sizes
    fracBulk = 1 - (fracBelow + fracAbove)

    #----------

    # integral of x times p(x) between the lower and upper limit
    integBulk = integFuncTimesX(upperLimit, normalMean, normalSigma) - \
                integFuncTimesX(lowerLimit, normalMean, normalSigma)

    # no denominator any more because the weights
    # sum up to one

    return fracBelow * lowerLimit + \
           integBulk  + \
           fracAbove * upperLimit

#----------------------------------------------------------------------

def averageFractionSizeSampling(mean, sigma, lowerLimit, upperLimit, numSamples = 1000000):
    """ calculates the average fraction size by just generating
    fragment lengths and restricting them to the boundaries if outside """

    # convert from mean/sigma to normalMean / normalSigma
    normalMean, normalSigma = calcNormalMeanAndSigma(mean, sigma)

    sumValues = 0
    numGenerated = 0

    import random

    while numGenerated < numSamples:

        # draw a number
        value = random.lognormvariate(normalMean, normalSigma)

        if value < lowerLimit:
            value = lowerLimit

        if value > upperLimit:
            value = upperLimit

        sumValues += value
        numGenerated += 1

    return sumValues / float(numGenerated)


#----------------------------------------------------------------------

def averageFractionSizeSamplingWithRounding(mean, sigma, lowerLimit, upperLimit, numSamples = 1000000, wordsize = 4):
    """ samples from the lognormal distribution, rounds to the nearest
        word size and caps at lower and upper limit """

    wordsize = float(wordsize)

    # convert from mean/sigma to normalMean / normalSigma
    normalMean, normalSigma = calcNormalMeanAndSigma(mean, sigma)

    sumValues = 0
    numGenerated = 0

    import random

    while numGenerated < numSamples:

        # draw a number
        value = random.lognormvariate(normalMean, normalSigma)

        # round to nearest word size
        value = round(value / wordsize) * wordsize

        # cap at lower and upper bound
        if value < lowerLimit:
            value = lowerLimit

        if value > upperLimit:
            value = upperLimit

        sumValues += value
        numGenerated += 1

    return sumValues / float(numGenerated)



# #----------------------------------------------------------------------
# # main (test program)
# #----------------------------------------------------------------------
# import sys
# ARGV = sys.argv[1:]

# if len(ARGV) == 0:
#     doPlot = True
#     lowerLimit, upperLimit = 32, 262000

#     # for testing
#     # lowerLimit, upperLimit = 1e-9, 1e9

#     # mean = 40256 ; sigma = mean ; numSamples = 50000000
#     # mean = 40256 ; sigma = 2 * mean ; numSamples = 10000000

#     # mean = 256   ; sigma = mean ; numSamples = 1000000
#     # mean = 256   ; sigma = 2 * mean ; numSamples = 1000000

#     mean = 60256 ; sigma = mean ; numSamples = 50000000
#     # mean = 60256 ; sigma = 2 * mean ; numSamples = 50000000

#     #--------------------
#     # test results:
#     #--------------------
#     # mean   sigma        number of samples   analytical     sampling        sampling/analytical - 1
#     #                                                        (without
#     #                                                         rounding)
#     #
#     # 40256  mean                50'000'000   39918.2824564  39907.7074523     -0.03 %
#     # 40256  2 * mean            10'000'000   36768.3382446  36784.7727597     +0.04 %
#     # 256    2 * mean             1'000'000   258.095868254  257.901741485     -0.08 %
#     # 256    256                  1'000'000   256.141548247  256.126371356   -5.9e-3 %
#     # 60256  mean                50'000'000   58730.8488662  58716.5144495     -0.02 %
#     # 60256  2 * mean            50'000'000   51737.8826898  51736.6273017   -2.4e-3 %

# else:
#     # numbers specified on command line
#     if len(ARGV) != 2:
#         print >> sys.stderr,"must specify none or exactly two command line arguments (mean and sigma)"
#         sys.exit(1)

#     mean,sigma = [ float(x) for x in ARGV ]
#     numSamples = None

#     doPlot = False

# print "analytical average fragment size for mean=",mean,"sigma=",sigma,"is",averageFractionSize(mean,sigma, lowerLimit, upperLimit)


# if numSamples != None:
#     print "sampling average fragment size for mean=",mean,"sigma=",sigma,"is",averageFractionSizeSampling(mean,sigma, lowerLimit, upperLimit, numSamples = numSamples)
#     print "rounded sampling average fragment size for mean=",mean,"sigma=",sigma,"is",averageFractionSizeSamplingWithRounding(mean,sigma, lowerLimit, upperLimit, numSamples = numSamples)

# #----------------------------------------

# if doPlot:
#     #----------------------------------------
#     # plot the different cases
#     #----------------------------------------
#     import pylab
#     means = pylab.linspace(256,70000,1000 + 1)

#     allTitles = []

#     for sigmaFunc, title in (
#         (lambda mean: 0.01 * mean, 'sigma = 0.01 * mean'),
#         (lambda mean: 0.5 * mean,  'sigma = 0.5 * mean'),
#         (lambda mean: mean,        'sigma = mean'),
#         (lambda mean: 2 * mean,    'sigma = 2 * mean'),
#         ):

#         pylab.plot(means, [ averageFractionSize(mean,sigmaFunc(mean), lowerLimit, upperLimit) / float(mean) for mean in means] ,linewidth = 2)

#         allTitles.append(title)


#     pylab.xlabel('mean parameter given to generator')
#     pylab.ylabel('average fragment size after truncation divided by mean')
#     pylab.grid()
#     pylab.legend(allTitles)
#     pylab.show()
