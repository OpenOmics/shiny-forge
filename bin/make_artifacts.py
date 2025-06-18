#!/usr/bin/env python3
"""
"""
import argparse
import os
from textwrap import dedent
from pprint import pprint as pp
from dockerfile_parse import DockerfileParser

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def valid_dockerfile(file):
    file = os.path.abspath(file)
    if not os.path.exists(file):
        raise argparse.ArgumentError('dockerfile does not exist!')
    return file


def read_dockerfile(file):
    file = os.path.abspath(file)
    if not os.path.exists(file):
        raise FileNotFoundError('docker file missing')
    dockerfile = DockerfileParser(fileobj=open(file), cache_content=True)
    build_args = [line['value'] for line in dockerfile.structure if line['instruction'] in ('BUILD-ARG', 'ARG')]
    optional_args, reqd_args = [], []
    for arg in build_args:
        if '=' in arg:
            optional_args.append(arg.split('=')[0])
        else:
            reqd_args.append(arg)
    return optional_args, reqd_args


def main():
    parser = argparse.ArgumentParser(
        description="Template CLI application with optional file output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent("""
               Examples:
               %(prog)s Dockerfile                    # Process Dockerfile, print to stdout
               %(prog)s Dockerfile -o output.txt      # Process Dockerfile, write to file
               %(prog)s /path/to/Dockerfile --output results.log  # Process with file output
               """)
    )
    parser.add_argument(
        'dockerfile',
        type=valid_dockerfile,
        help='Path to the Dockerfile to process'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        metavar='FILE',
        help='Output file path (default: print to stdout)'
    )
    args = parser.parse_args()
    if args.output:
        if not os.access(args.output, os.W_OK):
            raise PermissionError(f"Write access is denied for: {args.output}")

    optional, reqd = read_dockerfile(args.dockerfile)

    if not reqd:
        raise ValueError(f'No {bcolors.UNDERLINE}{bcolors.FAIL}BUILD ARGs{bcolors.ENDC} in this dockerfile: {bcolors.FAIL}({args.dockerfile}){bcolors.ENDC}!')
    
    to_out = []
    for arg in reqd:
        to_out.append(f'{arg}=   # required')
    for arg in optional:
        to_out.append(f'{arg}=   # optional')

    # Handle output destination
    if args.output:
        with open(args.out, 'w') as fo:
            for line in to_out:
                fo.write(line + '\n')
    else:
        for line in to_out:
            print(line)
        

if __name__ == "__main__":
    main()