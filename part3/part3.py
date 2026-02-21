#!/usr/bin/env python3

import argparse
import os
import time
from pprint import pprint

import googleapiclient.discovery
from google.auth import compute_engine
from google.oauth2 import service_account
from googleapiclient.discovery import build
import google.auth

#
# Use Google Service Account - See https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.service_account.html#module-google.oauth2.service_account
#
credentials = service_account.Credentials.from_service_account_file(filename='service-credentials.json')
project = 'serious-truck-450805-d9'
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

PROJECT_ID = 'serious-truck-450805-d9'   
ZONE = 'us-west1-b'      
VM1_NAME = 'vm1-launcher'
MACHINE_TYPE = 'n1-standard-1'
IMAGE_PROJECT = "ubuntu-os-cloud"
IMAGE_FAMILY = "ubuntu-2204-lts"
SERVICE_ACCOUNT_FILE = 'service-credentials.json' 

VM2_STARTUP_SCRIPT_FILE = './../part1/part1.py'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE
)
compute = build('compute', 'v1', credentials=credentials)

with open(VM2_STARTUP_SCRIPT_FILE, 'r') as f:
    vm2_startup_script = f.read()

startup_script_vm1 = f"""#!/bin/bash
# Create directory for scripts
mkdir -p /srv
cd /srv

# Download VM-2 startup script from metadata (already passed)
echo "{vm2_startup_script}" > vm2-startup-script.sh
chmod +x vm2-startup-script.sh

# Copy service credentials from metadata (if using explicit credentials)
# curl http://metadata/computeMetadata/v1/instance/attributes/service-credentials -H "Metadata-Flavor: Google" > service-credentials.json

# Download VM-1 Python launch script from metadata
curl http://metadata/computeMetadata/v1/instance/attributes/vm1-launch-vm2-code -H "Metadata-Flavor: Google" > vm1-launch-vm2-code.py
chmod +x vm1-launch-vm2-code.py

# Set project environment variable
export GOOGLE_CLOUD_PROJECT=$(curl http://metadata/computeMetadata/v1/instance/attributes/project -H "Metadata-Flavor: Google")

# Install Python dependencies
apt-get update && apt-get install -y python3-pip
pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

# Launch VM-2
python3 ./vm1-launch-vm2-code.py
"""

metadata = {
    'items': [
        {'key': 'startup-script', 'value': startup_script_vm1},
        {'key': 'project', 'value': PROJECT_ID},
        {'key': 'vm1-launch-vm2-code', 'value': vm2_startup_script},
        {'key': 'service-credentials', 'value': open(SERVICE_ACCOUNT_FILE).read()}
    ]
}

machine_type_url = f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}"

image_response = compute.images().getFromFamily(
    project=IMAGE_PROJECT, family=IMAGE_FAMILY
).execute()
source_disk_image = image_response['selfLink']

config = {
    'name': VM1_NAME,
    'machineType': machine_type_url,
    'disks': [
        {
            'boot': True,
            'autoDelete': True,
            'initializeParams': {
                'sourceImage': source_disk_image,
            }
        }
    ],
    'networkInterfaces': [
        {
            'network': 'global/networks/default',
            'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}]
        }
    ],
    'serviceAccounts': [
        {
            'email': 'default', 
            'scopes': [
                'https://www.googleapis.com/auth/cloud-platform'
            ]
        }
    ],
    'metadata': metadata
}

print(f"Creating VM-1: {VM1_NAME} ...")
operation = compute.instances().insert(
    project=PROJECT_ID,
    zone=ZONE,
    body=config
).execute()

print("Operation started. Check Google Cloud Console to monitor VM creation.")

def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    return result['items'] if 'items' in result else None

print("Your running instances are:")
for instance in list_instances(service, project, 'us-west1-b'):
    print(instance['name'])