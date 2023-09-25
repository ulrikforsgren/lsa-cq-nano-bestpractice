# -*- mode: python; python-indent: 4 -*-

import asyncio
from base64 import b64encode
import json
import aioconsole
import aiohttp
from yarl import URL
import sys


HEADERS_JSON={
    'Accept':'application/yang-data+json',
    'Accept-Encoding': 'identity', # Prevent NSO from gzipping the data
    'Content-type': 'application/yang-data+json'
}

HEADERS_STREAM={
    'Accept':'text/event-stream',
    'Accept-Encoding': 'identity', # Prevent NSO from gzipping data and delaying
                                   # sending of events.
}

def add_authentication(h, user, password):
    credentials = f'{user}:{password}'.encode('ascii')
    h['Authorization'] = 'Basic %s' % b64encode(credentials).decode("ascii")


# Expected response status for successful requests.
REQ_DISPATCH = {
    'create': ('POST', [201]),
    'read':   ('GET', [200]),
    'update': ('PATCH', [200, 204]),
    'set': ('PUT', [204]),
    'delete': ('DELETE', [200, 204]),
    'action': ('POST', [200, 204])
}


def get_client():
    conn = aiohttp.TCPConnector(limit=0) # No limit of parallel connections
    client = aiohttp.ClientSession(connector=conn)
    return client


class RESTCONF:
    def __init__(self, host, user, password, client=None, log=None):
        if client is not None:
            self.client = client
        else:
            self.client = get_client()
        self.host = host
        self.user = user
        self.password = password
        self.headers = HEADERS_JSON.copy()
        add_authentication(self.headers, self.user, self.password)
        self.idval = 0
        self.idlock = asyncio.Lock()
        if log is not None:
            self.log = log
        else:
            self.log = lambda *msg: None


    async def next_id(self):
        async with self.idlock:
            self.idval += 1
            return self.idval


    # TODO: Handle token to speed up logins
    # Returns tuples:
    # Successful: (request-id, "ok"/"nok", http-status, data/json)
    # Exception:  (request-id, "exception", exception-object)
    #
    async def request(self, op, resource, data=None, jdata=None,
                      resource_type='data', params=None):
        method, expected_status = REQ_DISPATCH[op]
        url = f'http://{self.host}/restconf/{resource_type}{resource}'
        if params is not None:
            # aiohttp request uses yarl.URL is used for params and can not handle
            # params without equal sign (=). Putting them directly in the url instead.
            url += '?' + params
        try:
            rid = await self.next_id()
            if data is not None:
                await self.log(self.host, 'restconf', 'request', rid=rid,
                               method=method, url=url, data=data)
                data=data.encode('utf-8')
            elif jdata is not None:
                await self.log(self.host, 'restconf', 'request', rid=rid,
                                method=method, url=url, data=jdata)
            else:
                await self.log(self.host, 'restconf', 'request', rid=rid,
                                method=method, url=url)
            async with self.client.request(method, url, headers=self.headers,
                                      data=data, json=jdata) as response:
                if response.status in [ 201, 204 ]:
                    data = None # No content is expected.
                else:
                    if response.headers['Content-Type'] == 'application/yang-data+json':
                        data = await response.json()
                    else:
                        data = await response.text()
                await self.log(self.host, 'restconf', 'response',
                               status=response.status, rid=rid,
                               url=url, data=data)
                res = 'ok' if response.status in expected_status else 'nok'
                return (rid, res, response.status, data)
        except Exception as e:
            return (rid, 'exception', repr(e))


    async def get_stream(self, stream):
        url = f'http://{self.host}/restconf/streams/{stream}/json'
        headers = HEADERS_STREAM.copy()
        add_authentication(headers, self.user, self.password)
        rid = await self.next_id()
        await self.log(self.host, 'restconf', 'stream', rid=rid, stream=stream, 
                       method='GET', url=url)
        async with self.client.get(url, headers=headers) as response:
            assert response.status == 200
            # TODO: Improve performance by using something better than a string?
            # TODO: Handle errors
            s = ""
            try:
                async for line in response.content:
                    l = line.decode('utf-8').strip()
                    if l == "": # Assuming an emply lines is end of message
                        o = json.loads(s)
                        s = ""
                        await self.log(self.host, 'restconf', 'stream', rid=rid,
                                        stream=stream, data=o)
                    elif l[:6] == 'data: ':
                        s += l[6:]
                    elif l[:9] == ': error :':
                        await self.log(self.host, 'restconf', 'stream', rid=rid,
                                        stream=stream, data=l)
                    else:
                        await aioconsole.aprint("UNHANDLED", self.host,
                                                response.status, l)
            except Exception as s:
                await aioconsole.aprint(
                        f"EXCEPTION: {s}\n"+
                        f"s= {s}\n"+
                        f"l= {l}"
                        )
                sys.exit(1)
