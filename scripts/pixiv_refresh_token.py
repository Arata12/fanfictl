#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import secrets
import sys
import urllib.parse
import webbrowser

import httpx


CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"
REDIRECT_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
AUTH_URL = "https://app-api.pixiv.net/web/v1/login"
TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
USER_AGENT = "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Get a Pixiv refresh token for Fableport"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="Start Pixiv OAuth login flow")
    login_parser.add_argument(
        "--no-browser", action="store_true", help="Do not auto-open the browser"
    )

    refresh_parser = subparsers.add_parser(
        "refresh", help="Exchange an existing refresh token"
    )
    refresh_parser.add_argument("refresh_token", help="Existing Pixiv refresh token")

    args = parser.parse_args()
    if args.command == "login":
        return run_login(no_browser=args.no_browser)
    if args.command == "refresh":
        return run_refresh(args.refresh_token)
    parser.print_help()
    return 1


def run_login(*, no_browser: bool) -> int:
    verifier = _create_code_verifier()
    challenge = _create_code_challenge(verifier)
    state = secrets.token_urlsafe(16)

    params = {
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "client": "pixiv-android",
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": state,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("Open this URL and sign into Pixiv:")
    print(url)
    print()
    print("After login, Pixiv redirects to a callback URL containing ?code=...")
    print("Paste either the full callback URL or just the code below.")
    print("The code expires quickly, so do it immediately.")
    print()

    if not no_browser:
        webbrowser.open(url)

    pasted = input("Callback URL or code: ").strip()
    code = _extract_code(pasted)
    if not code:
        print("Could not extract a Pixiv OAuth code from your input.", file=sys.stderr)
        return 2

    payload = exchange_code_for_token(code=code, code_verifier=verifier)
    print_token_result(payload)
    return 0


def run_refresh(refresh_token: str) -> int:
    payload = refresh_access_token(refresh_token)
    print_token_result(payload)
    return 0


def exchange_code_for_token(*, code: str, code_verifier: str) -> dict:
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "include_policy": "true",
        "redirect_uri": REDIRECT_URI,
    }
    return _post_token_request(data)


def refresh_access_token(refresh_token: str) -> dict:
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "include_policy": "true",
        "refresh_token": refresh_token,
    }
    return _post_token_request(data)


def _post_token_request(data: dict) -> dict:
    response = httpx.post(
        TOKEN_URL,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "App-OS": "android",
            "App-OS-Version": "11",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("has_error") or payload.get("error"):
        raise RuntimeError(payload)
    return payload


def print_token_result(payload: dict) -> None:
    print()
    print("Pixiv OAuth succeeded.")
    print()
    print("refresh_token:")
    print(payload.get("refresh_token", ""))
    print()
    print("access_token:")
    print(payload.get("access_token", ""))
    print()
    print(
        "Use the refresh_token in Fableport Settings or in .env as PIXIV_REFRESH_TOKEN."
    )


def _create_code_verifier() -> str:
    return secrets.token_urlsafe(32)


def _create_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _extract_code(value: str) -> str | None:
    if "code=" in value:
        parsed = urllib.parse.urlparse(value)
        query = urllib.parse.parse_qs(parsed.query)
        code = query.get("code", [None])[0]
        return code
    return value or None


if __name__ == "__main__":
    raise SystemExit(main())
