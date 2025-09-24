# Repository Guidelines
## Project Structure & Module Organization
shiny-forge is the CLI entry point that orchestrates deployments. Core modules live in src/: uild.py handles Cloud Build and Cloud Run orchestration, parse.py parses artifact files and wraps gcloud helpers, hooks.py cleans up temporary assets, and config.py centralises defaults. Command helpers stay in in/ (for example make_artifacts.py). Docker assets include the Shiny demos in docker/shinycell* and the Firebase-enabled proxy in docker/auth-proxy/. Sample datasets live in data/, while MkDocs content in docs/ mirrors supported workflows?update those pages whenever behaviour changes.

## Build, Test, and Development Commands
- python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1 to prepare an isolated PowerShell environment.
- pip install -r requirements.txt (and docs/requirements.txt for MkDocs) to install runtime dependencies.
- ./shiny-forge --help to inspect commands. Use ./shiny-forge create ... / update ... for single services and ./shiny-forge stack ... to launch a Shiny app plus auth proxy.
- mkdocs serve to preview documentation updates locally.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indent, descriptive docstrings, and type hints on public functions. Keep CLI flag names aligned with function parameters (including the new stack options). Route shared constants through src/config.py and wire new helper modules through src/__init__.py only when necessary.

## Testing Guidelines
There is no automated suite yet?new work should add pytest coverage in 	ests/ (grouped by module). Favour fixtures and mocks for gcloud and Firebase calls, and add smoke tests for the proxy that validate token enforcement. Run pytest -q before opening a PR.

## Commit & Pull Request Guidelines
Commits follow the existing conventional style (eat:, ix:, etc.) with issue references where applicable. PRs should describe behavioural changes, list manual verification (./shiny-forge stack ... against the sample Dockerfiles), and include logs or screenshots for deployment-facing tweaks. Tag reviewers when introducing new GCP resources or IAM bindings.

## GCP & Configuration Tips
Authenticate with gcloud auth login, ensure the openomics-gcp project is active, and avoid committing service-account material. Store Firebase secrets in Secret Manager and surface them via environment variables during stack deployments. Update src/config.py when adding regions or tuning resource limits so scripts stay consistent.
