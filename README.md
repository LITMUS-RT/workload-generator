# LITMUS^RT Random Workload Generator

This repository contains tools that help with setting up and running (a large number of) synthetic, randomly generated real-time workloads under [LITMUS^RT](http://www.litmus-rt.org). This is useful for instance when stress testing LITMUS^RT on a new platform or when rebasing to a new base Linux version, and can also be useful to collect and analyze runtime overheads.

## Synopses

### `mktasks.py`

**Purpose**: Generate feasible periodic task sets for a given number of cores, number of tasks, utilization, etc. 

```
usage: mktasks.py [-h] [--prefix PREFIX] [-m [NCORES [NCORES ...]]]
                  [-s [NSOCKETS [NSOCKETS ...]]] [-n [NTASKS [NTASKS ...]]]
                  [-t [NTASKS_PER_CORE [NTASKS_PER_CORE ...]]]
                  [-u [UTILS [UTILS ...]]] [--apa {partitioned,random,socket}]
                  [-c COUNT]

LITMUS^RT workload generator

optional arguments:
  -h, --help            show this help message and exit
  --prefix PREFIX       Prefix for the generated file[s]
  -m [NCORES [NCORES ...]], --num-cores [NCORES [NCORES ...]]
                        processor counts to consider [multiple possible]
  -s [NSOCKETS [NSOCKETS ...]], --num-sockets [NSOCKETS [NSOCKETS ...]]
                        socket counts to consider [multiple possible, default
                        1]
  -n [NTASKS [NTASKS ...]], --num-tasks [NTASKS [NTASKS ...]]
                        task counts to consider, absolute values [multiple
                        possible]
  -t [NTASKS_PER_CORE [NTASKS_PER_CORE ...]], --task-per-core [NTASKS_PER_CORE [NTASKS_PER_CORE ...]]
                        task counts to consider, relative to -m [default 5]
  -u [UTILS [UTILS ...]], --per-core-utilization [UTILS [UTILS ...]]
                        average processor utilizations to consider [multiple
                        possible]
  --apa {partitioned,random,socket}
                        what sort of affinities to generate [default:
                        partitioned]
  -c COUNT, --count COUNT
                        how many task sets per #cores, #tasks, and util
```

The task sets are generated using Emberson et al.’s method as described in their paper:

- P. Emberson, R. Stafford, and R. Davis, “[Techniques For The Synthesis of
Multiprocessor Tasksets](https://www.cs.york.ac.uk/ftpdir/papers/rtspapers/R:Emberson:2010a.pdf)”, In: *Proceedings of the  proceedings 1st International Workshop on Analysis Tools and Methodologies for Embedded and Real-time Systems* (WATERS’10), 2010.

Periods are chosen from a log-uniform distribution ranging from 1 millisecond to 1 second, in steps of integral milliseconds. 


### `mkscript.py`

**Purpose**: generate shell scripts that set-up, execute, and tear-down experiments under LITMUS^RT. 

```
usage: mkscript.py [-h] [-S] [-O] [-D] [-t DURATION] [-w WSS] [-b BG_WSS]
                   [-p PLUGIN] [--dsp SERVICE_CORE] [--prefix PREFIX]
                   [input-files [input-files ...]]

LITMUS^RT setup script generator

positional arguments:
  input-files           task set descriptions in JSON format

optional arguments:
  -h, --help            show this help message and exit
  -S, --trace-schedule  Record the schedule with sched_trace
  -O, --trace-overheads
                        Record runtime overheads with Feather-Trace
  -D, --trace-debug-log
                        Record TRACE() messages [debug feature]
  -t DURATION, --duration DURATION
                        how long should the experiment run?
  -w WSS, --wss WSS     default working set size of RT tasks [in KiB]
  -b BG_WSS, --bg-memory BG_WSS
                        working set size of background cache-thrashing tasks
                        [in KiB]
  -p PLUGIN, --scheduler PLUGIN
                        Which scheduler plugin to use?
  --dsp SERVICE_CORE    Which core is the dedicated service processor?
                        Relevant only for message-passing plugins.
  --prefix PREFIX       Where to store the generated script[s]?  
```

## Quick Walkthrough 

First, we create some feasible sets of periodic, CPU-bound real-time tasks. 

The following command creates task sets for **4, 8, and 16 cores**, with **2, 5, and 10 tasks per core**, and a total utilization of **30%, 50%, and 70%**, and stores the resulting JSON files in the directory `/tmp/demo`.
	
	./mktasks.py -m 4 8 16 -t 2 5 10 -u 0.3 0.5 0.7 --prefix /tmp/demo/

Output:

	[pre-partitioned, 4 cores, 0.30 utilization, 2.00 tasks per core]
	=> /tmp/demo/part-workload_m=04_n=08_u=30_seq=00.json
	[pre-partitioned, 4 cores, 0.30 utilization, 5.00 tasks per core]
	=> /tmp/demo/part-workload_m=04_n=20_u=30_seq=00.json
	[...]
	[pre-partitioned, 16 cores, 0.70 utilization, 10.00 tasks per core]
	=> /tmp/demo/part-workload_m=16_n=160_u=70_seq=00.json

Each generated JSON file contains a simple task set description. The word “partitioned” in the file names refers to the fact that all generated task sets are by construction feasible under partitioned scheduling (e.g., with P-EDF).

In the second step, we generate shell scripts that set up and tear down experiments under LITMUS^RT, optionally with a variety of tracers.

The following command converts the just-generated task sets into executable shell scripts. In particular, we generate scripts for the **partitioned fixed-priority (P-FP) plugin** of LITMUS^RT that will execute each task set for **30 seconds** while collecting **kernel overheads with Feather-Trace**. The resulting shell scripts are stored in the folder `/tmp/pfp-exp’.

	./mkscript.py --scheduler P-FP --duration 30 --trace-overheads --prefix /tmp/pfp-scripts/ /tmp/demo/*.json	

Output: 

	Processing /tmp/demo/part-workload_m=04_n=08_u=30_seq=00.json -> /tmp/pfp-scripts/part-workload_m=04_n=08_u=30_seq=00.sh
	Processing /tmp/demo/part-workload_m=04_n=08_u=50_seq=00.json -> /tmp/pfp-scripts/part-workload_m=04_n=08_u=50_seq=00.sh
	[...]
	Processing /tmp/demo/part-workload_m=16_n=80_u=70_seq=00.json -> /tmp/pfp-scripts/part-workload_m=16_n=80_u=70_seq=00.sh


The resulting bash scripts can be directly executed under LITMUS^RT (root privileges required).

Example:

```
bbb@rts5:/tmp/pfp-scripts$ sudo -s
[sudo] password for bbb: 
root@rts5:/tmp/pfp-scripts# ./part-workload_m\=04_n\=08_u\=50_seq\=00.sh 
Running part-workload_m=04_n=08_u=50_seq=00 for 30 seconds under P-FP...
Launching Feather-Trace overhead tracer... ok.
Released 8 real-time tasks.
. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 
All tasks finished.
Sent SIGTERM to stop background tasks...
Sent SIGUSR1 to stop tracers...
Disabling 4 events.
Disabling 18 events.
Disabling 18 events.
Disabling 18 events.
Disabling 18 events.
Disabling 4 events.
Disabling 4 events.
Disabling 4 events.
/dev/litmus/ft_cpu_trace0: 2529840 bytes read.
/dev/litmus/ft_cpu_trace2: 889632 bytes read.
/dev/litmus/ft_cpu_trace1: 809328 bytes read.
/dev/litmus/ft_msg_trace0: 64 bytes read.
/dev/litmus/ft_msg_trace3: 0 bytes read.
/dev/litmus/ft_cpu_trace3: 3966624 bytes read.
/dev/litmus/ft_msg_trace1: 32 bytes read.
/dev/litmus/ft_msg_trace2: 64 bytes read.
```

The overhead trace files resulting from the `--trace-overheads` flag of `mkscript.py` can be processed and analyzed as described in the [Feather-Trace documentation](https://github.com/LITMUS-RT/feather-trace-tools/blob/master/doc/howto-trace-and-process-overheads.md).

When using the `--trace-schedule` flag of `mkscript.py`, the experiment scripts will generate `sched_trace` files that can be processed and analyzed as described in the [`sched_trace` documentation](https://github.com/LITMUS-RT/feather-trace-tools/blob/master/doc/howto-trace-and-analyze-a-schedule.md).

# Installation Instructions

The scripts should work on any recent Linux and can also be used under macOS (with Homebrew).

## Dependencies

- Python 2.7
- SchedCAT --- [The Schedulability test Collection   
And Toolkit](https://people.mpi-sws.org/~bbb/projects/schedcat), for the random generation of task parameters.

SchedCAT in turn requires:

-  the [Simplified Wrapper and Interface Generator](http://swig.org) (SWIG)
- the [GNU Multiple Precision Arithmetic Library](https://gmplib.org) (GMP)
- the [GNU Linear Programming Kit](https://www.gnu.org/software/glpk/) (GLPK)
- a C++ compiler

Any recent versions of these libraries should work.

## Step-by-Step Instructions

There are two steps:

1. Get and compile [SchedCAT](https://people.mpi-sws.org/~bbb/projects/schedcat), a library for Python 2.7, and
2. make sure that `import schedcat` works.

At the time of writing, Python 3 is not yet supported.

### Clone and Compile SchedCAT

First, clone the SchedCAT repository. In the following, we use `~/my-projects` as a placeholder for some work directory.

	cd ~/my-projects
	git clone https://github.com/brandenburg/schedcat.git
	
Next, compile the project. On Linux, with all dependencies installed, this should work out of the box. 

	cd schedcat
	make

(Tested on Debian Linux 8.7.)

**Note:** SchedCAT is required only for `mktasks.py` and *not* for `mkscript.py`, nor at runtime to actually execute the generated workloads.

### Making the `schedcat` Module Available

We need to make sure that Python can successfully import the `schedcat` module. This can be accomplished either by setting the `PYTHONPATH` environment variable or with a symbolic link. We use the latter approach since it is stable across shell sessions. 

Clone the LITMUS^RT Random Workload Generator repository  (i.e., this repository) into `~/my-projects/workload-generator/`.

	cd ~/my-projects
	git clone https://github.com/LITMUS-RT/workload-generator.git

Assuming the `schedcat` repository has been cloned to `~/my-projects/schedcat`, we are going to create a symbolic link from `~/my-projects/workload generator/schedcat` to `~/my-projects/schedcat/schedcat` (note that the target is the `schedcat` directory *inside* the checkout of  SchedCAT repository).

	cd workload-generator
	ln -S ~/my-projects/workload generator/schedcat

At this point, both `mktasks.py` and `mkscript.py` should work.

# Contact

Patches and improvements welcome. Please fork and create a pull request. If you have questions, comments, suggestions, and for general discussion, please contact the [LITMUS^RT mailing list](https://wiki.litmus-rt.org/litmus/Mailinglist). 

# License

(c) 2017 B. Brandenburg. Released under the BSD license. 