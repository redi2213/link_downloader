#!/usr/bin/env python3
"""
xHamster quality links extractor.
Uses working_proxies.txt from repo (or PROXY env).
Writes human output + GitHub Step Summary (no zip needed).
"""

from __future__ import annotations

import os
import re
import json
import asyncio


def _compat_base_api() -> None:
    try:
        import base_api.base as b

        if not hasattr(b, "setup_logger") and hasattr(b, "get_logger"):
            b.setup_logger = b.get_logger  # type: ignore[attr-defined]
        if not hasattr(b, "Helper"):
            try:
                from base_api import Helper as H  # type: ignore

                b.Helper = H  # type: ignore[attr-defined]
            except Exception:
                pass
    except Exception:
        pass


_compat_base_api()


def load_proxies() -> list[str]:
    proxies: list[str] = []
    one = (os.environ.get("PROXY") or "").strip()
    if one:
        proxies.append(one)
    for path in ("working_proxies.txt", "proxies.txt"):
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                proxies.append(line)
    seen: set[str] = set()
    out: list[str] = []
    for p in proxies:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def apply_proxy_env(proxy: str | None) -> None:
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(k, None)
    if not proxy:
        return
    os.environ["HTTP_PROXY"] = proxy
    os.environ["HTTPS_PROXY"] = proxy
    os.environ["ALL_PROXY"] = proxy
    os.environ["http_proxy"] = proxy
    os.environ["https_proxy"] = proxy
    os.environ["all_proxy"] = proxy


def make_client(proxy: str | None = None):
    apply_proxy_env(proxy)
    _compat_base_api()
    from xhamster_api import Client

    if not proxy:
        return Client()

    try:
        from base_api.modules.config import config as cfg  # type: ignore

        cfg.proxies = {"http": proxy, "https": proxy}
        cfg.trust_env = True
        try:
            cfg.impersonation = os.environ.get("IMPERSONATE", "chrome")
        except Exception:
            pass
        try:
            from base_api import BaseCore  # type: ignore

            return Client(core=BaseCore(config=cfg))
        except Exception:
            return Client()
    except Exception as e:
        print(f"  (base_api config skipped: {type(e).__name__}: {e})")
        return Client()


async def process_url(url: str, proxy: str | None = None) -> dict:
    client = make_client(proxy)
    video = await client.get_video(url)

    title = getattr(video, "title", None) or "unknown"
    max_res = getattr(video, "max_resolution", None)
    m3u8 = getattr(video, "m3u8_base_url", None)
    if not m3u8:
        m3u8 = getattr(video, "m3u8", None) or getattr(video, "hls", None)

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

    matches = re.findall(r"(\d+x\d+):(\d+p)", str(m3u8))
    for resolution, quality in matches:
        link = str(m3u8).replace("_TPL_", quality)
        result["qualities"].append(
            {"quality": quality, "resolution": resolution, "link": link}
        )
    return result


def print_result(data: dict, index: int | None = None) -> None:
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
    print("=" * 55)


def write_summary(results: list[dict]) -> None:
    """GitHub Actions Job Summary — visible on the run page, no zip."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return

    lines: list[str] = []
    lines.append("# XHamster Links")
    lines.append("")

    ok = 0
    for i, item in enumerate(results, 1):
        title = item.get("title") or "(no title)"
        lines.append(f"## {i}. {title}")
        lines.append(f"- URL: `{item.get('url')}`")
        if item.get("proxy_used"):
            lines.append(f"- Proxy: `{item['proxy_used']}`")
        if item.get("error"):
            lines.append(f"- **ERROR:** `{item['error']}`")
            lines.append("")
            continue
        ok += 1
        if item.get("m3u8"):
            lines.append("- Master m3u8:")
            lines.append("```")
            lines.append(str(item["m3u8"]))
            lines.append("```")
        quals = item.get("qualities") or []
        if quals:
            lines.append("- Quality links:")
            for q in quals:
                lines.append(f"  - **{q['quality']}** ({q['resolution']})")
                lines.append(f"    ```")
                lines.append(f"    {q['link']}")
                lines.append(f"    ```")
        lines.append("")

    lines.append("---")
    lines.append(f"**Success:** {ok}/{len(results)}")
    if ok == 0:
        lines.append("")
        lines.append(
            "> Free public proxies are usually **datacenter** IPs. "
            "xHamster often blocks them (same as GitHub Actions IPs). "
            "For reliable results use **Termux on your phone** without proxy."
        )

    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


async def try_with_proxies(url: str, proxies: list[str]) -> dict:
    chain: list[str | None] = []
    if not proxies:
        chain = [None]
    else:
        if os.environ.get("ALLOW_DIRECT", "0") == "1":
            chain.append(None)
        chain.extend(proxies)

    last: dict | None = None
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


async def main() -> None:
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
    for p in proxies[:15]:
        print(f"  - {p}")

    print(f"\nProcessing {len(urls)} link(s)...")
    results = []

    for i, url in enumerate(urls, 1):
        data = await try_with_proxies(url, proxies)
        print_result(data, index=i if len(urls) > 1 else None)
        print()
        results.append(data)

    with open("xh_links.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    txt_lines: list[str] = []
    for item in results:
        txt_lines.append(f"# {item.get('title') or item['url']}")
        if item.get("proxy_used"):
            txt_lines.append(f"# proxy: {item['proxy_used']}")
        if item.get("error"):
            txt_lines.append(f"# ERROR: {item['error']}")
            txt_lines.append("")
            continue
        if item.get("m3u8"):
            txt_lines.append(f"# master: {item['m3u8']}")
        for q in item.get("qualities") or []:
            txt_lines.append(q["link"])
        txt_lines.append("")

    text = "\n".join(txt_lines) + "\n"
    with open("xh_links.txt", "w", encoding="utf-8") as f:
        f.write(text)

    write_summary(results)

    # Always dump plain text at end of log for easy copy
    print("\n" + "#" * 60)
    print("# COPY BELOW (also in Job Summary on the run page)")
    print("#" * 60)
    print(text)


if __name__ == "__main__":
    asyncio.run(main())
