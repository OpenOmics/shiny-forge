# Steps for Building Docker Images

Directly below are instructions for building an image using the provided Dockerfile:

```bash
# See listing of images on computer
docker image ls

# Build from Dockerfile
docker buildx build --platform linux/amd64 --no-cache -f Dockerfile --tag=example:v0.1.0 .

# Testing, take a peek inside
docker run --platform linux/amd64 -ti example:v0.1.0 /bin/bash

# Updating Tag  before pushing to DockerHub
docker tag example:v0.1.0 skchronicles/example:v0.1.0
docker tag example:v0.1.0 skchronicles/example         # latest

# Check out new tag(s)
docker image ls

# Push new tagged image to DockerHub
docker push --platform linux/amd64 skchronicles/example:v0.1.0
docker push --platform linux/amd64 skchronicles/example:latest
```

### Other Recommended Steps

Scan your image for known vulnerabilities:

```bash
docker scan example:v0.1.0
```

> **Please Note**: Any references to `skchronicles` should be replaced your username if you would also like to push the image to a non-org account.


# Build Arguments

It is necessary to build `artifact` files for deploying different shiny apps using shiny-forge. For each shiny app 
potentially different inputs and different configuration values are accepted and utilized. This is where docker 
[build arguments](https://docs.docker.com/build/building/variables/) comes in, they allow the docker image of the 
shiny application to route different files or configuration values. The following is a curated list of shiny-forge
supported applications and a break down of their various build arguments.

## shinycell

Source: https://github.com/SGDDNB/ShinyCell

| BUILD_ARG  |  Description  | Optional? |
|---|---|---|
| SEURAT_RDS | File path to seurat object  | No |
| PROJECT_ID | Project (or unique key) for application instance | No |
| DEFAULT_RED | Dimensional reduction to display by default on the application | Yes |
| RM_META | Comma delimited list of meta data columns to _NOT_ include for application | Yes |

## shinycell2

Souce: https://github.com/the-ouyang-lab/ShinyCell2

| BUILD_ARG  |  Description  | Optional? |
|---|---|---|
| SEURAT_RDS | File path to seurat object  | No |
| PROJECT_ID | Project (or unique key) for application instance | No |
| DEFAULT_RED | Dimensional reduction to display by default on the application | Yes |
| RM_META | Comma delimited list of meta data columns to _NOT_ include for application | Yes |