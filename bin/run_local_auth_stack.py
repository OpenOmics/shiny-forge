#!/usr/bin/env python3
"""Run the ShinyCell2 + auth proxy stack locally for Firebase login testing."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = "/srv/shiny-server/shinycell2"
DATASET_IN_CONTAINER = "/opt2/seurat_object.rds"
BUILD_SCRIPT = PROJECT_ROOT / "docker/shinycell2/base/build_shinycell.R"
RUNTIME_CMD = [
    "R",
    "-e",
    "shiny::runApp('/srv/shiny-server/shinycell2', port=8080, host='0.0.0.0')",
]


def _load_project_env() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}
    env_vars: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        env_vars[key.strip()] = value
    return env_vars


PROJECT_ENV = _load_project_env()
DEFAULT_FIREBASE_PROJECT = PROJECT_ENV.get("FIREBASE_PROJECT_ID")


class CommandError(RuntimeError):
    """Raised when a subprocess call fails."""


def run(cmd: Iterable[str], *, cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess command, surfacing stdout/stderr on failure."""
    process = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and process.returncode != 0:
        raise CommandError(
            f"Command {' '.join(cmd)} failed with exit code {process.returncode}\n"
            f"stdout:\n{process.stdout}\n"
            f"stderr:\n{process.stderr}\n"
        )
    return process


def ensure_docker_available() -> None:
    try:
        run(["docker", "version"])
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise SystemExit("Docker CLI not found. Install Docker Desktop or docker-ce before running this script.") from exc
    except CommandError as exc:
        raise SystemExit("Docker is not responding. Ensure the daemon is running and try again.") from exc


def build_shiny_image(args: argparse.Namespace) -> None:
    print("[+] Building ShinyCell2 image ...")
    dockerfile = (PROJECT_ROOT / args.shiny_dockerfile).resolve()
    if not dockerfile.exists():
        raise SystemExit(f"Dockerfile not found: {dockerfile}")

    rds_path = Path(args.seurat_rds).expanduser().resolve()
    if not rds_path.exists():
        raise SystemExit(f"Seurat RDS file not found: {rds_path}")

    default_red = args.default_reduction or "NA"
    rm_meta = args.rm_meta or "NA"
    max_levels_value = str(args.max_levels) if args.max_levels is not None else "NA"

    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        dockerfile_dest = tmp_path / "Dockerfile"
        shutil.copy2(dockerfile, dockerfile_dest)

        dataset_dest = tmp_path / rds_path.name
        shutil.copy2(rds_path, dataset_dest)

        build_cmd = [
            "docker",
            "build",
            "--progress=plain",
            "--platform",
            args.platform,
            "-t",
            args.shiny_image,
            "--build-arg",
            f"SEURAT_RDS={dataset_dest.name}",
            "--build-arg",
            f"PROJECT_ID={args.project_id}",
            "--build-arg",
            f"DEFAULT_RED={default_red}",
            "--build-arg",
            f"RM_META={rm_meta}",
            "--build-arg",
            f"MAX_LEVELS={max_levels_value}",
            str(tmp_path),
        ]
        run(build_cmd)
    print(f"    Built image {args.shiny_image}")


def build_proxy_image(args: argparse.Namespace) -> None:
    print("[+] Building auth proxy image ...")
    context = PROJECT_ROOT / args.proxy_context
    if not context.is_dir():
        raise SystemExit(f"Proxy context directory not found: {context}")

    build_cmd = [
        "docker",
        "build",
        "--progress=plain",
        "--platform",
        args.platform,
        "-t",
        args.proxy_image,
        ".",
    ]
    run(build_cmd, cwd=context)
    print(f"    Built image {args.proxy_image}")


def ensure_network(name: str) -> None:
    inspect = run(["docker", "network", "inspect", name], check=False)
    if inspect.returncode == 0:
        return
    print(f"[+] Creating docker network '{name}'")
    run(["docker", "network", "create", name])


def remove_container(name: str) -> None:
    run(["docker", "rm", "-f", name], check=False)


def image_has_shiny_app(image: str) -> bool:
    result = run(
        ["docker", "run", "--rm", image, "test", "-d", APP_DIR],
        check=False,
    )
    return result.returncode == 0


def get_image_cmd(image: str) -> Optional[list[str]]:
    result = run([
        "docker",
        "image",
        "inspect",
        image,
        "--format",
        "{{json .Config.Cmd}}",
    ], check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def bake_shiny_app(
    image: str,
    dataset_path: Path,
    project_id: str,
    default_reduction: Optional[str],
    rm_meta: Optional[str],
    max_levels: Optional[int],
) -> None:
    container_name = f"{image.replace(':', '_').replace('/', '_')}-bake"
    remove_container(container_name)

    dataset_mount = f"{dataset_path}:{DATASET_IN_CONTAINER}:ro"
    script_mount: Optional[str] = None
    if BUILD_SCRIPT.exists():
        script_mount = "/tmp/build_shinycell.R"

    original_cmd = get_image_cmd(image)
    if not original_cmd or any("build_shinycell" in part for part in original_cmd):
        original_cmd = RUNTIME_CMD

    script_parts = [
        "Rscript",
        script_mount or "/opt2/build_shinycell.R",
        "--obj",
        DATASET_IN_CONTAINER,
        "--proj",
        project_id,
    ]
    if rm_meta:
        script_parts.extend(["--rmmeta", rm_meta])
    if default_reduction:
        script_parts.extend(["--defred", default_reduction])
    if max_levels is not None:
        script_parts.extend(["--maxlevels", str(max_levels)])

    script = " ".join(shlex.quote(part) for part in script_parts)

    run([
        "docker",
        "run",
        "--name",
        container_name,
        "--user",
        "shinyuser",
        "-v",
        dataset_mount,
        *(["-v", f"{BUILD_SCRIPT}:{script_mount}:ro"] if script_mount else []),
        image,
        "/bin/bash",
        "-lc",
        script,
    ])

    commit_cmd = ["docker", "commit"]
    if original_cmd:
        commit_cmd.extend(["--change", f"CMD {json.dumps(original_cmd)}"])
    run(commit_cmd + [container_name, image])
    remove_container(container_name)


def wait_for_container_health(name: str, timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", name],
            check=False,
        )
        if result.returncode != 0:
            time.sleep(2)
            continue
        status = result.stdout.strip()
        if status == "healthy":
            return True
        if status == "unhealthy":
            print(f"    Container '{name}' reported unhealthy status")
            return False
        time.sleep(2)
    print(f"    Timed out waiting for container '{name}' healthcheck")
    return False


def wait_for_http(url: str, timeout: int = 60) -> int:
    deadline = time.time() + timeout
    last_error: Optional[Exception] = None
    while time.time() < deadline:
        try:
            with urlopen(url) as response:
                return response.getcode()
        except (URLError, HTTPError) as err:  # pragma: no cover - network timing dependent
            last_error = err
            time.sleep(1)
    if last_error:
        raise last_error
    raise TimeoutError(f"Timed out waiting for {url}")


def start_containers(args: argparse.Namespace) -> None:
    ensure_network(args.network)

    rds_path = Path(args.seurat_rds).expanduser().resolve()
    if not rds_path.exists():
        raise SystemExit(f"Seurat RDS file not found: {rds_path}")

    if not image_has_shiny_app(args.shiny_image):
        print("[+] ShinyCell2 assets missing from image; generating via build_shinycell.R ...")
        bake_shiny_app(
            args.shiny_image,
            rds_path,
            args.project_id,
            args.default_reduction,
            args.rm_meta,
            args.max_levels,
        )

    remove_container(args.shiny_container)
    remove_container(args.proxy_container)

    shiny_cmd = [
        "docker",
        "run",
        "-d",
        "--rm",
        "--name",
        args.shiny_container,
        "--network",
        args.network,
        "-p",
        f"{args.shiny_host_port}:8080",
        args.shiny_image,
    ]
    run(shiny_cmd)
    print(f"[+] Shiny container '{args.shiny_container}' started on port {args.shiny_host_port}")

    if not wait_for_container_health(args.shiny_container, timeout=args.shiny_health_timeout):
        print("    Warning: Shiny container did not reach healthy status in time.")

    env_pairs = {
        "TARGET_BASE_URL": f"http://{args.shiny_container}:8080",
        "TARGET_AUDIENCE": args.target_audience or f"http://{args.shiny_container}:8080",
        "FIREBASE_PROJECT_ID": args.firebase_project_id,
        "FIREBASE_ALLOWED_EMAILS": ",".join(args.firebase_allowed_emails) if args.firebase_allowed_emails else "",
        "FIREBASE_ALLOWED_DOMAINS": ",".join(args.firebase_allowed_domains) if args.firebase_allowed_domains else "",
        "ALLOW_ANONYMOUS_OPTIONS": "true" if args.allow_anonymous_options else "false",
        "FORWARD_HEADERS": args.forward_headers,
        "UPSTREAM_TIMEOUT_SECONDS": str(args.upstream_timeout),
    }

    cookie_names = args.firebase_cookie_names
    if cookie_names:
        env_pairs["FIREBASE_TOKEN_COOKIE_NAMES"] = ",".join(cookie_names)
    else:
        env_cookie_names = PROJECT_ENV.get("FIREBASE_TOKEN_COOKIE_NAMES")
        if env_cookie_names:
            env_pairs["FIREBASE_TOKEN_COOKIE_NAMES"] = env_cookie_names

    if args.login_redirect:
        env_pairs["FIREBASE_LOGIN_REDIRECT"] = args.login_redirect
    elif PROJECT_ENV.get("FIREBASE_LOGIN_REDIRECT"):
        env_pairs["FIREBASE_LOGIN_REDIRECT"] = PROJECT_ENV["FIREBASE_LOGIN_REDIRECT"]

    web_config_value = args.firebase_web_config or PROJECT_ENV.get("FIREBASE_WEB_CONFIG")
    if web_config_value:
        loaded = web_config_value
        try:
            candidate = Path(web_config_value).expanduser()
            if candidate.exists():
                loaded = candidate.read_text(encoding="utf-8")
        except (OSError, ValueError):
            pass
        env_pairs["FIREBASE_WEB_CONFIG"] = loaded

    proxy_cmd = [
        "docker",
        "run",
        "-d",
        "--rm",
        "--name",
        args.proxy_container,
        "--network",
        args.network,
        "-p",
        f"{args.proxy_host_port}:8080",
    ]

    for key, value in env_pairs.items():
        proxy_cmd.extend(["-e", f"{key}={value}"])

    temp_paths: list[Path] = []

    credentials_path: Optional[Path] = None
    credentials_value = args.firebase_credentials or PROJECT_ENV.get("FIREBASE_CREDENTIALS")
    if credentials_value:
        stripped = credentials_value.strip()
        if stripped.startswith("{"):
            fd, tmp_name = tempfile.mkstemp(prefix="firebase-cred-", suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_fp:
                tmp_fp.write(stripped)
            credentials_path = Path(tmp_name)
            temp_paths.append(credentials_path)
        else:
            credentials_path = Path(credentials_value).expanduser().resolve()
            if not credentials_path.exists():
                raise SystemExit(f"Firebase credentials file not found: {credentials_path}")

        container_path = PurePosixPath("/secrets/firebase.json")
        proxy_cmd.extend([
            "-v",
            f"{credentials_path}:{container_path}:ro",
            "-e",
            f"GOOGLE_APPLICATION_CREDENTIALS={container_path}",
        ])

    emulator_host = args.firebase_auth_emulator or PROJECT_ENV.get("FIREBASE_AUTH_EMULATOR_HOST")
    if emulator_host:
        proxy_cmd.extend([
            "-e",
            f"FIREBASE_AUTH_EMULATOR_HOST={emulator_host}",
        ])

    proxy_cmd.append(args.proxy_image)

    run(proxy_cmd)
    print(f"[+] Auth proxy container '{args.proxy_container}' started on port {args.proxy_host_port}")

    health_url = f"http://localhost:{args.proxy_host_port}/healthz"
    try:
        code = wait_for_http(health_url, timeout=args.proxy_start_timeout)
        print(f"    Proxy health endpoint responded with HTTP {code}")
    except Exception as exc:  # pragma: no cover - depends on docker runtime
        print(f"    Warning: unable to confirm proxy readiness: {exc}")

    for tmp in temp_paths:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def stop_containers(args: argparse.Namespace) -> None:
    print("[+] Stopping proxy container ...")
    remove_container(args.proxy_container)
    print("[+] Stopping Shiny container ...")
    remove_container(args.shiny_container)
    if args.remove_network:
        print(f"[+] Removing docker network '{args.network}' ...")
        run(["docker", "network", "rm", args.network], check=False)


def smoke_test(args: argparse.Namespace) -> None:
    if not args.firebase_id_token:
        print("[-] No Firebase ID token supplied; skipping authenticated smoke test.")
        return

    target_url = f"http://localhost:{args.proxy_host_port}{args.test_path}"
    print(f"[+] Running authenticated smoke test against {target_url}")
    headers = {"Authorization": f"Bearer {args.firebase_id_token}"}
    request = Request(target_url, headers=headers)
    try:
        with urlopen(request, timeout=args.smoke_timeout) as response:
            status = response.getcode()
            print(f"    Received HTTP {status} from proxy. Auth flow appears functional.")
    except HTTPError as err:
        print(f"    Proxy returned HTTP {err.code}: {err.reason}")
        body = err.read().decode("utf-8", errors="ignore")
        if body:
            print(f"    Response body:\n{body}")
    except URLError as err:
        print(f"    Failed to reach proxy: {err.reason}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--network", default="shiny-auth-test", help="Docker network name (default: %(default)s)")
    common.add_argument("--platform", default="linux/amd64", help="Docker target platform (default: %(default)s)")

    up_parser = subparsers.add_parser("up", parents=[common], help="Build images and start the local stack")
    up_parser.add_argument("--shiny-dockerfile", default="docker/shinycell2/app/Dockerfile", help="Dockerfile for the ShinyCell2 container")
    up_parser.add_argument("--seurat-rds", default=str(PROJECT_ROOT / "data/seurat-pbmc_small.rds"), help="Path to the Seurat RDS file")
    up_parser.add_argument("--project-id", default="PBMC Demo", help="Project identifier for the Shiny app")
    up_parser.add_argument("--default-reduction", default=None, help="Default reduction to display (optional)")
    up_parser.add_argument("--rm-meta", default=None, help="Metadata columns to remove (optional)")
    up_parser.add_argument("--max-levels", type=int, default=None, help="Maximum factor levels for categorical metadata (optional)")
    up_parser.add_argument("--shiny-image", default="shinycell2-local:test", help="Tag for the local ShinyCell2 image")
    up_parser.add_argument("--proxy-image", default="auth-proxy-local:test", help="Tag for the local auth proxy image")
    up_parser.add_argument("--proxy-context", default="docker/auth-proxy", help="Build context directory for the auth proxy")
    up_parser.add_argument("--shiny-container", default="shinycell2-local", help="Container name for the Shiny service")
    up_parser.add_argument("--proxy-container", default="auth-proxy-local", help="Container name for the proxy service")
    up_parser.add_argument("--shiny-host-port", type=int, default=8081, help="Host port bound to the Shiny container")
    up_parser.add_argument("--proxy-host-port", type=int, default=8080, help="Host port exposed by the auth proxy")
    up_parser.add_argument("--firebase-project-id", default=DEFAULT_FIREBASE_PROJECT, help="Firebase project ID used for token validation")
    up_parser.add_argument("--firebase-credentials", help="Path to service account JSON used to mint identity tokens")
    up_parser.add_argument("--firebase-auth-emulator", help="HOST:PORT for a running Firebase Auth emulator")
    up_parser.add_argument("--firebase-allowed-email", action="append", dest="firebase_allowed_emails", help="Allow-list specific email (repeatable)")
    up_parser.add_argument("--firebase-allowed-domain", action="append", dest="firebase_allowed_domains", help="Allow-list specific email domain (repeatable)")
    up_parser.add_argument("--firebase-cookie-name", action="append", dest="firebase_cookie_names", help="Cookie name used to store Firebase ID tokens (repeatable)")
    up_parser.add_argument("--firebase-web-config", help="Firebase web config JSON string or path to a JSON file")
    up_parser.add_argument("--login-redirect", help="Path to redirect to after successful login (default: /)")
    up_parser.add_argument("--forward-headers", default="content-type,x-request-id", help="Comma-separated headers to forward upstream")
    up_parser.add_argument(
        "--allow-anonymous-options",
        dest="allow_anonymous_options",
        action="store_true",
        default=True,
        help="Allow unauthenticated OPTIONS requests (default: true)",
    )
    up_parser.add_argument(
        "--disallow-anonymous-options",
        dest="allow_anonymous_options",
        action="store_false",
        help="Disable unauthenticated OPTIONS requests",
    )
    up_parser.add_argument("--upstream-timeout", type=int, default=45, help="Upstream timeout in seconds")
    up_parser.add_argument("--skip-build", action="store_true", help="Reuse existing images without rebuilding")
    up_parser.add_argument("--proxy-start-timeout", type=int, default=60, help="Seconds to wait for proxy health endpoint")
    up_parser.add_argument("--shiny-health-timeout", type=int, default=180, help="Seconds to wait for Shiny healthcheck")
    up_parser.add_argument("--firebase-id-token", help="Firebase ID token for the smoke test")
    up_parser.add_argument("--test-path", default="/", help="Path used for the authenticated smoke test")
    up_parser.add_argument("--smoke-timeout", type=int, default=30, help="Seconds to wait for the smoke test response")
    up_parser.add_argument("--target-audience", help="Override TARGET_AUDIENCE when minting identity tokens")

    down_parser = subparsers.add_parser("down", parents=[common], help="Stop containers and optionally remove the docker network")
    down_parser.add_argument("--shiny-container", default="shinycell2-local", help="Container name for the Shiny service")
    down_parser.add_argument("--proxy-container", default="auth-proxy-local", help="Container name for the proxy service")
    down_parser.add_argument("--remove-network", action="store_true", help="Remove the docker network after stopping containers")

    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    ensure_docker_available()

    if args.command == "up" and not args.firebase_project_id:
        raise SystemExit("firebase-project-id is required (set flag or FIREBASE_PROJECT_ID in .env)")

    if args.command == "up":
        if not args.skip_build:
            build_shiny_image(args)
            build_proxy_image(args)
        else:
            print("[+] Skipping image builds (per --skip-build)")

        start_containers(args)
        smoke_test(args)
        print("[+] Stack is ready. Open the proxy at http://localhost:%d" % args.proxy_host_port)
        print("    Supply a Firebase ID token in the Authorization header to authenticate.")
        return 0

    if args.command == "down":
        stop_containers(args)
        return 0

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
