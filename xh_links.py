#!/usr/bin/env python3
"""
xHamster quality links extractor.
- Interactive (Termux): python xh_links.py
- GitHub Actions: set URL or LINKS; optional PROXY secret for datacenter IP blocks
"""

import os
import re
import json
import asyncio


def make_client():
    """Build Client with optional proxy from env PROXY / HTTP_PROXY / HTTPS_PROXY."""
    from xhamster_api import Client

    proxy = (
        os.environ.get("PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or ""
    ).strip()

    if not proxy:
        return Client()

    try:
        from base_api.modules.config import RuntimeConfig
        from base_api.base import BaseCore
    except ImportError:
        try:
            from base_api.modules.config import config as cfg
            from base_api import BaseCore
            cfg.proxies = {"http": proxy, "https": proxy}
            cfg.trust_env = True
            return Client(core=BaseCore(config=cfg))
        except Exception:
            return Client()

    cfg = RuntimeConfig()
    cfg.proxies = {"http": proxy, "https": proxy}
    cfg.trust_env = True
    # Better chance against bot checks from cloud IPs
    cfg.impersonation = os.environ.get("IMPERSONATE", "chrome")
    core = BaseCore(config=cfg)
    return Client(core=core)


async def process_url(url: str) -> dict:
    client = make_client()
    video = await client.get_video(url)

    title = getattr(video, "title", None) or "unknown"
    max_res = getattr(video, "max_resolution", None)
    m3u8 = getattr(video, "m3u8_base_url", None)

    result = {
        "url": url,
        "title": title,
        "max_resolution": max_res,
        "m3u8": m3u8,
        "qualities": [],
        "error": None,
    }

    if not m3u8:
        result["error"] = "m3u8 not found"
        return result

    matches = re.findall(r"(\d+x\d+):(\d+p)", m3u8)
    for resolution, quality in matches:
        link = m3u8.replace("_TPL_", quality)
        result["qualities"].append({
            "quality": quality,
            "resolution": resolution,
            "link": link,
        })

    return result


def print_result(data: dict, index: int | None = None):
    prefix = f"[{index}] " if index is not None else ""
    print("=" * 55)
    print(f"{prefix}{data.get('title', 'unknown')}")
    print("=" * 55)
    print(f"URL          : {data['url']}")
    print(f"Max quality  : {data.get('max_resolution') or 'unknown'}")

    if data.get("error"):
        print(f"ERROR        : {data['error']}")
        return

    if data.get("m3u8"):
        print(f"\nMaster m3u8:\n{data['m3u8']}")

    qualities = data.get("qualities") or []
    if qualities:
        print("\nQuality links:")
        for i, q in enumerate(qualities, 1):
            print(f"\n  {i}. [{q['quality']}] {q['resolution']}")
            print(f"     {q['link']}")
    else:
        print("\nCould not split qualities; use master m3u8 above.")

    print("\nNote: these are HLS (m3u8) links. Use 1DM+ or similar.")
    print("=" * 55)


async def main():
    raw = os.environ.get("URL") or os.environ.get("LINKS") or ""
    urls = [x.strip() for x in raw.splitlines() if x.strip()]

    if not urls:
        try:
            u = input("\nلینک ویدیو را وارد کن:\n> ").strip()
            if u:
                urls = [u]
        except EOFError:
            pass

    if not urls:
        print("No URL provided. Set URL/LINKS env or pass interactively.")
        return

    proxy = (
        os.environ.get("PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or ""
    ).strip()
    if proxy:
        # mask credentials in logs
        safe = re.sub(r":([^:@/]+)@", ":***@", proxy)
        print(f"Using proxy: {safe}")
    else:
        print("No proxy set (GitHub Actions IPs are often blocked by xHamster).")

    print(f"Processing {len(urls)} link(s)...\n")
    results = []

    for i, url in enumerate(urls, 1):
        try:
            data = await process_url(url)
        except Exception as e:
            data = {
                "url": url,
                "title": None,
                "max_resolution": None,
                "m3u8": None,
                "qualities": [],
                "error": f"{type(e).__name__}: {e}",
            }
        print_result(data, index=i if len(urls) > 1 else None)
        print()
        results.append(data)

    with open("xh_links.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open("xh_links.txt", "w", encoding="utf-8") as f:
        for item in results:
            f.write(f"# {item.get('title') or item['url']}\n")
            if item.get("error"):
                f.write(f"# ERROR: {item['error']}\n\n")
                continue
            if item.get("m3u8"):
                f.write(f"# master: {item['m3u8']}\n")
            for q in item.get("qualities") or []:
                f.write(f"{q['link']}\n")
            f.write("\n")

    print("Saved: xh_links.json  and  xh_links.txt")


if __name__ == "__main__":
    asyncio.run(main())
