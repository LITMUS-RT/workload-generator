#!/usr/bin/env python

from __future__ import division

from os.path import basename

import sys
import json

def us2ms(x):
    return x / 1000

APA_SCHEDULERS = frozenset([
    'LSA-FP-MP',
])

PREAMBLE = """
#!/bin/bash
RTPID=""
TRACERS=""

DURATION={duration}

echo Running {name} for $DURATION seconds...

setsched Linux
if [ "$?" -ne 0 ]
then
    echo "Could not switch to Linux"
    exit 1
fi

echo 0 > /proc/litmus/release_master
if [ "$?" -ne 0 ]
then
    echo "Could not set release master"
    exit 1
fi

setsched {scheduler}
if [ "$?" -ne 0 ]
then
    echo "Scheduler {scheduler} could not be activated"
    exit 1
fi

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

"""

DEBUG_TRACE = """
cat /dev/litmus/log > {name}.log &
TRACERS="$TRACERS $!"
"""

OVERHEAD_TRACE = """
which ft-trace-overheads > /dev/null
if [ "$?" -ne 0 ]
then
    echo "Cannot find ft-trace-overheads in PATH"
    die
fi
ft-trace-overheads -s {name} &
TRACERS="$TRACERS $!"
"""

SCHEDULE_TRACE = """
which st_trace > /dev/null
if [ "$?" -ne 0 ]
then
    echo "Cannot find st_trace in PATH"
    die
fi
st_trace -s {name} &
TRACERS="$TRACERS $!"
"""

SET_AFFINITY = "taskset 0x{affinity_mask:x} "

RTSPIN = """rtspin -w -s {scale} -q {prio} {cost:.2f} {period:.2f} $DURATION &
RTPID="$RTPID $!"
"""

MAIN_EXP = """
release_ts -f {num_tasks}
progress_wait $DURATION
wait $RTPID
echo All tasks finished.
cleanup_tracers

setsched Linux
if [ "$?" -ne 0 ]
then
    echo "Could not switch back to Linux"
    exit 1
fi
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
        scheduler = scheduler,
        name = fname,
        duration = duration
    ))

    if want_debug:
        f.write(DEBUG_TRACE.format(name = fname))
    if want_overheads:
        f.write(OVERHEAD_TRACE.format(name = fname))
    if want_schedule:
        f.write(OVERHEAD_TRACE.format(name = fname))

    for id in data['tasks']:
        t = data['tasks'][id]
        if scheduler in APA_SCHEDULERS:
            f.write(SET_AFFINITY.format(affinity_mask = t['affinity_mask']))
        f.write(RTSPIN.format(
            affinity_mask = t['affinity_mask'],
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
    f.close()


def load_ts_from_json(fname):
    data = json.load(open(fname, 'r'))
    return data

def main(args=sys.argv[1:]):
    for fname in args:
        print 'Processing %s' %fname
        ts = load_ts_from_json(fname)
        generate_sh(basename(fname).replace('.json', ''), ts,
                    duration=30, scheduler="G-FP-MP",
                    want_debug=False, want_overheads=True, want_schedule=False)


if __name__ == '__main__':
    main()
