<div align="center">
   
  <h1>shiny-forge 🚀</h1>
  
  **_Simplifying the deployment of Shiny applications to the cloud_**

  [![GitHub issues](https://img.shields.io/github/issues/OpenOmics/shiny-forge?color=brightgreen)](https://github.com/OpenOmics/shiny-forge/issues) [![GitHub license](https://img.shields.io/github/license/OpenOmics/shiny-forge)](https://github.com/OpenOmics/shiny-forge/blob/main/LICENSE) 
  
  <i>
    This is the home of the tool, shiny-forge. Its long-term goals are to simplify the process of running, managing, and deploying Shiny applications.
  </i>
</div>


## Overview

`shiny-forge` is a command-line tool designed to streamline the deployment of [R Shiny applications](https://shiny.posit.co/r/getstarted/shiny-basics/lesson1/) to Google Cloud Platform (GCP) and Posit Connect. With integrated support for Docker, Google Cloud Platform (GCP), and Posit Connect, this tool enables users to build, deploy, and manage Shiny applications to the cloud with ease!

## Getting Started

### Dependencies

**Requires:** `docker`  `gcloud`

Before getting started, please ensure you have the following dependencies installed:

- [Docker](https://docs.docker.com/get-docker/): To build portability and reproducibility Shiny applications.
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install): To deploy applications directly to GCP for scalable, cloud-based hosting.
- [Python3](https://www.python.org/downloads): To run `shiny-forge` on your local machine.

### Installation

Once you have installed the dependencies above, please run the following commands to setup and install `shiny-forge`:

```bash
# Clone Repository from Github
git clone https://github.com/OpenOmics/shiny-forge.git
# Change your working directory
cd shiny-forge/
# Create a python virtual environment
python3 -m venv .venv
source .venv/bin/activate
# Install the required python packages
pip install -U pip
pip install -r requirements.txt

# Add shiny-forge to your $PATH
export PATH="${PATH}:${PWD}"
# Get usage information
shiny-forge -h
```

## Usage

### Deploy to Google Cloud Platform

```bash
# Create a new GCP deployment
shiny-forge create my-app ./path/to/Dockerfile ./path/to/artifacts.txt

# Update an existing GCP deployment
shiny-forge update my-app ./path/to/Dockerfile ./path/to/artifacts.txt

# List all deployed applications
shiny-forge read

# Get details about a specific application
shiny-forge read my-app

# Delete an application
shiny-forge delete my-app

# View application logs
shiny-forge logs my-app
```

### Deploy to Posit Connect

The `posit` subcommand allows you to deploy Shiny applications to Posit Connect servers. You can provide credentials and configuration either via command-line arguments or a JSON configuration file.

#### Using command-line arguments:

```bash
shiny-forge posit \
  --username your-username \
  --api-key your-api-key \
  --server https://connect.example.com \
  --app-dir ./path/to/shiny-app \
  --app-name my-shiny-app \
  --title "My Shiny Application"
```

#### Using a JSON configuration file:

Create a configuration file (e.g., `posit-config.json`):

```json
{
  "username": "your-username",
  "api_key": "your-api-key-here",
  "server": "https://connect.example.com",
  "app_dir": "/path/to/your/shiny-app",
  "app_name": "my-shiny-app",
  "title": "My Shiny Application"
}
```

Then deploy using:

```bash
shiny-forge posit --config posit-config.json
```

#### Combining config file with command-line overrides:

You can use a config file for most settings and override specific values via command-line:

```bash
shiny-forge posit --config posit-config.json --app-dir ./different-app
```

**Note:** An example configuration file is available at `data/posit-config-example.json`.

