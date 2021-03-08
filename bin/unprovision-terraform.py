#!/bin/python3

import yaml
import terraform

with open('properties.yml') as f:
    properties = yaml.load(f, Loader=yaml.FullLoader)

terraform.destroy(properties.get('terraform_plan'))