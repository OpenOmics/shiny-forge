#!/usr/bin/env python3
import subprocess
import json
import ipdb
from typing import Dict, List, Optional, Union

###
# utilities file for parsing json formatted outputs by gcloud
###

REGION = "us-east4"

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