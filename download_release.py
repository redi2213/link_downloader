#!/usr/bin/env python3
"""Download from page URL with same proxy, upload GitHub Release."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def safe_name(title: str, idx: int) -> str:
    t = re.sub(r"[^\w\s\-.]+", "", title or "video")
    t = re.sub(r"\s+", "_", t).strip("._")[:80] or "video"
    return f"{idx:02d}_{t}"


def pick_format(quality_pref: str) -> str:
    pref = (quality_pref or "best").strip().lower()
    if pref in ("best", "max", ""):
        return "best[ext=mp4]/best[protocol^=m3u8]/best"
    m = re.search(r"(\d{3,4})", pref)
    if m:
        h = m.group(1)
        return (
            f"best[height<={h}][ext=mp4]/"
            f"best[height<={h}][protocol^=m3u8]/"
            f"best[height<={h}]/best"
        )
    return "best[ext=mp4]/best"


def download_one(item: dict, out_dir: Path, quality_pref: str) -> Path | None:
    url = item.get("url")
    if not url:
        return None
    proxy = item.get("proxy_used") or os.environ.get("PROXY") or ""
    title = item.get("title") or "video"
    idx = item.get("_idx", 1)
    base = safe_name(title, idx)
    out_tmpl = str(out_dir / f"{base}.%(ext)s")
    fmt = pick_format(quality_pref)
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "-f",
        fmt,
        "--merge-output-format",
        "mp4",
        "-o",
        out_tmpl,
        "--retries",
        "5",
        "--fragment-retries",
        "5",
        url,
    ]
    if proxy:
        cmd[1:1] = ["--proxy", proxy]
    print("Running:", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(p.stdout or "")
    sys.stderr.write(p.stderr or "")
    if p.returncode != 0:
        print("yt-dlp failed")
        return None
    candidates = sorted(
        out_dir.glob(f"{base}.*"), key=lambda x: x.stat().st_size, reverse=True
    )
    candidates = [c for c in candidates if c.suffix.lower() in {".mp4", ".mkv", ".webm", ".ts"}]
    if not candidates:
        return None
    print(f"Downloaded: {candidates[0]} ({candidates[0].stat().st_size} bytes)")
    return candidates[0]


def main() -> int:
    if os.environ.get("UPLOAD", "false").lower() not in {"1", "true", "yes"}:
        print("UPLOAD=false")
        return 0
    data_path = Path("xh_links.json")
    if not data_path.is_file():
        print("xh_links.json missing")
        return 1
    results = json.loads(data_path.read_text(encoding="utf-8"))
    ok_items = []
    for i, item in enumerate(results, 1):
        if item.get("error") and not item.get("url"):
            continue
        it = dict(item)
        it["_idx"] = i
        ok_items.append(it)
    if not ok_items:
        print("Nothing to download")
        return 1

    quality = os.environ.get("QUALITY", "best")
    out_dir = Path("downloads")
    out_dir.mkdir(exist_ok=True)
    files = []
    for item in ok_items:
        f = download_one(item, out_dir, quality)
        if f:
            files.append(f)
    if not files:
        print("All downloads failed")
        return 1

    tag = f"xh-{os.environ.get('GITHUB_RUN_ID', 'local')}"
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not token or not repo:
        print("No token — files in downloads/")
        return 0

    notes = ["Downloaded on Actions with same proxy as extract.", f"Quality: {quality}", ""]
    for item in ok_items:
        notes.append(f"- {item.get('title') or item.get('url')}")
        notes.append(f"  {item.get('url')}")
    Path("release_notes.md").write_text("\n".join(notes), encoding="utf-8")

    env = os.environ.copy()
    env["GH_TOKEN"] = token
    title = f"xHamster {ok_items[0].get('title') or tag}"[:100]
    subprocess.run(["gh", "release", "delete", tag, "--yes", "--repo", repo], env=env, capture_output=True)
    cmd = [
        "gh",
        "release",
        "create",
        tag,
        "--repo",
        repo,
        "--prerelease",
        "--title",
        title,
        "--notes-file",
        "release_notes.md",
    ] + [str(f) for f in files]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    sys.stdout.write(p.stdout or "")
    sys.stderr.write(p.stderr or "")
    if p.returncode != 0:
        return 1
    release_url = f"https://github.com/{repo}/releases/tag/{tag}"
    print("RELEASE_URL=", release_url)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n## Download & Release\n\n")
            fh.write(f"- **Release:** {release_url}\n")
            for path in files:
                mb = path.stat().st_size // (1024 * 1024)
                fh.write(f"- `{path.name}` ({mb} MB)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
