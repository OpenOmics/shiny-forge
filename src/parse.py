#!/usr/bin/env python3
import subprocess
import json
import ipdb
import os
from .config import REGION
from packaging.version import Version, InvalidVersion
from typing import Dict, List, Optional, Union

###
# functions for executing and parsing structured file
###

def read_artifacts(file):
    if not os.path.exists(file):
        raise FileNotFoundError('artifacts file missing')
    artifacts = {}
    with open(file) as of:
        for line in of:
            spt = line.strip().split('=')
            if len(spt) != 2:
                raise ValueError('bad artifacts file')
            k, v = spt[0], spt[1]
            artifacts[k] = v
    return artifacts
    
###
# functions for executing and parsing gcloud activities
###

def run_and_grab(proc: List, out: Union[List, bool]):
    args = {'stderr': subprocess.PIPE}
    if out:
        args['stdout'] = subprocess.PIPE
    result = subprocess.run(proc, **args)
    if getattr(result, 'stdout', None):
        return json.loads(result.stdout)
    else:
        return result.stdout


def read_all():
    proc = ["gcloud", "run", "services", "list", f"--region={REGION}"]
    outs = run_and_grab(proc, False)
    return


def check_job_exists(project_name):
    proc = ["gcloud", "run", "services", "list", f"--region={REGION}", "--format=\"json\""]
    job_json = run_and_grab(proc, True)
    job_names = [app['metadata']['name'] for app in job_json]
    return project_name in job_names


def read_one(project_name):
    if check_job_exists(project_name):
        proc = ["gcloud", "run", "services", "describe", f"--region={REGION}", project_name]
        outs = run_and_grab(proc, False)
    else:
        raise ValueError(f'Application "{project_name}" does not exist!')
    

def get_docker_tag(image):
    proc = ['gcloud', 'container', 'images', 'list-tags', '--format="json"', image]
    outs = run_and_grab(proc, True)
    tags = []

    if len(outs) > 0:
        for tag in outs[0]['tags']:
            try:
                _t = Version(tag)
                tags.append(_t)
            except InvalidVersion:
                continue

    if tags:
        latest_v = sorted(tags)[-1].base_version.split('.')
        latest_minor = int(latest_v[2]) + 1
        latest_tag = f"{latest_v[0]}.{latest_v[1]}.{latest_minor}"
    else:
        latest_tag = '0.0.1'

    

    return latest_tag