import asyncio
import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Iterable, Optional
from urllib.parse import urljoin

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import websockets
import firebase_admin
from firebase_admin import auth as firebase_auth
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token

load_dotenv()

logger = logging.getLogger("auth-proxy")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())

APP_ROOT = Path(__file__).resolve().parent

TARGET_BASE_URL = os.environ.get("TARGET_BASE_URL")
if not TARGET_BASE_URL:
    raise RuntimeError("TARGET_BASE_URL environment variable is required.")
TARGET_BASE_URL = TARGET_BASE_URL.rstrip("/")
TARGET_AUDIENCE = os.environ.get("TARGET_AUDIENCE", TARGET_BASE_URL)
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")
ALLOW_ANONYMOUS_OPTIONS = os.environ.get("ALLOW_ANONYMOUS_OPTIONS", "true").lower() == "true"
FORWARD_HEADERS = {h.strip().lower() for h in os.environ.get("FORWARD_HEADERS", "").split(",") if h.strip()}
ALLOWED_EMAILS = {email.strip().lower() for email in os.environ.get("FIREBASE_ALLOWED_EMAILS", "").split(",") if email.strip()}
ALLOWED_DOMAINS = {domain.strip().lower() for domain in os.environ.get("FIREBASE_ALLOWED_DOMAINS", "").split(",") if domain.strip()}
UPSTREAM_TIMEOUT_SECONDS = float(os.environ.get("UPSTREAM_TIMEOUT_SECONDS", "45"))
TOKEN_COOKIE_NAMES = [
    name.strip() for name in os.environ.get("FIREBASE_TOKEN_COOKIE_NAMES", "__session,firebase_id_token").split(",") if name.strip()
]
LOGIN_REDIRECT_PATH = os.environ.get("FIREBASE_LOGIN_REDIRECT", "/")

_firebase_web_config_raw = os.environ.get("FIREBASE_WEB_CONFIG")
if _firebase_web_config_raw:
    try:
        FIREBASE_WEB_CONFIG = json.loads(_firebase_web_config_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FIREBASE_WEB_CONFIG must contain valid JSON") from exc
else:
    FIREBASE_WEB_CONFIG = None

_login_template = (APP_ROOT / "login.html")
LOGIN_TEMPLATE_CONTENT = _login_template.read_text(encoding="utf-8") if _login_template.exists() else None

if not firebase_admin._apps:
    firebase_admin.initialize_app()

HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
}

app = FastAPI(title="shiny-forge auth proxy", version="0.1.0")


def _render_login_page() -> str:
    if not LOGIN_TEMPLATE_CONTENT:
        return "<h1>Login unavailable</h1><p>Missing login.html template in the container image.</p>"
    if not FIREBASE_WEB_CONFIG:
        return (
            "<h1>Login unavailable</h1>"
            "<p>Set the <code>FIREBASE_WEB_CONFIG</code> environment variable to serve the login page.</p>"
        )
    config_json = json.dumps(FIREBASE_WEB_CONFIG)
    encoded = base64.b64encode(config_json.encode("utf-8")).decode("ascii")
    primary_cookie = TOKEN_COOKIE_NAMES[0] if TOKEN_COOKIE_NAMES else "__session"
    return (
        LOGIN_TEMPLATE_CONTENT
        .replace("__FIREBASE_CONFIG_B64__", encoded)
        .replace("__FIREBASE_COOKIE__", primary_cookie)
        .replace("__FIREBASE_REDIRECT__", LOGIN_REDIRECT_PATH)
    )


def _extract_token_from_cookies(request: Request) -> Optional[str]:
    for name in TOKEN_COOKIE_NAMES:
        value = request.cookies.get(name)
        if not value:
            continue
        if value.lower().startswith("bearer "):
            return value.split(" ", 1)[1]
        return value
    return None


def _get_bearer_token(request: Request) -> Optional[str]:
    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]
    return _extract_token_from_cookies(request)


def _clear_token_cookies(response: Response) -> None:
    for name in TOKEN_COOKIE_NAMES:
        response.delete_cookie(name, path="/")


def _build_logout_response(redirect: Optional[str] = None) -> Response:
    if redirect:
        response: Response = RedirectResponse(url=redirect, status_code=307)
    else:
        response = JSONResponse({"status": "ok"})
    _clear_token_cookies(response)
    return response


class IdentityTokenProvider:
    """Simple cache for Cloud Run identity tokens."""

    def __init__(self, audience: str):
        self._audience = audience
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._lock = asyncio.Lock()
        self._request = GoogleAuthRequest()

    async def _fetch(self) -> str:
        return await asyncio.to_thread(google_id_token.fetch_id_token, self._request, self._audience)

    async def token(self) -> str:
        async with self._lock:
            now = time.time()
            if self._token and now < self._expires_at - 60:
                return self._token
            token = await self._fetch()
            # Tokens are valid for roughly an hour; refresh slightly early
            self._token = token
            self._expires_at = now + 3000
            return token


identity_tokens = IdentityTokenProvider(TARGET_AUDIENCE)


@app.on_event("startup")
async def _startup() -> None:
    timeout = httpx.Timeout(UPSTREAM_TIMEOUT_SECONDS, read=UPSTREAM_TIMEOUT_SECONDS)
    app.state.http = httpx.AsyncClient(timeout=timeout, follow_redirects=True)


@app.on_event("shutdown")
async def _shutdown() -> None:
    http_client: httpx.AsyncClient = app.state.http
    await http_client.aclose()


def _email_allowed(email: Optional[str]) -> bool:
    if not ALLOWED_EMAILS and not ALLOWED_DOMAINS:
        return True
    if not email:
        return False
    email = email.lower()
    if ALLOWED_EMAILS and email in ALLOWED_EMAILS:
        return True
    if ALLOWED_DOMAINS:
        domain = email.split("@")[-1]
        if domain in ALLOWED_DOMAINS:
            return True
    return False


async def require_firebase_user(request: Request) -> Dict:
    if request.method == "OPTIONS" and ALLOW_ANONYMOUS_OPTIONS:
        return {}

    token = _get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization bearer token")
    try:
        decoded = firebase_auth.verify_id_token(token, clock_skew_seconds=60)
    except Exception as exc:  # firebase_admin raises several specific errors; wrap into 401
        logger.debug("Failed to verify Firebase token", exc_info=exc)
        raise HTTPException(status_code=401, detail="Invalid Firebase ID token") from exc

    if FIREBASE_PROJECT_ID and decoded.get("aud") != FIREBASE_PROJECT_ID:
        raise HTTPException(status_code=401, detail="Token audience mismatch")

    email = decoded.get("email")
    if not _email_allowed(email):
        raise HTTPException(status_code=403, detail="Email is not permitted")

    request.state.firebase_claims = decoded
    request.state.firebase_token = token
    return decoded


def _prepare_headers(
    original_headers: Iterable[tuple[str, str]],
    claims: Dict,
    firebase_token: Optional[str],
    client_host: Optional[str],
) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for key, value in original_headers:
        lower = key.lower()
        if lower in HOP_HEADERS:
            continue
        if lower == "authorization":
            continue
        if FORWARD_HEADERS and lower not in FORWARD_HEADERS:
            continue
        headers[key] = value
    headers["X-Forwarded-User"] = claims.get("email", claims.get("uid", ""))
    headers["X-Firebase-UID"] = claims.get("uid", "")
    if firebase_token:
        headers["X-Firebase-Token"] = firebase_token
    if client_host:
        existing = headers.get("X-Forwarded-For")
        headers["X-Forwarded-For"] = f"{existing}, {client_host}" if existing else client_host
    return headers


@app.get("/healthz")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/login", response_class=HTMLResponse)
async def login_page() -> HTMLResponse:
    content = _render_login_page()
    status_code = 200 if FIREBASE_WEB_CONFIG else 503
    return HTMLResponse(content=content, status_code=status_code)


@app.post("/logout")
async def api_logout() -> Response:
    return _build_logout_response()


@app.get("/logout")
async def logout_page(request: Request) -> Response:
    redirect_target = request.query_params.get("redirect") or "/login"
    return _build_logout_response(redirect_target)


@app.post("/session")
async def establish_session(payload: Dict[str, str], request: Request) -> JSONResponse:
    token = payload.get("token") or payload.get("idToken") or payload.get("id_token")
    if not token:
        logger.warning("/session called without token payload")
        raise HTTPException(status_code=400, detail="Missing Firebase ID token")

    try:
        decoded = firebase_auth.verify_id_token(token, clock_skew_seconds=60)
    except Exception as exc:  # noqa: BLE001 - firebase raises multiple subclasses
        logger.debug("Failed to verify Firebase token during session creation", exc_info=exc)
        raise HTTPException(status_code=401, detail="Invalid Firebase ID token") from exc

    if FIREBASE_PROJECT_ID and decoded.get("aud") != FIREBASE_PROJECT_ID:
        logger.warning(
            "Firebase token audience mismatch",
            extra={
                "expected_aud": FIREBASE_PROJECT_ID,
                "token_aud": decoded.get("aud"),
                "uid": decoded.get("uid"),
            },
        )
        raise HTTPException(status_code=401, detail="Token audience mismatch")

    if not _email_allowed(decoded.get("email")):
        logger.warning(
            "Firebase email not permitted",
            extra={
                "email": decoded.get("email"),
                "uid": decoded.get("uid"),
            },
        )
        raise HTTPException(status_code=403, detail="Email is not permitted")

    cookie_name = TOKEN_COOKIE_NAMES[0] if TOKEN_COOKIE_NAMES else "__session"
    secure = request.url.scheme == "https"

    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        cookie_name,
        token,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=3600,
    )
    logger.info(
        "Session established",
        extra={
            "uid": decoded.get("uid"),
            "email": decoded.get("email"),
        },
    )
    return response


@app.get("/")
async def root(request: Request) -> Response:
    token = _get_bearer_token(request)

    if not token:
        return RedirectResponse(url="/login", status_code=307)

    try:
        await require_firebase_user(request)
    except HTTPException as exc:
        if exc.status_code == 401:
            return RedirectResponse(url="/login", status_code=307)
        raise

    return await proxy("", request)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(path: str, request: Request) -> Response:
    claims = await require_firebase_user(request)

    if request.method == "OPTIONS" and ALLOW_ANONYMOUS_OPTIONS:
        response = Response(status_code=200)
        response.headers.update({
            "Access-Control-Allow-Origin": request.headers.get("Origin", "*"),
            "Access-Control-Allow-Headers": request.headers.get(
                "Access-Control-Request-Headers", "Authorization, Content-Type"
            ),
            "Access-Control-Allow-Methods": request.headers.get(
                "Access-Control-Request-Method", "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            ),
            "Access-Control-Max-Age": "3600",
        })
        return response

    downstream_url = TARGET_BASE_URL
    if path:
        downstream_url = urljoin(f"{TARGET_BASE_URL}/", path)

    content = await request.body()
    firebase_token = getattr(request.state, "firebase_token", None)
    headers = _prepare_headers(request.headers.items(), claims, firebase_token, request.client.host if request.client else None)
    query_params = list(request.query_params.multi_items())

    identity = await identity_tokens.token()
    headers["Authorization"] = f"Bearer {identity}"

    client: httpx.AsyncClient = app.state.http
    try:
        upstream = await client.request(
            request.method,
            downstream_url,
            params=query_params,
            content=content if content else None,
            headers=headers,
        )
    except httpx.HTTPError as exc:
        logger.error("Upstream request failed", exc_info=exc)
        raise HTTPException(status_code=502, detail="Failed to reach upstream service") from exc

    skip_headers = HOP_HEADERS | {"content-encoding"}
    filtered_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in skip_headers}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=filtered_headers)


@app.websocket("/{path:path}")
async def websocket_proxy(websocket: WebSocket, path: str) -> None:
    token = _get_bearer_token(websocket)
    if not token:
        await websocket.close(code=4401)
        return

    fake_request = Request(scope={
        "type": "http",
        "headers": [],
        "method": "GET",
        "path": f"/{path}",
        "query_string": b"",
    })
    fake_request._cookies = websocket.cookies
    try:
        await require_firebase_user(fake_request)
    except HTTPException:
        await websocket.close(code=4403)
        return

    await websocket.accept()

    downstream_url = TARGET_BASE_URL
    if path:
        downstream_url = urljoin(f"{TARGET_BASE_URL}/", path)
    downstream_url = downstream_url.replace("http://", "ws://").replace("https://", "wss://")

    async with websockets.connect(downstream_url) as upstream_ws:
        async def client_to_upstream() -> None:
            try:
                while True:
                    message = await websocket.receive()
                    if "text" in message:
                        await upstream_ws.send(message["text"])
                    elif "bytes" in message:
                        await upstream_ws.send(message["bytes"])
                    elif message.get("type") == "ping":
                        await upstream_ws.ping()
                    elif message.get("type") == "close":
                        await upstream_ws.close()
                        break
            except Exception:
                await upstream_ws.close()

        async def upstream_to_client() -> None:
            try:
                async for data in upstream_ws:
                    if isinstance(data, str):
                        await websocket.send_text(data)
                    else:
                        await websocket.send_bytes(data)
            except Exception:
                await websocket.close()

        await asyncio.gather(client_to_upstream(), upstream_to_client())

@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    logger.debug("Returning error %s", exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
