"""Builds a Decky Loader store: the official plugin list plus the plugins in my-plugins.json.

Output (served by GitHub Pages, store URL = https://<user>.github.io/<repo>/plugins):
  site/plugins/index.html           -> GET {store}?sort_by=...   (plugin list)
  site/plugins/versions/index.html  -> GET {store}/versions      (update check)

The files are JSON; Decky parses the body and ignores the content type.
"""
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

OFFICIAL_URL = "https://plugins.deckbrew.xyz/plugins"
MAX_VERSIONS = 5           # releases listed per plugin of mine, newest first
MY_ID_BASE = 900000        # ids for my plugins, far from the official ones

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "site")


def fetch(url, accept="application/json"):
    headers = {"User-Agent": "decky-store-builder", "Accept": accept}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
        return r.read()


def fetch_json(url):
    return json.loads(fetch(url))


def build_my_plugin(index, entry):
    repo = entry["repo"]
    asset_name = entry["asset"]
    releases = [
        r for r in fetch_json(f"https://api.github.com/repos/{repo}/releases?per_page=30")
        if not r["draft"] and (entry.get("prereleases") or not r["prerelease"])
    ]
    versions = []
    for rel in releases:
        asset = next((a for a in rel["assets"] if a["name"] == asset_name), None)
        if not asset:
            continue
        url = asset["browser_download_url"]
        print(f"  {repo} {rel['tag_name']}: hashing {url}")
        versions.append({
            # Decky compares this with the installed package.json version, so no "v".
            "name": rel["tag_name"].lstrip("vV"),
            "hash": hashlib.sha256(fetch(url, "application/octet-stream")).hexdigest(),
            "artifact": url,
            "created": rel["published_at"],
            "downloads": asset["download_count"],
            "updates": 0,
        })
        if len(versions) >= MAX_VERSIONS:
            break
    if not versions:
        raise RuntimeError(f"{repo}: no release has an asset named {asset_name}")

    latest_tag = next(r["tag_name"] for r in releases if any(a["name"] == asset_name for a in r["assets"]))
    meta = fetch_json(f"https://raw.githubusercontent.com/{repo}/{latest_tag}/plugin.json")
    publish = meta.get("publish", {})
    return {
        "id": MY_ID_BASE + index,
        "name": meta["name"],
        "author": meta.get("author", repo.split("/")[0]),
        "description": entry.get("description") or publish.get("description", ""),
        "tags": publish.get("tags", []),
        "image_url": entry.get("image_url") or publish.get("image", ""),
        "versions": versions,
        "visible": True,
        "created": versions[-1]["created"],
        "updated": versions[0]["created"],
        "downloads": sum(v["downloads"] for v in versions),
        "updates": 0,
    }


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def main():
    official = fetch_json(OFFICIAL_URL)
    if not isinstance(official, list) or not official:
        raise RuntimeError("official store returned an empty or invalid list")
    print(f"Official store: {len(official)} plugins")

    with open(os.path.join(ROOT, "my-plugins.json"), encoding="utf-8") as f:
        mine_cfg = json.load(f)
    mine = [build_my_plugin(i, e) for i, e in enumerate(mine_cfg, start=1)]
    print(f"My plugins: {[p['name'] for p in mine]}")

    # A plugin of mine with the same name as an official one replaces it.
    my_names = {p["name"] for p in mine}
    plugins = mine + [p for p in official if p["name"] not in my_names]

    versions = {}
    for p in plugins:
        if not p.get("versions"):
            continue
        v = p["versions"][0]
        versions[p["name"]] = [v["name"], v["hash"], v["artifact"]] if v.get("artifact") else [v["name"], v["hash"]]

    write_json(os.path.join(SITE, "plugins", "index.html"), plugins)
    write_json(os.path.join(SITE, "plugins", "versions", "index.html"), versions)
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(
            "<!doctype html><meta charset='utf-8'><title>Decky Store</title>"
            f"<p>Decky Loader store: {len(plugins)} plugins ({len(mine)} custom), updated {stamp}.</p>"
            "<p>In Decky: Settings &rarr; Developer &rarr; Store channel <b>Custom</b>, "
            "URL = this address + <code>/plugins</code></p>"
        )
    print(f"Wrote {len(plugins)} plugins to {SITE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
