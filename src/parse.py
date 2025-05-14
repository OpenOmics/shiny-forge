#!/usr/bin/env python3
import subprocess
import json
import ipdb
import os
from .config import REGION
from dockerfile_parse import DockerfileParser
from typing import Dict, List, Optional, Union

###
###  > Objective: encapsulate all parsing related helpers and utilities
###


###
###  >> Section: functions for executing and parsing structured file formats
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
###  >> Section: functions for executing and parsing GCP artifacts
###

def run_and_grab(proc: List, out: Union[List, bool]):
    args = {'stderr': subprocess.PIPE}
    env = os.environ.copy()
    env['PYTHONWARNINGS'] = "ignore:Unverified HTTPS request"
    args['env'] = env
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


def list_apps():
    get_apps = run_and_grab(
                ["gcloud", 
                 "run", 
                 "services", 
                 "list", 
                 f"--region={REGION}", 
                 "--format=\"json\""],
                 True
               )
    return [app['metadata']['name'] for app in get_apps]


def get_container_for_service(service_name):
    proc = ["gcloud", "run", "services", "describe", f"--region={REGION}", "--format=\"json\"", service_name]
    outs = run_and_grab(proc, True)
    return outs['spec']['template']['spec']['containers'][0]['image']


###
###  >> Section: functions for executing and parsing docker artifacts
### 

def read_dockerfile(file):
    file = os.path.abspath(file)
    if not os.path.exists(file):
        raise FileNotFoundError('docker file missing')
    dockerfile = DockerfileParser()
    dockerfile.content = open(file).read()
    build_args = [line['value'] for line in dockerfile.structure if line['instruction'] in ('BUILD-ARG', 'ARG')]
    return build_args


# def get_docker_tag(image):
#     proc = ['gcloud', 'container', 'images', 'list-tags', '--format="json"', image]
#     outs = run_and_grab(proc, True)
#     tags = []
#     if len(outs) > 0:
#         for tag in outs[0]['tags']:
#             try:
#                 _t = Version(tag)
#                 tags.append(_t)
#             except InvalidVersion:
#                 continue
#     if tags:
#         latest_v = sorted(tags)[-1].base_version.split('.')
#         latest_minor = int(latest_v[2]) + 1
#         latest_tag = f"{latest_v[0]}.{latest_v[1]}.{latest_minor}"
#     else:
#         latest_tag = '0.0.1'
#     return latest_tag