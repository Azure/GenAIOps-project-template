#!/bin/bash

# Function to display error messages and exit
function error_exit {
    echo "❌ | $1" >&2
    exit 1
}

echo "🔶 | Post-provisioning - starting script"

# Function to check azd authentication status
function check_azd_auth {
    # Run 'azd auth login --check-status' and capture the output
    local status
    status=$(azd auth login --check-status 2>&1)

    if echo "$status" | grep -q "Not logged in"; then
        return 1
    else
        return 0
    fi
}

# Function to check Azure CLI (az) authentication status
function check_az_auth {
    # Attempt to show the current Azure account
    if ! az account show > /dev/null 2>&1; then
        return 1
    fi
    return 0
}

# Function to check if azd environment is refreshed
function check_azd_env {
    # Attempt to retrieve environment values
    if ! azd env get-values > /dev/null 2>&1; then
        return 1
    fi
    return 0
}

# Check Python version
echo "🐍 | Checking Python version..."
PYTHON_VERSION=$(python -V 2>&1 | grep -oP "\d+\.\d+")
if [[ "$PYTHON_VERSION" != "3.8" && "$PYTHON_VERSION" != "3.9" && "$PYTHON_VERSION" != "3.10" && "$PYTHON_VERSION" != "3.11" ]]; then
    error_exit "Python 3.8, 3.9, 3.10 or 3.11 is required. Current version: $PYTHON_VERSION"
else
    echo "✅ | Python version $PYTHON_VERSION detected."
fi

# Check if logged in to Azure CLI (az)
echo "🔍 | Checking Azure CLI authentication status..."
if ! check_az_auth; then
    echo "🔑 | You are not logged in to Azure CLI."
    echo "ℹ️  | Please run 'az login --use-device-code' to authenticate with Azure CLI."
    error_exit "Azure CLI authentication required. Exiting script."
else
    echo "✅ | Azure CLI is authenticated."
fi

# Check if logged in to azd
echo "🔍 | Checking azd authentication status..."
if ! check_azd_auth; then
    echo "🔑 | You are not logged in to azd."
    echo "ℹ️  | Please run 'azd auth login --use-device-code' to authenticate with azd."
    error_exit "azd authentication required. Exiting script."
else
    echo "✅ | azd is authenticated."
fi

# Check if azd environment is refreshed
echo "🔄 | Checking if azd environment is refreshed..."
if ! check_azd_env; then
    echo "⚠️  | Environment is not refreshed."
    echo "ℹ️  | Run 'azd env refresh' to get environment variables from your azure deployment."
    echo "ℹ️  | Choose the same environment name, subscription and location used when you deployed the environment."    
    error_exit "Failed to retrieve environment values using 'azd env get-values'"
else
    echo "✅ | azd environment is  refreshed."
    azd env get-values > .env
    echo "📄 | Environment values saved to .env."
fi

# Install dependencies
echo '📦 | Installing dependencies from "requirements.txt"...'
if ! pip install --upgrade pip setuptools; then
    error_exit "Failed to upgrade pip and setuptools."
fi

if ! python -m pip install -r requirements.txt -qq; then
    error_exit "Failed to install dependencies from requirements.txt."
fi
echo "📦 | Dependencies installed successfully."

# Populate sample data
echo "📊 | Populating sample data..."
export PYTHONPATH=./src:$PYTHONPATH
if ! python data/sample-documents-indexing.py; then
    error_exit "Failed to populate sample data."
fi
echo "🔶 | Post-provisioning - populated data successfully."
