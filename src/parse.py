#!/usr/bin/env python3
import subprocess
import json
import os
import yaml
import argparse
import git
import hashlib
from dockerfile_parse import DockerfileParser
from typing import List, Union
from .config import REGION, ENV


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
    env['PYTHONWARNINGS'] = "ignore"
    args['env'] = env
    if out:
        args['stdout'] = subprocess.PIPE
    
    result = subprocess.run(proc, **args)
    if getattr(result, 'stdout', None):
        try:
            return json.loads(result.stdout)
        except:
            return result.stdout
    else:
        return result.stdout

def read_all():
    meta_data = [   
        'name', 'labels.seurat_rds', 
        "labels.commit_sha,metadata.annotations.'serving.knative.dev/creator':label='DEPLOYED_BY'",
        "metadata.creationTimestamp.date('%m-%d-%Y'):label='DEPLOYED_ON'"
    ]
    proc = f"gcloud run services list --region={REGION} " + \
           f"--format=\"table({','.join(meta_data)})\""
    subprocess.run(proc, env=ENV, shell=True)
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


def app_name_valid(name):
    if len(name) > 63:
        raise argparse.ArgumentTypeError('App name must be shorter than 63 characters! (GCP requirement)')
    name_no_dash = name.replace('-', '')
    if not name_no_dash.isalnum():
        raise argparse.ArgumentTypeError('App name must only contain lowercase alphanumeric characters and/or dashes! (GCP requirement)')
    if not name.islower():
        raise argparse.ArgumentTypeError('App name must only contain lowercase characters! (GCP requirement)')
    return name

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
    dockerfile = DockerfileParser(fileobj=open(file), cache_content=True)
    build_args = [line['value'] for line in dockerfile.structure if line['instruction'] in ('BUILD-ARG', 'ARG')]
    return build_args


###
###  >> Section: functions for executing and parsing yaml artifacts
### 

def save_yaml(content, filepath):
    # Custom representer to handle None values and formatting
    def represent_none(self, data):
        return self.represent_scalar('tag:yaml.org,2002:null', '')
        
    yaml.add_representer(type(None), represent_none)
    
    # Generate YAML with proper formatting
    return yaml.dump(
        content,
        open(filepath, 'w'),
        default_flow_style=False,
        indent=2,
        sort_keys=False,
        allow_unicode=True,
        explicit_start=True
    )


### 
###
###
def get_sha1_hash(file_path):
    """Calculate SHA1 hash of a file."""
    sha1_hash = hashlib.sha1()
    with open(file_path, 'rb') as file:
        # Read the file in chunks to handle large files efficiently
        for chunk in iter(lambda: file.read(4096), b""):
            sha1_hash.update(chunk)
    return sha1_hash.hexdigest()


def get_hash_labels(artifacts_file):
    # get git hash
    repo = git.Repo(search_parent_directories=True)
    sha = repo.head.object.hexsha
    # get artifacts hash
    artifacts = {k: v for k, v in read_artifacts(artifacts_file).items() if os.path.exists(os.path.abspath(v))}
    artifact_hashes = {k: get_sha1_hash(v) for k, v in artifacts.items()}
    labels = f"COMMIT_SHA={sha}".lower()
    for artifact_name, hash in artifact_hashes.items():
        # should always start with COMMIT_SHA
        if len(artifact_name) > 63:
            raise ValueError(f"GCP cloud run label ({artifact_name}) cannot be longer than 63 characters")
        labels += f",{artifact_name}={hash}".lower()
    return labels