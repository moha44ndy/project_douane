#!/usr/bin/env bash

set -e

python -m venv venv-sam-api

source ./venv-sam-api/bin/activate

pip install -r requirements.txt