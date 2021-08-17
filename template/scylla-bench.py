#!/bin/python3

import sys
import os

sys.path.insert(1, f"{os.environ['SSO']}/src/")

from time import sleep
from sso import common
from sso import terraform
from sso import scylla
from sso.scylla_bench import ScyllaBench
from sso.common import Iteration
from sso import prometheus

props = common.load_yaml('properties.yml')

env = common.load_yaml('environment.yml')
cluster_private_ips = env['cluster_private_ips']
cluster_string = ",".join(cluster_private_ips)

iteration = Iteration("dummy-benchmark")

bench = ScyllaBench(env['loadgenerator_public_ips'], props)
bench.install()
bench.prepare()

# clear and restarts the cluster. So any config changes will also be picked up
scylla.clear_cluster(env['cluster_public_ips'], props['cluster_user'], props['ssh_options'])

rows = 10_000_000

duration = "2m"

# Insert the test data.
bench.insert(rows, cluster_string)

# Restart to cluster to make sure the Scylla starts fresh 
# e.g. the memtable is flushed.
scylla.restart_cluster(env['cluster_public_ips'], props['cluster_user'], props['ssh_options'])

# Actual benchmark
bench.stress(f'-workload sequential -mode write -partition-count {rows} -nodes {cluster_string} -duration {duration} -host-selection-policy=token-aware')

# collect the results.
bench.collect_results(iteration.dir)

# Download and clear the prometheus data (can take a lot of time/space)
prometheus.download_and_clear(env, props, iteration)

# Automatically terminates the cluster.
#terraform.destroy(props['terraform_plan'])
print("Call 'unprovision-terraform' to destroy the created infrastructure!")

