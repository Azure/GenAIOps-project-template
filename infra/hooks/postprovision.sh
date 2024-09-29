#!/bin/bash

echo "🔶 | Post-provisioning - starting script"

if [ "$GITHUB_ACTIONS" == "true" ]; then
    echo "Running in GitHub Actions - exporting environment variables"
    # Output environment variables to .env file using azd env get-values
    azd env get-values > .env
else
    echo "Not running in GitHub Actions - skipping azd env get-values"
fi

# Run sample documents ingestion
echo 'Installing dependencies from "requirements.txt"'
pip install --upgrade pip setuptools 
# python -m pip install --upgrade --force-reinstall -r requirements.txt 
python -m pip install -r requirements.txt 
echo "Populating sample data ...."
export PYTHONPATH=./src:$PYTHONPATH
python data/sample-documents-indexing.py 

echo "🔶 | Post-provisioning - populated data"