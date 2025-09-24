# Auth Proxy Container

This container runs a small FastAPI application that validates Firebase ID tokens and forwards authenticated traffic to a private Cloud Run service that serves a Shiny application. It is designed to be deployed alongside a shiny-forge workload where the underlying Shiny app requires Cloud Run IAM authentication.

## Environment variables

The proxy expects the following runtime variables (set through Cloud Run --set-env-vars or secrets):

- TARGET_BASE_URL: URL of the private Shiny service (set automatically by the stack command).
- TARGET_AUDIENCE: Audience used when minting an identity token for the upstream Cloud Run service. Defaults to TARGET_BASE_URL.
- FIREBASE_PROJECT_ID: Firebase project that issued the end-user ID token.
- FIREBASE_ALLOWED_EMAILS: Optional comma-separated allow-list of email addresses.
- FIREBASE_ALLOWED_DOMAINS: Optional comma-separated allow-list of email domains.
- ALLOW_ANONYMOUS_OPTIONS: Allow unauthenticated CORS preflight requests (default 	rue).
- FORWARD_HEADERS: Optional comma-separated list of request headers to forward verbatim.
- UPSTREAM_TIMEOUT_SECONDS: Timeout applied to upstream calls (default 45).

## Artifacts template

Use the sample uth-proxy.artifacts file to provide build arguments and defaults:

`
FIREBASE_PROJECT_ID=
FIREBASE_ALLOWED_EMAILS=
FIREBASE_ALLOWED_DOMAINS=
ALLOW_ANONYMOUS_OPTIONS=true
FORWARD_HEADERS=content-type,x-request-id
UPSTREAM_TIMEOUT_SECONDS=45
`

shiny-forge uses the artifacts file both for Docker build arguments and to populate runtime environment variables when deploying the proxy.

## Local development

`ash
cd docker/auth-proxy
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
TARGET_BASE_URL="https://example.com" FIREBASE_PROJECT_ID="demo" uvicorn app.main:app --reload
`

Provide a valid Firebase ID token in the Authorization header when testing locally.
