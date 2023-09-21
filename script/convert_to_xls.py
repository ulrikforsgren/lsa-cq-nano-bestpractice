#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
from pathlib import Path
import sys

import pandas as pd


def parseArgs(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('file', nargs='+', type=str,
                        help='csv file to convert into a Excel document.')
    return parser.parse_args(args)

def main(args):
    for f in args.file:
        read_file = pd.read_csv(f)
        read_file.to_excel (Path(f).with_suffix('.xls'), index = None, header=True)


if __name__ == '__main__':
    main(parseArgs(sys.argv[1:]))

