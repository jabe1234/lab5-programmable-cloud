#!/usr/bin/env python3

import argparse
import os
import time
from pprint import pprint

import googleapiclient.discovery
import google.auth

credentials, project = google.auth.default()
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

PROJECT = "serious-truck-450805-d9"
ZONE = "us-west1-b"
INSTANCE_NAME = "flask-vm"
MACHINE_TYPE = f"zones/{ZONE}/machineTypes/f1-micro"
IMAGE_PROJECT = "ubuntu-os-cloud"
IMAGE_FAMILY = "ubuntu-2204-lts"
NETWORK = "global/networks/default"
FIREWALL_NAME = "allow-5000"
TAG_NAME = "allow-5000"

startup_script = """#!/bin/bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip git
mkdir -p /opt/flask_app
cd /opt/flask_app
git clone https://github.com/cu-csci-4253-datacenter/flask-tutorial
cd flask-tutorial
sudo python3 setup.py install
sudo pip3 install -e .
export FLASK_APP=flaskr
flask init-db
nohup flask run -h 0.0.0.0 -p 5000 &
"""

def create_firewall():
    firewall_list = service.firewalls().list(project=PROJECT).execute()
    if "items" in firewall_list:
        for f in firewall_list["items"]:
            if f["name"] == FIREWALL_NAME:
                print(f"Firewall {FIREWALL_NAME} already exists.")
                return
    
    firewall_body = {
        "name": FIREWALL_NAME,
        "allowed": [{"IPProtocol": "tcp", "ports": ["5000"]}],
        "direction": "INGRESS",
        "sourceRanges": ["0.0.0.0/0"],
        "targetTags": [TAG_NAME],
        "network": NETWORK
    }
    request = service.firewalls().insert(project=PROJECT, body=firewall_body)
    response = request.execute()
    print(f"Firewall {FIREWALL_NAME} created: {response}")

def create_instance():
    image_response = service.images().getFromFamily(
        project=IMAGE_PROJECT, family=IMAGE_FAMILY).execute()
    source_disk_image = image_response['selfLink']

    config = {
        "name": INSTANCE_NAME,
        "machineType": MACHINE_TYPE,
        "tags": {"items": [TAG_NAME]},
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {"sourceImage": source_disk_image},
            }
        ],
        "networkInterfaces": [
            {
                "network": NETWORK,
                "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}],
            }
        ],
        "metadata": {"items": [{"key": "startup-script", "value": startup_script}]},
    }

    request = service.instances().insert(project=PROJECT, zone=ZONE, body=config)
    response = request.execute()
    print(f"Instance creation started: {response}")

    operation_name = response["name"]
    while True:
        result = service.zoneOperations().get(
            project=PROJECT, zone=ZONE, operation=operation_name).execute()
        if result["status"] == "DONE":
            print("VM instance created.")
            break
        time.sleep(2)

    instance_info = service.instances().get(project=PROJECT, zone=ZONE, instance=INSTANCE_NAME).execute()
    external_ip = instance_info["networkInterfaces"][0]["accessConfigs"][0]["natIP"]
    print(f"Visit your Flask app at: http://{external_ip}:5000")

if __name__ == "__main__":
    create_firewall()
    create_instance()

def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    return result['items'] if 'items' in result else None

print("Your running instances are:")
for instance in list_instances(service, PROJECT, ZONE):
    print(instance['name'])