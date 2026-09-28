"""Authorize Sentry MCP and save its refreshable credential in a vault.

This is deliberately a separate OAuth client from Claude Code's Sentry plugin.
Claude Code keeps its own tokens private. Scheduled Managed Agents sessions use
the credential created here, and Anthropic refreshes it from the vault.

The credential itself is created with `ant beta:vaults:credentials create`, the
same command the setup script uses for everything else, so the token travels on
that command's stdin and never through argv, .env, or the agent prompt.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

from dotenv import load_dotenv

# ./agents/setup.sh sources .env before calling this script, but a direct
# `uv run python oauth_setup.py` should find ANTHROPIC_API_KEY the same way,
# because `ant` does not read .env itself. Same override as managed_agents.py.
load_dotenv(override=True)

MCP_SERVER_URL = "https://mcp.sentry.dev/mcp"
CALLBACK_TIMEOUT_SECONDS = 300
README_LIMITATIONS = "README.md, 'Known limitations'"


def request_json(
    url: str,
    *,
    data: dict[str, Any] | None = None,
    form: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = None
    # Cloudflare rejects urllib's default Python-urllib user agent before the
    # request reaches Sentry's OAuth metadata endpoints.
    headers = {
        "Accept": "application/json",
        "User-Agent": "claude-quickstarts-sentry-oauth/1.0",
    }
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        body = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # OAuth errors are useful, but response bodies can contain server
        # details. Keep the terminal output bounded and never print tokens.
        detail = error.read(1000).decode(errors="replace")
        raise RuntimeError(f"{url} returned HTTP {error.code}: {detail}") from error


def discover_oauth() -> tuple[dict[str, Any], dict[str, Any]]:
    parsed = urllib.parse.urlparse(MCP_SERVER_URL)
    resource_metadata_url = (
        f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource{parsed.path}"
    )
    resource = request_json(resource_metadata_url)
    authorization_servers = resource.get("authorization_servers", [])
    if not authorization_servers:
        raise RuntimeError("Sentry MCP did not advertise an OAuth authorization server")

    issuer = authorization_servers[0].rstrip("/")
    issuer_parsed = urllib.parse.urlparse(issuer)
    if issuer_parsed.path in ("", "/"):
        metadata_url = f"{issuer}/.well-known/oauth-authorization-server"
    else:
        metadata_url = (
            f"{issuer_parsed.scheme}://{issuer_parsed.netloc}"
            f"/.well-known/oauth-authorization-server{issuer_parsed.path}"
        )
    return resource, request_json(metadata_url)


class CallbackHandler(BaseHTTPRequestHandler):
    result: ClassVar[dict[str, str]] = {}
    completed: ClassVar[threading.Event] = threading.Event()

    def do_GET(self) -> None:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        for key in ("code", "state", "error", "error_description"):
            if query.get(key):
                self.result[key] = query[key][0]

        success = "code" in self.result and "error" not in self.result
        body = (
            "Sentry authorization complete. Return to your terminal."
            if success
            else "Sentry authorization failed. Return to your terminal."
        ).encode()
        self.send_response(200 if success else 400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.completed.set()

    def log_message(self, _format: str, *_args: object) -> None:
        pass


def authorize() -> tuple[dict[str, Any], dict[str, Any], str]:
    resource, metadata = discover_oauth()
    for field in ("authorization_endpoint", "token_endpoint", "registration_endpoint"):
        if not metadata.get(field):
            raise RuntimeError(f"Sentry OAuth metadata is missing {field}")

    server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/callback"
    registration = request_json(
        metadata["registration_endpoint"],
        data={
            "client_name": "Claude Managed Agents Sentry triage quickstart",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    client_id = registration.get("client_id")
    if not client_id:
        raise RuntimeError("Sentry OAuth client registration returned no client_id")

    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    state = secrets.token_urlsafe(32)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge.decode(),
        "code_challenge_method": "S256",
        "resource": resource.get("resource", MCP_SERVER_URL),
    }
    # Request all scopes the server advertises so the consent screen shows every
    # available skill. The user's approval on the consent screen determines what
    # is actually granted; the token will carry only the approved subset.
    all_scopes = " ".join(resource.get("scopes_supported", []))
    if all_scopes:
        params["scope"] = all_scopes
    authorization_url = f"{metadata['authorization_endpoint']}?{urllib.parse.urlencode(params)}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(
        "Opening Sentry in your browser. On the approval screen, leave only "
        "'Inspect Issues & Events' and 'Seer' checked; untick 'Triage Issues' "
        "and 'Manage Projects & Teams'. The token carries only what you approve."
    )
    if not webbrowser.open(authorization_url):
        print(f"Open this URL:\n{authorization_url}")

    if not CallbackHandler.completed.wait(CALLBACK_TIMEOUT_SECONDS):
        server.shutdown()
        raise RuntimeError("timed out waiting for Sentry authorization")
    server.shutdown()

    if CallbackHandler.result.get("state") != state:
        raise RuntimeError("OAuth callback state did not match")
    if error := CallbackHandler.result.get("error"):
        description = CallbackHandler.result.get("error_description", "")
        raise RuntimeError(f"Sentry authorization failed: {error} {description}".strip())
    code = CallbackHandler.result.get("code")
    if not code:
        raise RuntimeError("Sentry authorization returned no code")

    token = request_json(
        metadata["token_endpoint"],
        form={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "resource": resource.get("resource", MCP_SERVER_URL),
        },
    )
    return token, metadata, client_id


def ant(*args: str, stdin: str | None = None) -> str:
    """Run an `ant` command and return its stdout, stripped."""
    completed = subprocess.run(
        ["ant", *args],
        input=stdin,
        text=True,
        check=True,
        stdout=subprocess.PIPE,
    )
    return completed.stdout.strip()


def save_to_vault(
    vault_id: str, token: dict[str, Any], metadata: dict[str, Any], client_id: str
) -> str:
    """Create the mcp_oauth credential and return its ID."""
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    if not access_token or not refresh_token:
        raise RuntimeError(
            "Sentry OAuth did not return both access and refresh tokens; "
            "refusing to create a credential that scheduled runs cannot refresh"
        )

    auth: dict[str, Any] = {
        "type": "mcp_oauth",
        "mcp_server_url": MCP_SERVER_URL,
        "access_token": access_token,
        "refresh": {
            "token_endpoint": metadata["token_endpoint"],
            "client_id": client_id,
            "refresh_token": refresh_token,
            "token_endpoint_auth": {"type": "none"},
            "resource": MCP_SERVER_URL,
        },
    }
    if scope := token.get("scope"):
        auth["refresh"]["scope"] = scope
    if expires_in := token.get("expires_in"):
        expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
        auth["expires_at"] = expires_at.isoformat().replace("+00:00", "Z")

    payload = {
        "display_name": "Sentry MCP OAuth (inspection and Seer)",
        "auth": auth,
    }
    # JSON is valid YAML, so the request body goes to ant on stdin exactly as
    # the environment_variable credential did in earlier versions of setup.sh.
    credential_id = ant(
        "beta:vaults:credentials",
        "create",
        "--vault-id",
        vault_id,
        "--transform",
        "id",
        "--raw-output",
        stdin=json.dumps(payload),
    )
    # Give the credential service a moment to make the new record visible to a
    # session started immediately by the setup guide.
    time.sleep(1)
    print(f"credential: created {credential_id} in {vault_id}")
    return credential_id


def validate(vault_id: str, credential_id: str) -> None:
    """Live-probe the new credential against the MCP server and report.

    The probe runs `initialize` and `tools/list` with the stored token. The
    vault always presents it as `Authorization: Bearer <token>`, so a server or
    organization that only accepts another scheme fails here, before the first
    scheduled run does. Advisory only: it reports and never fails setup, and
    run_now.py remains the real end-to-end test.
    """
    try:
        status = ant(
            "beta:vaults:credentials",
            "mcp-oauth-validate",
            "--vault-id",
            vault_id,
            "--credential-id",
            credential_id,
            "--transform",
            "status",
            "--raw-output",
        )
    except subprocess.CalledProcessError:
        print("credential: validation probe did not run; smoke-test with run_now.py")
        return
    print(f"credential: validation status {status}")
    if status == "invalid":
        print(
            "The MCP server rejected the stored token. If your Sentry organization "
            "enforces SSO or otherwise rejects user-bound OAuth tokens, see "
            f"{README_LIMITATIONS}."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-id", required=True)
    args = parser.parse_args()
    token, metadata, client_id = authorize()
    credential_id = save_to_vault(args.vault_id, token, metadata, client_id)
    validate(args.vault_id, credential_id)


if __name__ == "__main__":
    main()
