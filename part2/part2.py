#!/usr/bin/env python3

import argparse
import os
import time
from pprint import pprint

import googleapiclient.discovery
import google.auth
from google.cloud import compute_v1
from google.api_core.exceptions import NotFound

credentials, project = google.auth.default()
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

PROJECT = "serious-truck-450805-d9"
ZONE = "us-west1-b" 
INSTANCE_NAME = "flask-vm"
SNAPSHOT_NAME = f"base-snapshot-{INSTANCE_NAME}"
NEW_INSTANCES = ["flask-clone-1", "flask-clone-2", "flask-clone-3"]
MACHINE_TYPE = "e2-medium"
IMAGE_PROJECT = "ubuntu-os-cloud"
IMAGE_FAMILY = "ubuntu-2204-lts"
NETWORK = "global/networks/default"

disks_client = compute_v1.DisksClient()
instances_client = compute_v1.InstancesClient()
snapshots_client = compute_v1.SnapshotsClient()

def create_snapshot():
    """
    Check if the snapshot exists.
    If it exists, skip creation (or delete & recreate if desired).
    """
    try:
        snapshot = snapshots_client.get(project=PROJECT, snapshot=SNAPSHOT_NAME)
        print(f"Snapshot '{SNAPSHOT_NAME}' already exists. Skipping creation.")
        return
    except NotFound:
        print(f"Snapshot '{SNAPSHOT_NAME}' does not exist. Creating it now...")
    
    snapshot_resource = compute_v1.Snapshot(name=SNAPSHOT_NAME)
    operation = disks_client.create_snapshot(
        project=PROJECT,
        zone=ZONE,
        disk=INSTANCE_NAME,
        snapshot_resource=snapshot_resource
    )
    operation.result()
    print(f"Snapshot '{SNAPSHOT_NAME}' created successfully.")

def create_instance_from_snapshot(instance_name):
    source_snapshot = f"projects/{PROJECT}/global/snapshots/{SNAPSHOT_NAME}"
    disk = compute_v1.AttachedDisk()
    disk.auto_delete = True
    disk.boot = True
    disk.type_ = "PERSISTENT"

    disk.initialize_params = compute_v1.AttachedDiskInitializeParams()
    disk.initialize_params.source_snapshot = source_snapshot

    network_interface = compute_v1.NetworkInterface()
    network_interface.network = NETWORK
    access_config = compute_v1.AccessConfig()
    access_config.name = "External NAT"
    access_config.type_ = "ONE_TO_ONE_NAT"
    network_interface.access_configs = [access_config]

    instance = compute_v1.Instance(
        name=instance_name,
        machine_type=f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}",
        disks=[disk],
        network_interfaces=[network_interface]
    )

    instance.metadata = compute_v1.Metadata()
    instance.metadata.items = [
        compute_v1.Items(
            key="startup-script",
            value="""#!/bin/bash
    cd /opt/flask_app/flask-tutorial
    export FLASK_APP=flaskr
    flask init-db
    nohup flask run -h 0.0.0.0 -p 5000 &
    """
        )
    ]

    tags = compute_v1.Tags()
    tags.items = ["allow-5000"]
    instance.tags = tags

    start_time = time.time()
    operation = instances_client.insert(
        project=PROJECT,
        zone=ZONE,
        instance_resource=instance
    )
    operation.result() 
    elapsed = time.time() - start_time
    print(f"Instance '{instance_name}' created in {elapsed:.2f} seconds.")
    return elapsed


def instance_exists(instance_name: str) -> bool:
    """Check if a VM instance already exists."""
    try:
        instances_client.get(project=PROJECT, zone=ZONE, instance=instance_name)
        return True
    except NotFound:
        return False

if __name__ == "__main__":
    create_snapshot()
    
    timing_results = {}
    for inst in NEW_INSTANCES:
        if instance_exists(inst):
            print(f"Instance '{inst}' already exists. Skipping creation.")
            continue
        elapsed_time = create_instance_from_snapshot(inst)
        timing_results[inst] = elapsed_time

    with open("./TIMING.md", "w") as f:
        f.write("# Instance Creation Timing\n\n")
        for inst, t in timing_results.items():
            f.write(f"- {inst}: {t:.2f} seconds\n")
    print("TIMING.md created.")

def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    return result['items'] if 'items' in result else None

print("Your running instances are:")
for instance in list_instances(service, PROJECT, ZONE):
    print(instance['name'])