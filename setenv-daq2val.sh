# XDAQ
export XDAQ_ROOT=/opt/xdaq
export XDAQ_LOCAL=/opt/xdaq
export XDAQ_SETUP_ROOT=${XDAQ_ROOT}/share

export XDAQ_PLATFORM=`uname -m`
if test ".$XDAQ_PLATFORM" != ".x86_64"; then
    export XDAQ_PLATFORM=x86
fi
checkos=`$XDAQ_ROOT/config/checkos.sh`
export XDAQ_PLATFORM=$XDAQ_PLATFORM"_"$checkos

export XDAQ_RUBUILDER=${XDAQ_ROOT}
export XDAQ_DOCUMENT_ROOT=${XDAQ_ROOT}/htdocs
export LD_LIBRARY_PATH=${XDAQ_RUBUILDER}/lib:${XDAQ_ROOT}/lib:${LD_LIBRARY_PATH}
export PATH=${PATH}:${XDAQ_RUBUILDER}/bin:${XDAQ_ROOT}/bin

# RU builder tester
WORKINGDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" # get location of this file
export RUB_TESTER_HOME=${WORKINGDIR}
export TESTS_SYMBOL_MAP=${RUB_TESTER_HOME}/daq2valSymbolMap.txt
export TEST_TYPE=daq2val

export PATH=${PATH}:${RUB_TESTER_HOME}/daq2Control
export PATH=${PATH}:${RUB_TESTER_HOME}/daq2Control/scripts
export XDAQ_SHARED=/tmp

