<div align="center">
   
  <h1>shiny-forge 🚀</h1>
  
  **_Simplifying the deployment of Shiny applications to the cloud_**

  [![GitHub issues](https://img.shields.io/github/issues/OpenOmics/shiny-forge?color=brightgreen)](https://github.com/OpenOmics/shiny-forge/issues) [![GitHub license](https://img.shields.io/github/license/OpenOmics/shiny-forge)](https://github.com/OpenOmics/shiny-forge/blob/main/LICENSE) 
  
  <i>
    This is the home of the tool, shiny-forge. Its long-term goals are to simplify the process of running, managing, and deploying Shiny applications.
  </i>
</div>


## Overview

`shiny-forge` is a command-line tool designed to streamline the deployment of [R Shiny applications](https://shiny.posit.co/r/getstarted/shiny-basics/lesson1/) to Google Cloud Platform (GCP). With integrated support for Docker and Google Cloud Platform (GCP), this tool enables users to build, deploy, and manage Shiny applications to the cloud with ease!

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
