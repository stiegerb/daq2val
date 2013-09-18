---------------------------------------------------------------------
python (2.6) framework for running tests on the daq2val setups
---------------------------------------------------------------------

------------------------
daq2Config.py:

- Contains the daq2Config class:
  - Reads a template xdaq config.xml file and returns an object that will know the
    setup of the system.
  - Checks the config for EvB vs gevb2g cases, for GTPe (soon), etc.
  - Additional checks on the config file, such as enableStream0/1,
    Event_Length_Max_bytes_FED0/1, etc.
- Also contains the host and FEROL classes.


------------------------
daq2SymbolMap.py:

- Contains the daq2SymbolMap class:
  - Reads the daq2 symbolmap and fills dictionaries for each host
  - Class object can be called with the keys directly, or with a host keys, i.e.:
    >>> sm = daq2SymbolMap(file)
    >>> sm('GTPE0_SOAP_HOST_NAME')  ## will return 'dvfmmpc-C2F31-06-01.cms'
    or:
    >>> h = sm('GTPE0')
    >>> h.host  ## will return the same: 'dvfmmpc-C2F31-06-01.cms'
    etc.


------------------------
daq2Launchers.py:

- Script to start, stop, and check status of xdaqLaunchers
- The only noteworthy addition to previously existing scripts is the ability to redirect the output to a logfile


------------------------
daq2Utils.py:

- Collection of general utilities for communicating with the xdaq processes
- Some are just wrappers for the existing perl scripts, others are re-implemented in python
- stopXDAQs and others are using multiprocessing to speed up the script


------------------------
daq2Control.py:

- Contains the daq2Control class:
  - Is initialized with a .xml config file and uses daq2Config and daq2SymbolMap to
    set up a test system which can then be started and controlled
  - This replaces the previous control scripts


------------------------
runDAQ2Test.py:

- Interface to daq2Control, always takes a template .xml file as first argument
- Can be used to just start/stop a running system, or change the fragment size of a running system
- Main functionality is to run a scan of fragment sizes with --runScan
- Can also run a set of scans with different rms values

