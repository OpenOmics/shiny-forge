#!/usr/bin/env python3
import subprocess
import os
import datetime
import uuid
import shutil
import yaml
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import List, Dict
from google.cloud import storage
from .config import PROJECT, bcolors, ENV, BASE_CLOUD_BUILD_STRUCTURE, BASE_CLOUD_BUILD_STEP
from .parse import read_artifacts, save_yaml


###
###  > Objective: encapsulate all google cloud build logic here
###
large_code_clean = lambda codes: dedent(codes.strip())


def build_setup():
    ## For slow upload speed
    storage.blob._DEFAULT_CHUNKSIZE = 5242880 # 1024 * 1024 B * 2 = 5 MB
    storage.blob._MAX_MULTIPART_SIZE = 5242880 
    subprocess.run(['gcloud', 'config', 'set', 'billing/quota_project', PROJECT.lower()], env=ENV, check=True)
    subprocess.run(['gcloud', 'config', 'set', 'storage/parallel_composite_upload_enabled', 'True'], check=True)
    return


def create_gcs_bucket(project_id: str, bucket_name: str) -> None:
    """
    Create a new GCS bucket.
    
    Args:
        project_id: Google Cloud Project ID
        bucket_name: Name for the new bucket
    """
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.create_bucket(bucket_name)
    return bucket


def delete_gcs_bucket(project_id: str, bucket_name: str) -> None:
    """
    Delete a GCS bucket and all its contents.
    
    Args:
        project_id: Google Cloud Project ID
        bucket_name: Name of the bucket to delete
    """
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.get_bucket(bucket_name)
    blobs = list(bucket.list_blobs())
    for blob in blobs: blob.delete()
    bucket.delete()
    return


def upload_to_gcs(
        bucket_name: str, 
        files: List[str]
    ) -> Dict:
    """
        Upload one or many docker artifact files 
        to google cloud storage bucket.
        Input:
            bucket_name [str] = name of the bucket to transfer to
            files List[str] = list of file paths to upload to google bucket
        Output:
            files2url Dict[str > str] = map of file paths to google bucket paths
    """
    files2url = {}
    for file_path in files:
        file_name = os.path.basename(file_path)
        destination_gcp = f"gs://{bucket_name}/{file_name}"
        subprocess.run(['gcloud', 'storage', 'cp', os.path.abspath(file_path), destination_gcp], env=ENV, check=True)
        files2url[file_path] = destination_gcp
    return files2url


def mk_gsutil_download_args(
        uploads: Dict
    ):
    steps = []
    waitfor = []
    for local_file, bucket_file in uploads.items():
        local_file_name = os.path.basename(local_file)
        _step = BASE_CLOUD_BUILD_STEP.copy()
        _step['name'] = 'gcr.io/cloud-builders/gsutil'
        _step['id'] = f'download-{local_file_name}'
        _step['args'] = ['cp', bucket_file, './' + local_file_name]
        waitfor.append(f'download-{local_file_name}')
        steps.append(_step)

    return steps, waitfor


def mk_build_args(args):
    finish_args = []
    for arg_key, arg_val in args.items():
        start = ['--build-arg']
        if os.path.exists(arg_val):
            start.append(f'{arg_key}={os.path.basename(arg_val)}')
        else:
            start.append(f'{arg_key}={arg_val}')
        finish_args.extend(start)
    return finish_args


def silo_docker(dockerfile, barg_files):
    docker_file_dir = os.path.dirname(os.path.abspath(dockerfile))
    temp_dir = TemporaryDirectory()
    for _file in os.listdir(os.path.abspath(docker_file_dir)):
        if _file not in barg_files:
            shutil.copy(os.path.abspath(os.path.join(docker_file_dir, _file)), temp_dir.name)
    return temp_dir


def cloud_build(
        project_name: str,
        app_name: str,
        docker: str,
        artifacts: str
    ):
    # initialize could build
    build_setup()

    # 1. Creates a temporary GCS bucket based on project ID hash
    formatted_date = datetime.date.today().strftime("%Y-%m-%d")
    bucket_hash = f"{formatted_date}_{str(uuid.uuid4())}"
    bucket = create_gcs_bucket(project_id=project_name, bucket_name=bucket_hash)

    # 2. Uploads large file artifacts to the temporary bucket
    bargs = read_artifacts(artifacts)
    files_to_upload_to_gcs = [_value for _, _value in bargs.items() if os.path.exists(os.path.abspath(_value))]
    uploaded = upload_to_gcs(bucket_hash, files_to_upload_to_gcs)

    # 3. Copy docker file and small docker artifacts (!= large docker artifacts) to temporary location
    docker_dir = silo_docker(docker, files_to_upload_to_gcs)

    # 4. Create a Cloud Build configuration
    # > 4a. Steps to download all the pre-requisite bucket files
    cloudbuild_download_steps, build_waitfor = mk_gsutil_download_args(uploaded)

    # > 4b. Steps to build actual docker container
    docker_build_step_id = f'build-docker-{app_name}'
    cloudbuild_build_docker_step = {
        'name': 'gcr.io/cloud-builders/docker', 
        'args': ['build', '-t', f'gcr.io/$PROJECT_ID/{app_name}:0.0.1', '-t', f'gcr.io/$PROJECT_ID/{app_name}:latest', 
                    *mk_build_args(bargs), "."],
        'id': docker_build_step_id,
        'waitFor': build_waitfor,
    }

    # > 4b. Push container to registry
    cloudbuild_docker_push_001 = {
        'name': 'gcr.io/cloud-builders/docker', 
        'args': ['push', f'gcr.io/$PROJECT_ID/{app_name}:0.0.1'],
        'id': 'push-001',
        'waitFor': [docker_build_step_id]
    }

    cloudbuild_docker_push_latest = {
        'name': 'gcr.io/cloud-builders/docker', 
        'args': ['push', f'gcr.io/$PROJECT_ID/{app_name}:latest'],
        'id': 'push-latest',
        'waitFor': [docker_build_step_id]
    }

    # > 4c. Deploy to Google Cloud Run and start
    cloudbuild_cloudrun_deploy = {
        'name': 'gcr.io/google.com/cloudsdktool/cloud-sdk',
        'id': 'deploy-cloud-run',
        'entrypoint': 'gcloud',
        'args': [
            'run', 'deploy', app_name, 
            '--allow-unauthenticated', # allow for unauthenticated access online
            '--image', f'gcr.io/$PROJECT_ID/{app_name}:latest', 
            '--region', 'us-east4'
        ],
        'waitFor': ['push-latest']
    }

    full_build_yaml = BASE_CLOUD_BUILD_STRUCTURE.copy()
    full_build_yaml['steps'] = [*cloudbuild_download_steps, cloudbuild_build_docker_step, 
                                cloudbuild_docker_push_001, cloudbuild_docker_push_latest, 
                                cloudbuild_cloudrun_deploy]
    full_build_yaml['images'] = [f'gcr.io/$PROJECT_ID/{app_name}:latest', f'gcr.io/$PROJECT_ID/{app_name}:0.0.1']
    dockerbuild_yaml = os.path.join(docker_dir.name, 'cloudbuild.yaml')

    save_yaml(full_build_yaml, dockerbuild_yaml)
    save_yaml(full_build_yaml, "/Users/routsongrm/git/OpenOmics/shiny-forge/test.yaml")

    # 6. Execute cloud build + run
    subprocess.run([
        'gcloud', 'builds', 'submit', 
        '--region=us-east4',
        '--config', dockerbuild_yaml,
        '--polling-interval=200',
        '--timeout=1h'
    ], cwd=docker_dir.name, env=ENV, check=True)
    
    # 7. Clean up temporary artifacts and destroys the temporary bucket after build
    docker_dir.cleanup()
    delete_gcs_bucket(project_id=project_name, bucket_name=bucket_hash)

    return
    
