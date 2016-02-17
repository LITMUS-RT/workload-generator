#!/usr/bin/env python

from __future__ import division

from os.path import basename
from os import chmod

import sys
import stat
import json

def us2ms(x):
    return x / 1000

APA_SCHEDULERS = frozenset([
    'LSA-FP-MP',
])

MP_SCHEDULERS = frozenset([
    'LSA-FP-MP',
    'G-FP-MP',
    'G-EDF-MP',
])

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

def generate_sh(fname, data,
                duration=30,
                scale=0.95,
                scheduler='LSA-FP-MP',
                want_debug=False,
                want_overheads=False,
                want_schedule=False):
    f = open(fname + '.sh', 'w')
    f.write(PREAMBLE.format(
        name = fname,
        duration = duration
    ))
    f.write(SET_SCHEDULER.format(scheduler = 'Linux'))

    core = lambda n: '${CORE[%d]}' % n

    if scheduler in MP_SCHEDULERS:
        max_cpu = 0
        for t in data['tasks'].itervalues():
            max_cpu = max(max_cpu, max(t['affinity']))
        max_cpu += 1

        trace_affinity = SET_AFFINITY.format(core_list = core(max_cpu))
        f.write(SET_DSP.format(scheduling_core = core(max_cpu)))
    else:
        trace_affinity = ''

    f.write(SET_SCHEDULER.format(scheduler = scheduler))

    if want_debug:
        f.write(DEBUG_TRACE.format(
            name = fname,
            taskset = trace_affinity
        ))
    if want_overheads:
        f.write(OVERHEAD_TRACE.format(
            name = fname,
            taskset = trace_affinity
        ))
    if want_schedule:
        f.write(OVERHEAD_TRACE.format(
            name = fname,
            taskset = trace_affinity
        ))

    for id in data['tasks']:
        t = data['tasks'][id]
        if scheduler in APA_SCHEDULERS:
            core_list = ",".join([core(x) for x in t['affinity']])
            affinity = SET_AFFINITY.format(core_list = core_list)
        else:
            affinity = ''
        f.write(RTSPIN.format(
            taskset       = affinity,
            prio          = t['priority'],
            cost          = us2ms(t['cost']),
            period        = us2ms(t['period']),
            duration      = duration,
            scale         = scale,
        ))
    f.write(MAIN_EXP.format(
        num_tasks = len(data['tasks']),
        duration  = duration,
    ))
    f.write(SET_SCHEDULER.format(scheduler = 'Linux'))
    f.close()
    chmod(fname + '.sh', stat.S_IRGRP | stat.S_IROTH | stat.S_IRWXU)


def load_ts_from_json(fname):
    data = json.load(open(fname, 'r'))
    return data

def main(args=sys.argv[1:]):
    for fname in args:
        name = basename(fname).replace('.json', '')
        print 'Processing %s -> %s' % (fname, name + '.sh')
        ts = load_ts_from_json(fname)
                    duration=30, scheduler="G-FP-MP",
                    want_debug=False, want_overheads=True, want_schedule=False)
        generate_sh(name, ts,


if __name__ == '__main__':
    main()
