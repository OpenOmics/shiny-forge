# ShinyCell2 container

The ShinyCell2 image builds on `gcr.io/openomics-gcp/shinycell2-base` and expects a Seurat RDS artifact plus project metadata, similar to the original ShinyCell container. See `docker/shinycell2/app/Dockerfile` for the full list of build args (`SEURAT_RDS`, `PROJECT_ID`, `DEFAULT_RED`, `RM_META`, `MAX_LEVELS`).

## Quick build example

```bash
cp ../../data/seurat-pbmc_small.rds .
docker buildx build \
  --platform linux/amd64 \
  --build-arg SEURAT_RDS=seurat-pbmc_small.rds \
  --build-arg PROJECT_ID="PBMC Demo" \
  -f Dockerfile \
  -t shinycell2:local .
```

## Local auth proxy testing

Use the shared helper to run the ShinyCell2 container with the Firebase auth proxy in front:

```bash
python bin/run_local_auth_stack.py up \
    --firebase-project-id my-firebase-project \
    --firebase-web-config C:/secrets/firebase-web-config.json

# Tear down when finished
python bin/run_local_auth_stack.py down --remove-network
```

The script launches ShinyCell2 on `http://localhost:8081`, the auth proxy on `http://localhost:8080`, and serves a `/login` page so you can complete browser-based sign-in before reaching the app.
