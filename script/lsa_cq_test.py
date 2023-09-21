#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
import os.path

import jsonrpc_api
import restconf_api


async def get_subscriptions(jsonrpc):
    await jsonrpc.login()
    handle = await jsonrpc.subscribe_changes('main', '/ncs:services/mid-link:mid-link')
    await jsonrpc.start_subscription(handle)
    handle = await jsonrpc.subscribe_cdboper('main', '/ncs:services/mid-link:mid-link-data')
    await jsonrpc.start_subscription(handle)

    while True:
        await jsonrpc.comet('main')


async def get_notifications(restconf):
    await asyncio.wait([
        restconf.get_stream('ncs-alarms'),
        restconf.get_stream('ncs-events'),
        restconf.get_stream('device-notifications'),
        restconf.get_stream('service-state-changes'),
        ])


async def logger(q, console=True, filename=None):
    f = None
    if filename is not None:
        f = open(filename, 'w')
    while True:
        msg = await q.get()
        if console:
            print(msg)
        if f:
            f.write(f'{msg}\n')
        q.task_done()


async def main():
    name = os.path.basename(__file__).split('.')[0]

    q = asyncio.Queue()
    async def log(msg):
        await q.put(msg)

    try:
        #
        # Setup
        #
        client = restconf_api.get_client()

        jsonrpc = jsonrpc_api.JSONRPC('localhost:8080', 'admin', 'admin',
                                      client=client, log=log)
        restconf = restconf_api.RESTCONF('localhost:8080', 'admin', 'admin',
                                         client=client, log=log)

        comet_task = asyncio.create_task(get_subscriptions(jsonrpc),
                                         name='comet_task')
        notif_task = asyncio.create_task(get_notifications(restconf))
        logger_task = asyncio.create_task(logger(q, filename=f'{name}.log'),
                                          name='logger_task')


        #
        # Do your stuff here
        #

        await restconf.request('read', '/tailf-ncs:devices/global-settings')

        await asyncio.sleep(10)

        #
        # Tear down
        #

        comet_task.cancel()
        notif_task.cancel()
    finally:
        await jsonrpc.logout()
        await q.join()
        logger_task.cancel()
        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
