## Steps for Building Docker Images

`deploy-shinycell` needs an RDS file containing a Seurat object and a project identifer (i.e NCBR-42, NIAMS-42, NHLBI-42, NIDDK-42, RTBGRS-42, etc.). An example RDS file has been provided within this Github repository. Please see 'seurat-pbmc_small.rds' in the data directory for an example. This RDS file was created using the `pbmc_small` seurat object that is bundled with newer versions of [Seurat](https://satijalab.org/seurat/).

It was created with by running the following R (version 4.4.3) code:
```
library(Seurat)
data(pbmc_small)
class(pbmc_small) # Sanity check: should return seurat object
saveRDS(pbmc_small, "seurat-pbmc_small.rds")
```

Please see the instructions below for building an image using the provided Dockerfile, a Seurat RDS file, and a Project ID. Please use the following steps as a guide to build, test, and push your image to DockerHub:

```bash
# See listing of images on computer
docker image ls

# Build from Dockerfile
# Create tag for the image
pid="NCBR-0"               # Example project identifier 
tag="v0.1.0_${pid:-test}"  # Semantic version for docker image
docker buildx build --build-arg SEURAT_RDS=seurat-pbmc_small.rds --build-arg ${pid:-test}  --platform linux/amd64 --no-cache -f Dockerfile --tag="shinycell:${tag:-v0.1.0_test}" .

# Testing, take a peek inside
# the filesystem, check all
# dependencies were installed,
# debug any problems, etc.
docker run --platform linux/amd64 -ti "shinycell:${tag:-v0.1.0_test}" /bin/bash
# Start up the application,
# runs on localhost:3838
docker run --platform linux/amd64 -p 3838:3838 "shinycell:${tag:-v0.1.0_test}"

# Updating tag before pushing to DockerHub
docker tag shinycell:v0.1.0 "skchronicles/shinycell:${tag:-v0.1.0_test}"

# Check out new tag(s)
docker image ls

# Push new tagged image to DockerHub
docker push --platform linux/amd64 "skchronicles/shinycell:${tag:-v0.1.0_test}"
```

### Other Recommended Steps

Scan your image for known vulnerabilities:

```bash
docker scan "shinycell:${tag:-v0.1.0_test}"
```

> **Please Note**: Any references to `skchronicles` should be replaced your username if you would also like to push the image to a non-org account.
