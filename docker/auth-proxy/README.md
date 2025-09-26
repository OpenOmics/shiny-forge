# Auth Proxy Container

This container runs a small FastAPI application that validates Firebase ID tokens and forwards authenticated traffic to a private Cloud Run service that serves a Shiny application. It is designed to be deployed alongside a shiny-forge workload where the underlying Shiny app requires Cloud Run IAM authentication.

## Environment variables

The proxy expects the following runtime variables (set through Cloud Run --set-env-vars or secrets):

- TARGET_BASE_URL: URL of the private Shiny service (set automatically by the stack command).
- TARGET_AUDIENCE: Audience used when minting an identity token for the upstream Cloud Run service. Defaults to TARGET_BASE_URL.
- FIREBASE_PROJECT_ID: Firebase project that issued the end-user ID token.
- FIREBASE_ALLOWED_EMAILS: Optional comma-separated allow-list of email addresses.
- FIREBASE_ALLOWED_DOMAINS: Optional comma-separated allow-list of email domains.
- ALLOW_ANONYMOUS_OPTIONS: Allow unauthenticated CORS preflight requests (default \true).
- FORWARD_HEADERS: Optional comma-separated list of request headers to forward verbatim.
- UPSTREAM_TIMEOUT_SECONDS: Timeout applied to upstream calls (default 45).
- FIREBASE_TOKEN_COOKIE_NAMES: Optional comma-separated list of cookie names that may contain Firebase ID tokens (default `__session,firebase_id_token`).
- FIREBASE_LOGIN_REDIRECT: Path to redirect users to after a successful login (default `/`).
- FIREBASE_WEB_CONFIG: JSON string containing your Firebase web configuration (apiKey, authDomain, projectId, etc.). Required to render the `/login` experience.

## Artifacts template

Use the sample auth-proxy.artifacts file to provide build arguments and defaults:

```
FIREBASE_PROJECT_ID=
FIREBASE_ALLOWED_EMAILS=
FIREBASE_ALLOWED_DOMAINS=
ALLOW_ANONYMOUS_OPTIONS=true
FORWARD_HEADERS=content-type,x-request-id
UPSTREAM_TIMEOUT_SECONDS=45
FIREBASE_TOKEN_COOKIE_NAMES=__session,firebase_id_token
FIREBASE_LOGIN_REDIRECT=/
# Place the JSON payload on a single line when exporting to env vars
FIREBASE_WEB_CONFIG=
```

shiny-forge uses the artifacts file both for Docker build arguments and to populate runtime environment variables when deploying the proxy.

## Local development

```
cd docker/auth-proxy
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
TARGET_BASE_URL="https://example.com" FIREBASE_PROJECT_ID="demo" uvicorn app.main:app --reload
```

Provide a valid Firebase ID token in the Authorization header when testing locally. To exercise the browser login flow, set `FIREBASE_WEB_CONFIG` by exporting the Firebase web configuration JSON (for example, paste the JSON on a single line in your shell or load it from Secret Manager) so the `/login` page can bootstrap the Firebase SDK without committing credentials to the repository. When you run the helper scripts, you can also place `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS`, and other options in `.env`; they will be injected automatically.

For an end-to-end smoke test that includes a Shiny backend, use `python bin/run_local_auth_stack.py up ...` (ShinyCell2) or `python bin/run_local_auth_shiny_stack.py up ...` (legacy ShinyCell). Those helpers build the containers, serve `/login`, and wire the proxy to the sample app automatically.

After a successful sign-in at `/login`, requests to `/` now redirect to `/index.html` instead of returning the JSON status payload so testers immediately land in the Shiny UI.

### Documentation note

The architecture SVG used in the MkDocs pages (`auth-proxy-to-shinycell2.svg`) is treated as a generated asset and intentionally left untracked in Git. Export it from the design source (or copy the published version) before running `mkdocs build` locally; otherwise the rendered documentation will fall back to a missing image placeholder.
