#!/usr/bin/env python

PREAMBLE = """#!/bin/bash
RTPID=""
TRACERS=""
BG_TASKS=""

DURATION={duration}

echo "Running {name} for $DURATION seconds under {sched}..."

function progress_wait()
{{
    COUNT=0
    while (( $COUNT < $1 ))
    do
        echo -n ". "
        sleep 1
        COUNT=$((COUNT + 1))
    done
    echo
}}

function cleanup_tracers()
{{
    if [ -n "$TRACERS" ]
    then
        kill -SIGUSR1 $TRACERS
        echo "Sent SIGUSR1 to stop tracers..."
        wait $TRACERS
    fi
}}

function cleanup_background()
{{
    if [ -n "$BG_TASKS" ]
    then
        kill -SIGTERM $BG_TASKS
        echo "Sent SIGTERM to stop background tasks..."
        wait $BG_TASKS
    fi
}}

function cleanup_tasks()
{{
    if [ -n "$RTPID" ]
    then
        kill $RTPID
        echo "Sent SIGTERM to stop experiment tasks..."
        wait $RTPID
    fi
}}


function backup_file()
{{
	SRC=$1
	TGT=$2

	if [ -z "$TGT" ]
	then
		TGT=$SRC
	fi

	if ! [ -e "$TGT" ]
	then
		cp "$SRC" "$TGT"
	else
		CNT=1
		while [ -e "$TGT.$CNT" ]
		do
			CNT=$((CNT + 1))
		done
		cp "$SRC" "$TGT.$CNT"
	fi
}}

function die()
{{
    cleanup_background
    cleanup_tasks
    cleanup_tracers
    setsched Linux
    exit 1
}}

trap 'die' SIGUSR1 SIGTERM SIGINT

# Make sure the scheduler that we want to run actually is available.

if ! grep -q {sched} /proc/litmus/plugins/loaded 2>/dev/null
then
    echo "Error: scheduler {sched} is not supported by this kernel."
    die
fi

# Make sure we have access to liblitmus

which release_ts > /dev/null
if [ "$?" -ne 0 ]
then
    echo "Cannot find release_ts in PATH."
    echo "Make sure liblitmus is part of the shell's search path."
    die
fi

# Auto-discover cache topology

SOCKETS=`cat /sys/devices/system/cpu/*/topology/physical_package_id | sort | uniq`
declare -A CPUS_IN_SOCKET
for S in $SOCKETS
do
    CPUS_IN_SOCKET[$S]=`grep -l $S /sys/devices/system/cpu/*/topology/physical_package_id | egrep -o '[0-9]+'`
done

declare -a CORE
M=0
for S in $SOCKETS
do
	for C in ${{CPUS_IN_SOCKET[$S]}}
	do
		CORE[$M]=$C
		M=$((M + 1))
	done
done
"""

SET_DSP = """
echo "Setting processor {scheduling_core} to be the dedicated scheduling core."
echo {scheduling_core} > /proc/litmus/release_master
if [ "$?" -ne 0 ]
then
    echo "Could not set release master"
    die
fi
"""

SET_SCHEDULER = """
setsched {scheduler}
if [ "$?" -ne 0 ]
then
    echo "Scheduler {scheduler} could not be activated"
    die
fi
"""

DEBUG_TRACE = """
echo "Launching TRACE() debug tracer."
LOG_FILE="debug_host=$(hostname)_scheduler=$(showsched)_trace={name}.log"
# Check environmental variable
if ! [ -z "$KEEP_DEBUG_LOGS" ]
then
    # Keep a copy of the old log if we are debugging.
    [ -e $LOG_FILE ] && backup_file $LOG_FILE
fi
{taskset}cat /dev/litmus/log > $LOG_FILE &
TRACERS="$TRACERS $!"
"""

OVERHEAD_TRACE = """
# Make sure we have access to the ft-trace-overheads wrapper script
which ft-trace-overheads > /dev/null
if [ "$?" -ne 0 ]
then
    echo "Cannot find ft-trace-overheads in PATH"
    die
fi
echo -n "Launching Feather-Trace overhead tracer..."
FT_OUT=`mktemp`
{taskset}ft-trace-overheads -s {name} > "$FT_OUT" &
TRACERS="$TRACERS $!"
while ! grep -q 'Waiting for SIGUSR1' "$FT_OUT"
do
    sleep 0.1
done
echo ' ok.'
"""

PROCESS_OVERHEAD_TRACE = """
which ft-sort-traces > /dev/null
if [ "$?" -ne 0 ]
then
    echo "Cannot find ft-sort-traces in PATH"
    die
fi

function fail() {{
    echo
    echo "Overhead processing failed."
    exit 2
}}

echo "**** [{name}] ****" >> overhead-processing.log

# See https://github.com/LITMUS-RT/feather-trace-tools/blob/master/doc/howto-trace-and-process-overheads.md

# (1) Sort
echo -n "Sorting overhead traces..."
ft-sort-traces overheads_host=*_trace={name}_{{msg,cpu}}=*.bin >> overhead-processing.log 2>&1 || fail
echo " ok."
# (2) Split
echo -n "Extracting samples..."
ft-extract-samples overheads_host=*_trace={name}_{{msg,cpu}}=*.bin >> overhead-processing.log 2>&1 || fail
echo " ok."
# Clean up...
echo -n "Moving raw overhead files to $(pwd)/raw-overhead-files ..."
mkdir -p raw-overhead-files/ >> overhead-processing.log 2>&1 || fail
mv -v overheads_host=*_trace={name}_{{msg,cpu}}=*.bin raw-overhead-files/ >> overhead-processing.log 2>&1 || fail
echo " ok."
# (3) Combine
echo -n "Aggregating samples..."
ft-combine-samples --std overheads_host=*_trace={name}_{{msg,cpu}}=*_overhead=*.float32  >> overhead-processing.log 2>&1
echo " ok."
# Clean up...
echo -n "Moving aggregated sample files to $(pwd)/overhead-samples ..."
mkdir -p overhead-samples/ >> overhead-processing.log 2>&1 || fail
mv -v overheads_host=*_trace={name}_{{msg,cpu}}=*_overhead=*.float32 overhead-samples/ >>  overhead-processing.log 2>&1 || fail
echo " ok."
echo "Hint: run ft-compute-stats combined-overheads_*.float32 > stats.csv to obtain summary statistics."
"""

SCHEDULE_TRACE = """
which st_trace > /dev/null
if [ "$?" -ne 0 ]
then
    echo "Cannot find st_trace in PATH"
    die
fi
echo -n "Launching sched_trace schedule tracer..."
ST_OUT=`mktemp`
{taskset}st_trace -s {name} > "$ST_OUT" &
TRACERS="$TRACERS $!"
while ! grep -q 'Waiting for SIGUSR1' "$ST_OUT"
do
    sleep 0.1
done
echo ' ok.'
"""

SET_AFFINITY_MASK = "taskset 0x{affinity_mask:x} "
SET_AFFINITY = "taskset -c {core_list} "

TASK_LAUNCH_PREFIX = """
echo -n "Launching {num_tasks} real-time tasks..."
"""

RTSPIN = """
# Task {tid}
{taskset}rtspin -w -s {scale} {partition} {prio} {reservation} {wss} {timer} {cost:.2f} {period:.2f} $DURATION &
RTPID="$RTPID $!"
"""

RT_LAUNCH = """
# Task {tid}
{taskset}rt_launch -w {partition} {prio} {reservation} {cost:.2f} {period:.2f} -- {cmd} &
RTPID="$RTPID $!"
# Launch killer task to timeout the launched command
(sleep $DURATION; kill $! 2>/dev/null) &
RTPID="$RTPID $!"
"""

TASK_LAUNCH_SUFFIX = """
# Wait for tasks to finish launching
release_ts -W {num_tasks}
echo ' ok.'
"""

MAIN_EXP = """
release_ts -f {num_tasks}
progress_wait $DURATION
wait $RTPID
echo All tasks finished.
cleanup_background
cleanup_tracers
"""

BACKGROUND_WORKLOAD="""
NUM_CPUS=`getconf _NPROCESSORS_ONLN`
echo -n "Launching $NUM_CPUS background tasks with a WSS of {wss_in_pages} pages each..."
for core in `seq 1 $NUM_CPUS`
do
        taskset -c $(($core - 1)) nice rtspin -B -m {wss_in_pages} &
        BG_TASKS="$BG_TASKS $!"
done
echo " ok."
"""
