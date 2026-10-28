#!/usr/bin/env python3
"""
xHamster quality links extractor.
- Interactive (Termux): python xh_links.py
- Actions: URL/LINKS env; tries proxies from PROXY env or working_proxies.txt
"""

import os
import re
import json
import asyncio


def load_proxies() -> list[str]:
    proxies = []
    # 1) single PROXY env
    one = (os.environ.get("PROXY") or "").strip()
    if one:
        proxies.append(one)
    # 2) file produced by Find Free Proxies workflow / local
    for path in ("working_proxies.txt", "proxies.txt"):
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        proxies.append(line)
    # unique keep order
    seen = set()
    out = []
    for p in proxies:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def make_client(proxy: str | None = None):
    from xhamster_api import Client

    if not proxy:
        return Client()

    try:
        from base_api.modules.config import RuntimeConfig
        from base_api.base import BaseCore

        cfg = RuntimeConfig()
        cfg.proxies = {"http": proxy, "https": proxy}
        cfg.trust_env = True
        cfg.impersonation = os.environ.get("IMPERSONATE", "chrome")
        return Client(core=BaseCore(config=cfg))
    except Exception:
        try:
            from base_api.modules.config import config as cfg
            from base_api import BaseCore

            cfg.proxies = {"http": proxy, "https": proxy}
            cfg.trust_env = True
            return Client(core=BaseCore(config=cfg))
        except Exception:
            return Client()


async def process_url(url: str, proxy: str | None = None) -> dict:
    client = make_client(proxy)
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
        "proxy_used": proxy,
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
    if data.get("proxy_used"):
        print(f"Proxy        : {data['proxy_used']}")

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

    print("\nNote: HLS (m3u8). Prefer 1DM+.")
    print("=" * 55)


async def try_with_proxies(url: str, proxies: list[str]) -> dict:
    """Try direct first (optional), then each proxy until one works."""
    chain = []
    # On Actions, direct almost always fails — still try if no proxies
    if not proxies:
        chain = [None]
    else:
        # skip direct on CI to save time unless ALLOW_DIRECT=1
        if os.environ.get("ALLOW_DIRECT", "0") == "1":
            chain.append(None)
        chain.extend(proxies)

    last = None
    for proxy in chain:
        label = proxy or "(direct)"
        print(f"\n>>> Trying {label} ...")
        try:
            data = await process_url(url, proxy)
            if data.get("m3u8") and not data.get("error"):
                return data
            last = data
            print(f"    no m3u8 / error: {data.get('error')}")
        except Exception as e:
            last = {
                "url": url,
                "title": None,
                "max_resolution": None,
                "m3u8": None,
                "qualities": [],
                "error": f"{type(e).__name__}: {e}",
                "proxy_used": proxy,
            }
            print(f"    failed: {type(e).__name__}: {e}")
    return last or {
        "url": url,
        "title": None,
        "max_resolution": None,
        "m3u8": None,
        "qualities": [],
        "error": "all proxies failed",
        "proxy_used": None,
    }


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
        print("No URL provided.")
        return

    proxies = load_proxies()
    print(f"Loaded {len(proxies)} proxy(ies)")
    for p in proxies[:10]:
        print(f"  - {p}")
    if len(proxies) > 10:
        print(f"  ... +{len(proxies) - 10} more")

    print(f"\nProcessing {len(urls)} link(s)...")
    results = []

    for i, url in enumerate(urls, 1):
        data = await try_with_proxies(url, proxies)
        print_result(data, index=i if len(urls) > 1 else None)
        print()
        results.append(data)

    with open("xh_links.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open("xh_links.txt", "w", encoding="utf-8") as f:
        for item in results:
            f.write(f"# {item.get('title') or item['url']}\n")
            if item.get("proxy_used"):
                f.write(f"# proxy: {item['proxy_used']}\n")
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
