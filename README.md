----------------------------------------------------------
### Get the scripts (do it once)

- Make a new folder (or use a pre-existing one):
     - `mkdir daq2test`

- Get the scripts:
     - `git clone /nfshome0/stiegerb/Workspace/daq2val && cd daq2val`
     - `git checkout production`

- To get a new version simply do:
     - `git pull`

----------------------------------------------------------
### Setup (do it once before running)

- ssh to dvsrv-C2F36-07-01 (or any other machine that has python 2.6+ and can ssh to the daq2 system)
	- `ssh dvsrv-C2F36-07-01`

- Get a kerberos token:
	- `kinit`

- Change into the working directory (`daq2test/daq2val/` in the example above):
	- `cd daq2test/daq2val/`

- Set the environment:
	- `source setenv-daq2.sh`

	or, when running on the daq2val system:
	- `source setenv-daq2val.sh`

- Start launchers:
(make sure the symbol map makes sense and that you can ssh to each of the machines with no password or key query)
	- `./daq2Control/daq2Launchers.py --start -m daq2SymbolMap.txt  -l /tmp/launcherLog.txt`

- To follow the xdaq output (best in a new window):
	- `tail -f /tmp/launcherLog.txt`

- To stop the launchers again:
	- `./daq2Control/daq2Launchers.py --stop -m daq2SymbolMap.txt`

- Check launcher status:
	- `./daq2Control/daq2Launchers.py --status -m daq2SymbolMap.txt`

----------------------------------------------------------
### Simple running (mostly for debugging)
- Note that you can do most of the following with `--dry` first to see what it will do without sending anything. For more options and help, use any of the scripts with `--help` (or `-h`).

- Start a config by using the `runDAQ2Test.py` script:
	- `./daq2Control/runDAQ2Test.py --start 12s12fx1x4_ibv.xml 4096 0.0 -v 5`

- To stop it again, use the `--kill` option:
	- `./daq2Control/runDAQ2Test.py --kill 12s12fx1x4_ibv.xml 4096 0.0 -v 5`

- You can also do the steps separately:
	- Setup:

	`./daq2Control/runDAQ2Test.py --prepare 12s12fx1x4_ibv.xml 4096 0.0 -v 5`
	- Configure:

	`./daq2Control/runDAQ2Test.py --configure 12s12fx1x4_ibv.xml 4096 0.0 -v 5`
	- Enable:

	`./daq2Control/runDAQ2Test.py --enable 12s12fx1x4_ibv.xml 4096 0.0 -v 5`
	- Stop (should get back to "Configured", but no guarantee):

	`./daq2Control/runDAQ2Test.py --stop 12s12fx1x4_ibv.xml 4096 0.0 -v 5`

	- For more options, use `--help`

----------------------------------------------------------
### Scanning (to do a measurement)
- Run a scan of fragment sizes over a single configuration:
	- `./daq2Control/runDAQ2Scan.py --stopRestart --maxSize 16000 --duration 120 12s12fx1x4_ibv.xml -v 5 -o output/`
	- To set a custom scanning range, use `--maxSize`, `--minSize`, and `--stepSize`, with the argument in bytes.
	- To set the duration for each step use `--duration` with an argument in seconds.
	- For all the options use `--help`, but note that some are not entirely bugfree...

- Run a scan of fragment sizes over a set of configurations:
	- `./daq2Control/scanAll.py --stopRestart --maxSize 16000 --duration 120 overnight/*.xml -v 5 -o output/output/`
	- `scanAll.py` takes all the same arguments as `runDAQ2Scan.py`


----------------------------------------------------------
### Configurator

- For EvB/gevb2g with FEROLs as input (run with `-h` to get all the options):
	- `./daq2Control/makeDAQ2Config.py 12s12fx1x4`
	- To use the gevb2g instead of Remi's EvB: `--useGevb2g`
	- To use UDAPL instead of IBV: `--useUDAPL`
	- To change the ferol running mode: `--ferolMode frl_autotrigger` (options are `ferol_emulator` (default), `frl_autotrigger`, `frl_gtpe_trigger`, `efed_slink_gtpe`)
	- For all the options, try `--help`

- For MStreamIO:
	- `./daq2Control/makeMSIOConfig.py 4x4`

- For gevb2g with input emulator:
	- `./daq2Control/makeMSIOConfig.py --useGevb2g 4x4`


----------------------------------------------------------
### Symbolmaps

- Create symbolmaps for the DAQ production system (this uses `2014-04-16-infiniband-ports.csv` as input. To blacklist machines, change the 0 to a 1 in the corresponding line/column):
	- `./daq2Control/makeDAQ2Symbolmap.py --nRUs 8 --nBUs 8 --splitBy 8 -v -o daq2SymbolMap_8x8.txt`
	- To take only N machines from one leaf: `--splitBy N`
	- To use only RU machines: `--useOnlyRUs`
	- To add a dedicated EVM machine: `--addEVM`
	- To maximally distribute the machines over all leafs: `--shuffle`
	- For all the options, try `--help`

- Print the cabling for a DAQ production system symbolmap:
	- `./daq2Control/printSwitchCabling.py customSymbolmap.txt`

----------------------------------------------------------
### Plotting

- To create a throughput vs fragment size plot from a .csv file obtained from a scan (or downloaded from the web archive), use the `plotData.py` script in the plotting subdir. Note that this needs python 2.7+ and ROOT with pyROOT to be installed:
	- `./plotting/plotData.py 1x1.csv 2x2.csv --legend '1x1' '2x2'`
- Some of the additional plotting options are:
	- `-o` to set the output file
	- `--minx`, `--maxx`, `--miny`, `--maxy` to set the plotting range
	- `--logy`, `--nologx` toggle logarithmic scale on y or x axis. Default is logarithmic in x.
	- `--tag TEXT`, `--subtag TEXT` to add text boxes on the canvas.
	- `--title`, `--titleX`, `--titleY` to set canvas title and axis labels
	- `--legend 'TEXT1' 'TEXT2' 'TEXT3'` to set the legend. Number of arguments needs to match with the number of .csv files provided.
	- `--sizeFromBU`, take the fragment size from the BU measurement instead of from the input
	- `--rate` Set the rate curve (in kHz) to be displayed. Default is 100 kHz.

----------------------------------------------------------
### Troubleshoot

- If you get an error like this:
```
  File "./daq2Control/makeDAQ2Config.py", line 89
    configurator.evbns = ('gevb2g' if options.useGevb2g and not
                                    ^
SyntaxError: invalid syntax
```

	- Probably means you're on a machine with an old version of python (i.e. older than 2.6). Try `ssh dvsrv-C2F36-07-01`.


