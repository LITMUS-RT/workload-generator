#!/usr/bin/env python

from __future__ import division

import argparse
import sys

from os.path import basename, exists, dirname
from os import chmod, makedirs

import random
import sys
import stat
import json

from config import *
from templates import *

def us2ms(x):
    return x / 1000

def core(n):
    return '${CORE[%d]}' % n

def get_affinity(tsk_json):
    if 'affinity' in tsk_json:
        return tsk_json['affinity']
    elif 'partition' in tsk_json:
        return [tsk_json['partition']]
    elif 'core' in tsk_json:
        return [tsk_json['core']]
    else:
        # no affinity given -> default to core zero
        return [0]

def generate_sh(name, data,
                duration=30,
                scale=0.95,
                scheduler='P-FP',
                want_debug=False,
                want_overheads=False,
                process_overheads=False,
                want_schedule=False,
                default_wss=0,
                background_wss=0,
                service_core=None,
                want_nanosleep=False,
                prefix=''):
    fname = prefix + name + '.sh'
    f = open(fname, 'w')
    f.write(PREAMBLE.format(
        sched = scheduler,
        name = name,
        duration = duration
    ))
    f.write(SET_SCHEDULER.format(scheduler = 'Linux'))

    if scheduler in MP_SCHEDULERS:
        if service_core is None:
            max_cpu = 0
            for t in data['tasks'].itervalues():
                max_cpu = max(max_cpu, max(get_affinity(t)))
            max_cpu += 1
            service_core = max_cpu

        trace_affinity = SET_AFFINITY.format(core_list = core(service_core))
        f.write(SET_DSP.format(scheduling_core = core(service_core)))
    else:
        trace_affinity = ''

    f.write(SET_SCHEDULER.format(scheduler = scheduler))

    if background_wss > 0:
        f.write(BACKGROUND_WORKLOAD.format(wss_in_pages = background_wss))

    if want_debug:
        f.write(DEBUG_TRACE.format(
            name = name,
            taskset = trace_affinity
        ))
    if want_schedule:
        f.write(SCHEDULE_TRACE.format(
            name = name,
            taskset = trace_affinity
        ))

    num_tasks = len(data['tasks'])

    f.write(TASK_LAUNCH_PREFIX.format(
        num_tasks = num_tasks
    ))

    for t in data['tasks']:
        if scheduler in APA_SCHEDULERS:
            core_list = ",".join([core(x) for x in get_affinity(t)])
            affinity = SET_AFFINITY.format(core_list = core_list)
        else:
            affinity = ''
        if scheduler in FIXED_PRIORITY_SCHEDULERS:
            prio = '-q %s' % t['priority']
        else:
            prio =''
        if scheduler in RESERVATION_SCHEDULERS:
            reservation = '-R'
        else:
            reservation = ''
        if scheduler in PARTITIONED_SCHEDULERS:
            partition = '-p %s' % core(random.choice(get_affinity(t)))
        else:
            partition = ''

        wss = default_wss
        if 'wss' in t:
            wss = t['wss']
        if wss:
            wss = '-m %s' % wss
        else:
            wss = ''

        timer_opt = ''
        if want_nanosleep:
            timer_opt = '-T'

        f.write(RTSPIN.format(
            taskset       = affinity,
            prio          = prio,
            cost          = us2ms(t['cost']),
            period        = us2ms(t['period']),
            duration      = duration,
            scale         = scale,
            reservation   = reservation,
            partition     = partition,
            wss           = wss,
            timer         = timer_opt,
            tid           = t['id'],
        ))

    f.write(TASK_LAUNCH_SUFFIX.format(
        num_tasks = num_tasks
    ))

    if want_overheads:
        f.write(OVERHEAD_TRACE.format(
            num_tasks = num_tasks,
            name = name,
            taskset = trace_affinity
        ))

    f.write(MAIN_EXP.format(
        num_tasks = len(data['tasks']),
        duration  = duration,
    ))
    f.write(SET_SCHEDULER.format(scheduler = 'Linux'))

    if process_overheads:
        f.write(PROCESS_OVERHEAD_TRACE.format(name = name))

    f.close()
    chmod(fname, stat.S_IRGRP | stat.S_IROTH | stat.S_IRWXU)


def load_ts_from_json(fname):
    data = json.load(open(fname, 'r'))
    return data

def parse_args():
    p = argparse.ArgumentParser(
        description='LITMUS^RT setup script generator')

    def pos_int(s):
        v = int(s)
        if v <= 0:
             raise argparse.ArgumentTypeError("must be positive")
        return v

    p.add_argument(
        'files', nargs='*', type=str, metavar='input-files',
        help='task set descriptions in JSON format')

    p.add_argument(
        '-S', '--trace-schedule', action='store_true', dest='want_sched_trace',
        default=False,
        help='Record the schedule with sched_trace')
    p.add_argument(
        '-O', '--trace-overheads', action='store_true', dest='want_overheads',
        default=False,
        help='Record runtime overheads with Feather-Trace')
    p.add_argument(
        '-P', '--process-overheads', action='store_true', dest='process_overheads',
        default=False,
        help='Extract overhead samples form Feather-Trace trace files')
    p.add_argument(
        '-D', '--trace-debug-log', action='store_true', dest='want_debug_trace',
        default=False,
        help='Record TRACE() messages [debug feature]')


    p.add_argument(
        '-t', '--duration', type=pos_int, dest='duration', default=10,
        help='how long should the experiment run?')
    p.add_argument(
        '-w', '--wss', type=pos_int, dest='wss', default=16,
        help='default working set size of RT tasks [in KiB]')
    p.add_argument(
        '-s', '--use-nanosleep', action='store_true', dest='use_nanosleep',
        default=False,
        help='make rtspin use clock_nanosleep()')
    p.add_argument(
        '-b', '--bg-memory', type=pos_int, dest='bg_wss', default=1024,
        help='working set size of background cache-thrashing tasks [in 4K pages]')
    p.add_argument(
        '-p', '--scheduler', type=str, dest='plugin', default='P-FP',
        help='Which scheduler plugin to use?')
    p.add_argument(
        '--dsp', type=pos_int, dest='service_core', default=None,
        help='Which core is the dedicated service processor? ' +
            'Relevant only for message-passing plugins.')

    p.add_argument(
        '--prefix', type=str, dest='prefix', default='./',
        help='Where to store the generated script[s]?')


    return p.parse_args()

def main(args=sys.argv[1:]):
    options = parse_args()

    prefix_dir = dirname(options.prefix)
    if prefix_dir and not exists(prefix_dir):
        makedirs(prefix_dir)

    for fname in options.files:
        name = basename(fname).replace('.json', '')
        print 'Processing %s -> %s' % (fname, options.prefix + name + '.sh')
        try:
            ts = load_ts_from_json(fname)
            generate_sh(name, ts,
                        scheduler=options.plugin,
                        duration=options.duration,
                        want_debug=options.want_debug_trace,
                        want_overheads=options.want_overheads,
                        process_overheads=options.process_overheads,
                        want_schedule=options.want_sched_trace,
                        background_wss=options.bg_wss,
                        default_wss=options.wss,
                        service_core=options.service_core,
                        want_nanosleep=options.use_nanosleep,
                        prefix=options.prefix)
        except IOError, err:
            print '%s: %s' % (fname, err)
        except ValueError, err:
            print '%s: %s' % (fname, err)

if __name__ == '__main__':
    main()
