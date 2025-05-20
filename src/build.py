#!/usr/bin/env python3
import subprocess
import os
import datetime
import uuid
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import List, Dict
from google.cloud import storage
from .config import PROJECT, bcolors, ENV
from .parse import read_artifacts


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
    for local_file, bucket_file in uploads:
        local_file_name = os.path.basename(local_file)
        steps.append({
            'name': 'gcr.io/google-containers/gcloud-cli',
            'entrypoint': 'gcloud',
            'args': ['storage', 'cp', bucket_file, './' + local_file_name]
        })

    return steps


def mk_build_args(args):
    finish_args = []
    for arg_key, arg_val in args.items():
        start = ['--build-args']
        if os.path.exists(arg_val):
            start.append(f'{arg_key}={os.path.basename(arg_val)}')
        else:
            start.append(f'{arg_key}={arg_val}')
        finish_args.extend(start)
    return finish_args


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
    uploaded = upload_to_gcs(bucket_hash, [_value for _, _value in bargs.items() if os.path.exists(os.path.abspath(_value))])

    # 3. Creates a Cloud Build configuration
    cloudbuild_download = mk_gsutil_download_args(uploaded)
    cloudbuild_docker = {
        'name': 'gcr.io/cloud-builders/docker', 
        'args': ['build', '-t', f'gcr.io/$PROJECT_ID/{app_name}', mk_build_args(bargs)]
    }
    
    # 4. Triggers a build on Google Cloud Build
    
    # 5. Cleans up artifacts and destroys the temporary bucket after build

    return
    
