#!/usr/bin/env python3
"""Minimal Yandex.Disk public-resource client (stdlib only).

Usage:
  python3 yadisk.py list [--path P] [--depth N]
  python3 yadisk.py get  --path P [--out FILE]

It lists / downloads from a public Yandex.Disk folder without any extra deps,
so it works even before the venv finishes installing.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

API = "https://cloud-api.yandex.net/v1/disk/public/resources"
DOWNLOAD_API = "https://cloud-api.yandex.net/v1/disk/public/resources/download"

# Decoded public URL (urlencode will encode it exactly once).
DEFAULT_PUBLIC = (
    "https://disk.360.yandex.ru/d/xv-QHgR9iPxyWg/"
    "FUT, OPT_Срочный рынок (01.2025-12.2025)"
)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"HTTP {e.code} for {url}\n{body}", file=sys.stderr)
        raise


def _h(n):
    if not isinstance(n, (int, float)):
        return "?"
    n = float(n)
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}PB"


def list_resource(public_key, path=None, limit=1000, offset=0):
    params = {"public_key": public_key, "limit": limit, "offset": offset}
    if path:
        params["path"] = path
    return _get(API + "?" + urllib.parse.urlencode(params))


def walk(public_key, path=None, depth=0, maxdepth=1, indent=0):
    data = list_resource(public_key, path=path)
    if data.get("type") == "file" and depth == 0:
        print(f"[file] {data.get('name')}  size={data.get('size')} "
              f"({_h(data.get('size'))})  path={data.get('path')}")
        return
    emb = data.get("_embedded", {})
    items = emb.get("items", [])
    total = emb.get("total")
    print(f"{'  ' * indent}(dir) {data.get('name', '?')}  items_total={total}")
    for it in items:
        typ = it.get("type")
        name = it.get("name")
        size = it.get("size")
        p = it.get("path")
        if typ == "file":
            print(f"{'  ' * (indent + 1)}- {name}  {_h(size)}  path={p}")
        else:
            print(f"{'  ' * (indent + 1)}+ {name}/   path={p}")
            if depth < maxdepth:
                walk(public_key, path=p, depth=depth + 1,
                     maxdepth=maxdepth, indent=indent + 2)


def get_href(public_key, path):
    params = {"public_key": public_key}
    if path:
        params["path"] = path
    data = _get(DOWNLOAD_API + "?" + urllib.parse.urlencode(params))
    return data["href"]


def download(public_key, path, out, timeout=120):
    href = get_href(public_key, path)
    req = urllib.request.Request(href, headers={"User-Agent": "Mozilla/5.0"})
    t0 = time.time()
    done = 0
    next_mark = 50 * 1024 * 1024
    expected = 0
    # per-read socket timeout -> a stalled stream raises instead of hanging
    with urllib.request.urlopen(req, timeout=timeout) as r, open(out, "wb") as f:
        expected = int(r.headers.get("Content-Length") or 0)
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if done >= next_mark:
                sp = done / max(time.time() - t0, 1e-9) / 1024 / 1024
                print(f"  ... {_h(done)} / {_h(expected)}  {sp:.1f} MB/s", flush=True)
                next_mark += 50 * 1024 * 1024
    # guard against silent truncation (server closing the stream early)
    if expected and done < expected:
        raise IOError(f"truncated download: got {done} of {expected} bytes")
    print(f"Saved {out}  ({_h(done)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "get"])
    ap.add_argument("--public", default=DEFAULT_PUBLIC)
    ap.add_argument("--path", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--depth", type=int, default=1)
    a = ap.parse_args()
    if a.cmd == "list":
        walk(a.public, path=a.path, maxdepth=a.depth)
    elif a.cmd == "get":
        out = a.out or os.path.basename(a.path or "download.bin")
        download(a.public, a.path, out)


if __name__ == "__main__":
    main()
