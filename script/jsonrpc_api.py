#!/usr/bin/env python3

import asyncio
from base64 import b64encode
import json
import os
import sys
import time

import aioconsole
import aiohttp


HEADERS_STREAM={
    'Content-Type':'application/json',
    'Accept-Encoding': 'identity', # Prevent NSO from gzipping data and delaying
                                   # sending of events.
}

def add_authentication(h, user, password):
    credentials = f'{user}:{password}'.encode('ascii')
    h['Authorization'] = 'Basic %s' % b64encode(credentials).decode("ascii")


def get_client():
    conn = aiohttp.TCPConnector(limit=0) # No limit of parallel connections
    client = aiohttp.ClientSession(connector=conn)
    return client


def dummy_logger(*a, **kwa):
    pass


class JSONRPC:
    def __init__(self, host, user='admin', password='admin', client=None,
                 log=None):
        if client is not None:
            self.client = client
        else:
            self.client = get_client()
        self.host = host
        self.baseurl = f"http://{host}/jsonrpc"
        self.user = user
        self.password = password
        self.headers = HEADERS_STREAM.copy()
        add_authentication(self.headers, self.user, self.password)
        self.idval = 0
        self.idlock = asyncio.Lock()
        self.cookies = None
        if log is not None:
            self.log = log
        else:
            self.log = dummy_logger

    async def next_id(self):
        async with self.idlock:
            self.idval += 1
            return self.idval

    async def post(self, payload, logging=True):
        payload.update({"jsonrpc" : "2.0", "id" : await self.next_id()})
        if logging:
            await self.log(self.host, 'jsonrpc', 'request', data=payload)
        try: # Fix no silent capture of exceptions
            if logging and payload['method'] != 'comet':
                await self.log(self.host, 'jsonrpc', 'request-cookies', data=self.client.cookies)
        except:
            pass
        async with self.client.post(self.baseurl, headers=self.headers, json=payload) as response:
            assert response.status == 200
            # Handle Set-Cookie
            status = response.status
            jresp = await response.json()
            if logging:
                if payload['method'] != 'comet' or ('result' in jresp and
                                                    len(jresp['result'])):
                    await self.log(self.host, 'jsonrpc', 'response', status=status,
                               data=jresp)
            return status, jresp

    async def login(self):
        payload = {
            "method" : "login",
            "params" : {
              "user" : self.user,
              "passwd" : self.password
            },
        }
        # TODO: Save sessionid cookie?
        resp = await self.post(payload)
        return resp

    async def logout(self):
        payload = {
            "method" : "logout"
        }
        resp = await self.post(payload)
        return resp


    async def get_trans(self):
        payload = {
            "method" : "get_trans"
        }
        resp = await self.post(payload)
        return resp

    async def new_trans(self, mode='read'):
        payload = {
            "method" : "new_trans",
            "params" : {
              "mode" : mode
            },
        }
        resp = await self.post(payload)
        return resp[1]['result']['th']

    async def get_value(self, th, path):
        payload = {
            "method" : "get_value",
            "params" : {
              "th" : th,
              "path" : path,
            },
        }
        resp = await self.post(payload)
        return resp[1]['result']['value']

    async def close(self):
        await self.client.close()

    async def comet(self, comet_id) :
        payload = {
            "method" : "comet",
            "params" : {
                         "comet_id": comet_id
                        },
        }
        resp = await self.post(payload)
        return resp
        # TODO: Handle streaming data


    async def batch_init_done(self, handle) :
        payload = {
            "method" : "batch_init_done",
            "params" : {
                "handle": handle
            },
        }
        resp = await self.post(payload)
        return resp

    async def subscribe_changes(self, comet_id, path, handle=None, hide_changes=False, hide_values=False):
        payload = {
            "method" : "subscribe_changes",
            "params" : {
                "comet_id": comet_id,
                "path": path,
                "hide_changes": hide_changes,
                "hide_values": hide_values
            }
        }
        if handle is not None:
            payload['params'].update({"handle": handle})
        resp = await self.post(payload)
        return resp[1]['result']['handle']

    async def subscribe_cdboper(self, comet_id, path, handle=None):
        payload = {
            "method" : "subscribe_cdboper",
            "params" : {
                "comet_id": comet_id,
                "path": path
            }
        }
        if handle is not None:
            payload['params'].update({"handle": handle})
        resp = await self.post(payload)
        return resp[1]['result']['handle']


    async def start_subscription(self, handle):
        payload = {
            "method" : "start_subscription",
            "params" : {
                "handle": handle
            }
        }
        resp = await self.post(payload)
        return resp

async def comet_channel(session, comet_id):
    while True:
        await session.comet(comet_id)


async def main():
    session = JSONRPC('localhost:8080')
    await session.login()
    try:
        await session.get_trans()
        th = await session.new_trans()
        value = await session.get_value(th, '/devices/global-settings/read-timeout')
        await aioconsole.aprint("value", value)
        handle = await session.subscribe_changes('main', '/ncs:services/mid-link:mid-link')
        await aioconsole.aprint("handle", handle)
        await session.start_subscription(handle)
        handle = await session.subscribe_cdboper('main', '/ncs:services/mid-link:mid-link-data')
        await aioconsole.aprint("handle", handle)
        await session.start_subscription(handle)
        await comet_channel(session, 'main')
    finally:
        await session.logout()
        await session.close()

if __name__ == '__main__':
    asyncio.run(main())
