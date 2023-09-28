#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import asyncio
import csv
from datetime import datetime
import os.path
import sys

import jsonrpc_api
import restconf_api

import aioconsole

def parseArgs(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', type=str,
                        help='logfile name')
    parser.add_argument('-f', action='store_true', default=False,
                        help='Log to file using scriptname as base for'+
                             'log file name (unless -o is used).')
    return parser.parse_args(args)


async def setup_subscriptions(jsonrpc, subscriptions):
    for t,p in subscriptions:
        if t == 'config':
            handle = await jsonrpc.subscribe_changes('main', p)
            await jsonrpc.start_subscription(handle)
        elif t == 'oper':
            handle = await jsonrpc.subscribe_cdboper('main', p)
            await jsonrpc.start_subscription(handle)


async def get_subscriptions(jsonrpc):
    await jsonrpc.login()
    await setup_subscriptions(jsonrpc, [
        ('config', '/ncs:services'),
        ('oper', '/ncs:services'),
        ('oper', '/ncs:devices/commit-queue/qitem'),
        ('oper', '/ncs:devices/commit-queue/completed/queue-item')
        ])
    while True:
        await jsonrpc.comet('main')
    # TODO: Catch task cancel exception and logout?!


async def get_notifications(restconf):
    await asyncio.wait([
        restconf.get_stream('ncs-alarms'),
        restconf.get_stream('ncs-events'),
        restconf.get_stream('device-notifications'),
        restconf.get_stream('service-state-changes'),
        ])


def get_logger(q):
    async def log(host, api, msg_type, **kwargs):
        msg = {
            'timestamp': datetime.isoformat(datetime.now()),
            'host': host,
            'api': api,
            'type': msg_type
            }
        msg.update(kwargs)
        await q.put(msg)
    return log


async def logger(q, log_console=True, log_file=False, log_format='csv',
                 log_filename="output.csv"):
    f = None
    if log_file:
        # Move to constructor
        f = open(log_filename, 'w')
        if log_format == 'raw':
            writer = lambda d,h,t,msg: f.write(f'{d, h, t, msg}\n')
        elif log_format == 'csv':
            fieldnames = [
                    'timestamp',
                    'host',
                    'api',
                    'type',
                    'rid',
                    'url',
                    'stream',
                    'status',
                    'method',
                    'data',
                    ]
            dw = csv.DictWriter(f, fieldnames=fieldnames)
            writer = dw.writerow
            dw.writeheader()
    while True:
        msg = await q.get()
        if log_console:
            await aioconsole.aprint(msg)
        if log_file and f:
            writer(msg)
        q.task_done()


async def subscribe_for_notifications(client, q,
             user='admin', password='admin',
             nodes=['localhost:8080', 'localhost:8081', 'localhost:8082'],
             log_console=True, log_file=True, log_format='csv',
             log_filename='output.csv'):

    log = get_logger(q)
    connections = []
    for n in nodes:
        jsonrpc = jsonrpc_api.JSONRPC(n, user, password,
                                      client=client, log=log)
        restconf = restconf_api.RESTCONF(n, user, password,
                                      client=client, log=log)
        connections += [(jsonrpc, restconf)]

    if log_file:
        if log_filename is None:
            log_filename = os.path.basename(sys.argv[0]).split('.')[0]
            if log_format == 'csv':
                log_filename += '.csv'
            else:
                log_filename += '.log'
        else:
            log_filename = log_filename

    tasks = []
    for jsonrpc, restconf in connections:
        tasks.append(asyncio.create_task(get_subscriptions(jsonrpc),
                                                    name='comet_task'))
        tasks.append(asyncio.create_task(get_notifications(restconf),
                                                    name='notif_task'))
    tasks.append(asyncio.create_task(logger(q, log_console=log_console,
                                            log_file=log_file,
                                            log_filename=log_filename),
                                            name='logger_task'))

    await asyncio.wait(tasks)


async def main(args):
    if args.o is not None:
        log_filename = args.o
    else:
        log_filename = os.path.basename(sys.argv[0]).split('.')[0]+'.csv'
    client = restconf_api.get_client()
    q = asyncio.Queue()
    await subscribe_for_notifications(client, q, nodes=
                      ['localhost:8080', 'localhost:8081', 'localhost:8082'],
                      log_file=args.f,
                      log_filename=log_filename)

    #TODO: Proper cleanup
    # Catch KeyboardException, logout, ...
    await client.close()

if __name__ == '__main__':
    asyncio.run(main(parseArgs(sys.argv[1:])))
