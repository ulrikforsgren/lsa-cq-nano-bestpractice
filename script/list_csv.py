#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import csv
import json
from pprint import pprint
import sys

_ColorType__colors = {
'BLACK' :     '\033[30m',
'RED' :       '\033[31m',
'GREEN' :     '\033[32m',
'YELLOW' :    '\033[33m',
'BLUE' :      '\033[34m',
'PINK' :      '\033[35m',
'CYAN' :      '\033[36m',
'WHITE' :     '\033[37m',
'BBLACK' :    '\033[90m',
'BRED' :      '\033[91m',
'BGREEN' :    '\033[92m',
'BYELLOW' :   '\033[93m',
'BBLUE' :     '\033[94m',
'BPINK' :     '\033[95m',
'BCYAN' :     '\033[96m',
'BWHITE' :    '\033[97m',
'ENDC' :      '\033[0m',
'BOLD' :      '\033[1m',
'UNDERLINE' : '\033[4m',
}
class ColorType:
    def __getattr__(self, attr):
        if attr in __colors:
            return __colors[attr]

color = ColorType()


def parseArgs(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str,
                        help='logfile name')
    parser.add_argument('-f', type=str, action='append', default=[],
                        help='filter')
    return parser.parse_args(args)


def match(row, filters):
    for k, v in filters:
        if row[k] != v:
            return False
    return True


def main(args):
    filters = []
    for l in args.f:
        k, v = l.split('=')
        filters.append((k, v))
    with open(args.file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if not match(row, filters): continue
            print(color.GREEN + row['host'], end=' ')
            print(color.ENDC + row['api'], end=' ')
            t = row['type']
            if t  == 'response':
                c = color.RED
                u = ''
            elif t == 'stream':
                c = color.RED
                u = row['stream']
            else:
                c = ''
                u = row['url']
            print(f"{c}{row['type']}{color.ENDC} {row['method']} {color.YELLOW}{u}{color.ENDC}")
            try:
                pprint(json.loads(row['data']))
            except json.decoder.JSONDecodeError as e:
                print(row['data'])
if __name__ == '__main__':
    main(parseArgs(sys.argv[1:]))
