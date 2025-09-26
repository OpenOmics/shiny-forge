# How to use shiny-forge

## CREATE


The `shiny-forge create` sub-command is used to create an entirely new google cloud run instance
serving the shiny application of interest.

The create command requires 3 arguments:
```bash
usage: shiny-forge create [-h] [--cloud] [--max-cpu MAXCPU] [--max-memory MAXMEM] app_name docker artifacts

positional arguments:
  app_name             Name of the application to deploy on the `openomics-gcp` project
  docker               Dockerfile or to use for shiny application
  artifacts            File containing the mapping between Dockerfile

optional arguments:
  -h, --help           show this help message and exit
  --cloud              File containing the mapping between Dockerfile
  --max-cpu MAXCPU     Maximum number of CPUs to use for application (Default 2 CPU)
  --max-memory MAXMEM  Maximum number of memory (in gigabytes) to use for application (Default 4GiB)
```

### Required Arguments

#### Dockerfile

The dockerfile utilized here should be the final Dockerfile in any type of staged build. It should accept
all the relevant docker [BUILD ARGUMENTS](https://docs.docker.com/build/building/variables/) with default values for optional arguments.

And should all specific google cloud run container requirements: https://cloud.google.com/run/docs/deploying

See [ShinyCell2 Dockerfile](../docker/shinycell2/app/Dockerfile) for a qualified example.

#### Artifacts file

The artifacts file is basically the equivalent syntax of [ENV files](https://www.geeksforgeeks.org/python/how-to-create-and-use-env-files-in-python/).
It is a plain text file without any restrictions of file extentsion that includes key-value pairs mapped to each other using "=" and pairs are
seperated by line breaks. Such as:

```bash
SEURAT_RDS=path/to/seurat_object.rds
PROJECT_ID=project-title
DEFAULT_RED=default.reduction
RM_META=meta.data.to.remove
MAX_LEVELS=100
```

#### App name

A alphanumeric identifier which can only contain digits, letters, letters and hyphens, the last character cannot be a hyphen and the maximum
possible length of the identifer is 63 characters.

> [!IMPORTANT] 
> Resource name must use only lowercase letters, numbers and '-'. Must begin with a letter and cannot end with a '-'. Maximum length is 63 characters. 
> These requirements are set by google: 
> - https://cloud.google.com/compute/docs/labeling-resources
> - https://cloud.google.com/compute/docs/naming-resources


### Optional Arguments

#### --cloud

An optional flag that tells the application to build the docker image using Google cloud build service rather than
locally building the docker image and pushing that image up to run on google cloud.

This costs extra with regard to google cloud billing, however is the only way to build some larger docker images
given the necessary resources.

> [!NOTE]  
> Google cloud activities of shiny-forge are controlled by the `gcloud` application
> any users of this option need to have the correct permissions and be authenticated
> with the `gcloud` application before use

#### --max-cpu

An optional flag that dictates the maximum number of CPUs to utilize within the shiny application instance

> [!NOTE]
> This CPU resource allocation refers to the instance serving the Shiny application, not the 
> instance that the docker image is built on.

> [!IMPORTANT]  
> Utilizing more additional CPUs will charge the GCP billing account at a higher rate, see
> https://cloud.google.com/products/calculator for pricing details

#### --max-memory

An optional flag that dictates the maximum number of gigabytes of RAM memory to utilize within the shiny application instance

> [!NOTE]
> This memory resource allocation refers to the instance serving the Shiny application, not the 
> instance that the docker image is built on.

> [!IMPORTANT]  
> Utilizing more additional memory will charge the GCP billing account at a higher rate, see
> https://cloud.google.com/products/calculator for pricing details

## READ

```
usage: shiny-forge read [-h] [app_name]

positional arguments:
  app_name    Name of the application to get details for

optional arguments:
  -h, --help  show this help message and exit
```

### No arguments

Running `shiny-forge read` without any arguments will list all the running cloud run jobs:

```bash
$ ./shiny-forge read
NAME         META_ID    COMMIT_SHA                                DEPLOYED_BY   DEPLOYED_ON
project_one  id1        0c735ecfd3de9237e8a7728817e83d52d456e1a4  clouduser     06-16-2025
project_one  id2        0c735ecfd3de9237e8a7728817e83d52d456e1a4  clouduser     06-17-2025
project_one  id3        65e83cf600cbb51803f9fb459b13f5f0d9e83cb8  clouduser     06-03-2025
```

### With <app_name>

Running `shiny-forge read` with a project identifer will list additional information about the cloud run job:

```bash
$ ./shiny-forge read project-0541
✔ Service project-0541 in region us-west1
 
URL:     https://project-1.us-west1.run.app
Ingress: all
Traffic:
  100% LATEST (currently grs-0541-00001-z2b)
 
Scaling:          Auto (Min: 0)
Threat Detection: Enabled
 
Last updated on 2025-05-19T21:17:42.227833Z by clouduser@google.com:
  Revision project-0541-00001-z2b
  Container None
    Image:           gcr.io/project-registry/project-0541:latest
    Port:            8080
    Memory:          2Gi
    CPU:             1
    Startup Probe:
      TCP every 240s
      Port:          8080
      Initial delay: 0s
      Timeout:       240s
      Failure threshold: 1
      Type:          Default
  Service account:   clouduser@google.com
  Concurrency:       80
  Max instances:     100
  Timeout:           300s
```

## UPDATE

Update is essentially the same command as create. The important distinction here is that <app_name> must
already exist in google cloud run, and the application will be deployed to replace the previous iteration[revision]
of the application. The required and optional arguments are exactly the same:

```
usage: shiny-forge update [-h] [--cloud] [--max-cpu MAXCPU] [--max-memory MAXMEM] app_name docker artifacts

positional arguments:
  app_name             Name of the application
  docker               Dockerfile or to use for shiny application
  artifacts            File containing the mapping between Dockerfile

optional arguments:
  -h, --help           show this help message and exit
  --cloud              File containing the mapping between Dockerfile
  --max-cpu MAXCPU     Maximum number of CPUs to use for application (Default 2 CPU)
  --max-memory MAXMEM  Maximum number of memory (in gigabytes) to use for application (Default 4GiB)
```

## DELETE

Delete sub-command will delete instances of google cloud run by <app_name> unique identifier.

```
usage: shiny-forge delete [-h] app_name

positional arguments:
  app_name    Name of the application

optional arguments:
  -h, --help  show this help message and exit
```

> [!IMPORTANT]  
> Utilizing more additional memory will charge the GCP billing account at a higher rate, see
> https://cloud.google.com/products/calculator for pricing details

## LOGS

Logs sub-command will list the log entries for a particular <app_name> in a YAML-esque format

```
usage: shiny-forge logs [-h] [--lastn LASTN] app_name

positional arguments:
  app_name       Name of the application

optional arguments:
  -h, --help     show this help message and exit
  --lastn LASTN  Limit log entries to the last N entries
```

### --lastn

This is a optional key word argument that limits the returned logs to *n* entries, where *n* is the integer specified as the value
## STACK

Use shiny-forge stack when you want to deploy a Shiny service that requires Firebase-authenticated access via the new proxy image located in docker/auth-proxy. The CLI will first publish the Shiny container with Cloud Run ingress restricted to IAM callers, then deploy the proxy in front of it and connect the two services.

`ash
./shiny-forge stack shinycell-auth \
    docker/shinycell/app/Dockerfile \
    docker/shinycell/app/artifacts \
    shinycell-auth-proxy \
    docker/auth-proxy/Dockerfile \
    docker/auth-proxy/auth-proxy.artifacts \
    --app-max-cpu 2 --app-max-memory 4 \
    --proxy-max-cpu 1 --proxy-max-memory 2 \
    --proxy-service-account shiny-proxy@openomics-gcp.iam.gserviceaccount.com
`

### Artifacts for the proxy

Populate docker/auth-proxy/auth-proxy.artifacts with Firebase project details and any optional allow-lists. At deploy time, stack injects those values as Cloud Run environment variables and appends the discovered Shiny URL (TARGET_BASE_URL) and audience (TARGET_AUDIENCE). Keep sensitive values (for example API keys) in Secret Manager and hydrate them into the artifacts file via environment substitution before running the command.

### Behaviour overview

1. Shiny service is built with cloud_build(... allow_unauthenticated=False) so only authenticated callers can reach it.
2. The proxy service is deployed with Firebase enforcement and granted oles/run.invoker on the Shiny service.
3. The command prints the proxy URL; distribute that endpoint to authenticated users and supply Firebase ID tokens through the Authorization: Bearer <token> header.

If you need to update both services, re-run the same command with --update to push new images while leaving URLs intact.

### Local auth proxy smoke test

Use `bin/run_local_auth_stack.py` when you want to validate the Firebase login flow against the ShinyCell2 sample without touching Cloud Run resources. The helper now serves a `/login` page so testers can sign in through Firebase like they would in production. If you still need the original ShinyCell example, invoke `bin/run_local_auth_shiny_stack.py` instead; it keeps the same interface but targets `/srv/shiny-server/shinycell`.

```
python bin/run_local_auth_stack.py up \
    --firebase-project-id my-firebase-project \
    --firebase-credentials C:/path/to/service-account.json \
    --firebase-web-config C:/secrets/firebase-web-config.json \
    --firebase-id-token eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

The script will:

1. Build local images for the Shiny app (using `data/seurat-pbmc_small.rds`) and the auth proxy.
2. Launch both containers on an isolated docker network and expose the proxy on `http://localhost:8080` (the Shiny service sits on `http://localhost:8081`).
3. Serve an interactive Firebase login page at `/login` that stores the ID token in a secure cookie before redirecting to the app.
4. Optionally issue an authenticated request to confirm a supplied Firebase ID token is accepted.

Pass `--skip-build` to reuse existing images, `--target-audience` when you need a specific Cloud Run audience for identity tokens, `--firebase-cookie-name` to test custom cookie names, and `--disallow-anonymous-options` to mirror production CORS behaviour. Tear the environment down with:

```
python bin/run_local_auth_stack.py down --remove-network
# (Use bin/run_local_auth_shiny_stack.py for the legacy ShinyCell sample.)
```

Ensure Docker Desktop is running locally and provide Firebase service account credentials (or emulator settings) so the proxy can mint identity tokens for the Shiny container. For the web experience, export your Firebase web configuration JSON (apiKey, authDomain, projectId, etc.) into an environment variable or secret referenced by `--firebase-web-config`; this keeps credentials out of source control while unlocking browser-based testing.
If you already store `FIREBASE_PROJECT_ID`, `FIREBASE_WEB_CONFIG`, `FIREBASE_CREDENTIALS`, `FIREBASE_TOKEN_COOKIE_NAMES`, `FIREBASE_LOGIN_REDIRECT`, or `FIREBASE_AUTH_EMULATOR_HOST` in a project-level `.env`, the helper will read those values automatically. Copy `.env.example` to `.env` for a starter template. After authenticating at `/login`, a visit to `http://localhost:8080/` now redirects into the Shiny UI instead of returning the JSON readiness payload.
