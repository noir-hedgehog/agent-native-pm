#!/usr/bin/env python3
import argparse
import json
import urllib.error
import urllib.request


def request_json(method: str, url: str, token: str | None, api_key: str | None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url=url, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:  # nosec B310
        body = resp.read().decode("utf-8")
        return resp.status, body


def probe(base_url: str, path: str, token: str | None, api_key: str | None):
    url = f"{base_url.rstrip('/')}{path}"
    try:
        status, body = request_json("GET", url, token, api_key)
        print(f"OK {status} {url}")
        preview = body[:300] if body else ""
        print(preview)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"HTTP {e.code} {url}")
        print(body[:300])
    except Exception as e:
        print(f"ERROR {url}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Probe OpenClaw endpoints")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--health-path", default="/health")
    parser.add_argument("--runs-path", default="/runs")
    args = parser.parse_args()

    print("== OpenClaw probe ==")
    probe(args.base_url, args.health_path, args.token, args.api_key)
    probe(args.base_url, args.runs_path, args.token, args.api_key)


if __name__ == "__main__":
    main()
