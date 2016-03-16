#!/usr/bin/env python

PREAMBLE = """
#!/bin/bash
RTPID=""
TRACERS=""

DURATION={duration}

echo "Running {name} for $DURATION seconds..."

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

function cleanup_tasks()
{{
    if [ -n "$RTPID" ]
    then
        kill $RTPID
        echo "Sent SIGTERM to stop experiment tasks..."
        wait $RTPID
    fi
}}

function die()
{{
    cleanup_tasks
    cleanup_tracers
    setsched Linux
    exit 1
}}

trap 'die' SIGUSR1 SIGTERM SIGINT

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
{taskset}cat /dev/litmus/log > {name}.log &
TRACERS="$TRACERS $!"
"""

OVERHEAD_TRACE = """
which ft-trace-overheads > /dev/null
if [ "$?" -ne 0 ]
then
    echo "Cannot find ft-trace-overheads in PATH"
    die
fi
{taskset}ft-trace-overheads -s {name} &
TRACERS="$TRACERS $!"
"""

SCHEDULE_TRACE = """
which st_trace > /dev/null
if [ "$?" -ne 0 ]
then
    echo "Cannot find st_trace in PATH"
    die
fi
{taskset}st_trace -s {name} &
TRACERS="$TRACERS $!"
"""

SET_AFFINITY_MASK = "taskset 0x{affinity_mask:x} "
SET_AFFINITY = "taskset -c {core_list} "

RTSPIN = """
{taskset}rtspin -w -s {scale} -q {prio} {cost:.2f} {period:.2f} $DURATION &
RTPID="$RTPID $!"
"""

MAIN_EXP = """
release_ts -f {num_tasks}
progress_wait $DURATION
wait $RTPID
echo All tasks finished.
cleanup_tracers
"""
