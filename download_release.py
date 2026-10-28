#!/usr/bin/env python3
"""
Download videos from xh_links.json on the SAME runner/proxy that extracted them,
then publish to a GitHub Release (so user can download without Termux).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def safe_name(title: str, idx: int) -> str:
    t = re.sub(r"[^\w\s\-.؀-\u06FF]+", "", title or "video", flags=re.U)
    t = re.sub(r"\s+", "_", t).strip("._")[:80] or "video"
    return f"{idx:02d}_{t}"


def height_from_quality(q: str | None) -> int | None:
    if not q:
        return None
    m = re.search(r"(\d{3,4})", str(q))
    return int(m.group(1)) if m else None


def pick_format(quality_pref: str) -> str:
    """yt-dlp -f expression."""
    pref = (quality_pref or "best").strip().lower()
    if pref in ("best", "max", ""):
        # prefer progressive mp4, else best video+audio / best
        return "best[ext=mp4]/best[protocol^=m3u8]/best"
    h = height_from_quality(pref)
    if h:
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
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        "--retries", "5",
        "--fragment-retries", "5",
        url,
    ]
    if proxy:
        cmd[1:1] = ["--proxy", proxy]

    print("Running:", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(p.stdout or "")
    sys.stderr.write(p.stderr or "")
    if p.returncode != 0:
        print(f"yt-dlp failed for {url}")
        return None

    # find produced file
    candidates = sorted(out_dir.glob(f"{base}.*"), key=lambda x: x.stat().st_size, reverse=True)
    candidates = [c for c in candidates if c.suffix.lower() in {".mp4", ".mkv", ".webm", ".ts"}]
    if not candidates:
        print("No output file found")
        return None
    path = candidates[0]
    print(f"Downloaded: {path} ({path.stat().st_size} bytes)")
    return path


def main() -> int:
    quality = os.environ.get("QUALITY", "best")
    do_upload = os.environ.get("UPLOAD", "false").lower() in {"1", "true", "yes"}
    if not do_upload:
        print("UPLOAD=false — skip download/release")
        return 0

    data_path = Path("xh_links.json")
    if not data_path.is_file():
        print("xh_links.json missing")
        return 1

    results = json.loads(data_path.read_text(encoding="utf-8"))
    ok_items = []
    for i, item in enumerate(results, 1):
        if item.get("error") and not (item.get("qualities") or item.get("m3u8")):
            continue
        item = dict(item)
        item["_idx"] = i
        ok_items.append(item)

    if not ok_items:
        print("Nothing to download")
        return 1

    out_dir = Path("downloads")
    out_dir.mkdir(exist_ok=True)
    files: list[Path] = []
    for item in ok_items:
        if item.get("error") and not item.get("url"):
            continue
        # always download from page URL with same proxy (fresh signed CDN URLs)
        f = download_one(item, out_dir, quality)
        if f:
            files.append(f)

    if not files:
        print("All downloads failed")
        Path("download_failed").write_text("1", encoding="utf-8")
        return 1

    # list for shell
    list_path = Path("downloaded_files.txt")
    list_path.write_text("\n".join(str(f) for f in files) + "\n", encoding="utf-8")
    print("Saved list:", list_path)

    # GitHub release
    tag = f"xh-{os.environ.get('GITHUB_RUN_ID', 'local')}"
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not token or not repo:
        print("No GH token/repo — files left in downloads/")
        return 0

    title = f"xHamster {ok_items[0].get('title') or tag}"
    notes_lines = [
        f"Downloaded on Actions (same proxy as extract).",
        f"Quality pref: {quality}",
        "",
    ]
    for item in ok_items:
        notes_lines.append(f"- {item.get('title') or item.get('url')}")
        notes_lines.append(f"  {item.get('url')}")
        if item.get("proxy_used"):
            notes_lines.append(f"  proxy: {item['proxy_used']}")
    notes = "\n".join(notes_lines)
    Path("release_notes.md").write_text(notes, encoding="utf-8")

    env = os.environ.copy()
    env["GH_TOKEN"] = token

    # delete existing tag/release if re-run same id unlikely; create new
    subprocess.run(["gh", "release", "delete", tag, "--yes", "--repo", repo], env=env, capture_output=True)
    subprocess.run(["git", "push", "--delete", "origin", tag], capture_output=True)

    cmd = [
        "gh", "release", "create", tag,
        "--repo", repo,
        "--prerelease",
        "--title", title[:100],
        "--notes-file", "release_notes.md",
    ] + [str(f) for f in files]
    print("Creating release:", tag)
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    sys.stdout.write(p.stdout or "")
    sys.stderr.write(p.stderr or "")
    if p.returncode != 0:
        print("gh release create failed")
        return 1

    release_url = f"https://github.com/{repo}/releases/tag/{tag}"
    print("RELEASE_URL=", release_url)
    Path("release_url.txt").write_text(release_url + "\n", encoding="utf-8")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n## Download & Release\n\n")
            f.write(f"- **Release:** {release_url}\n")
            for path in files:
                f.write(f"- Asset: `{path.name}` ({path.stat().st_size // (1024*1024)} MB)\n")
            f.write("\nFiles were downloaded **on this runner** with the same proxy, so CDN IP binding is OK.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
