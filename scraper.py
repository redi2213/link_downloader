"""
Core scraping logic - shared by list_qualities.py, resolve.py, fetch.py
No input() calls here - everything is passed as arguments.
"""

import re
import asyncio
import aiohttp


def clean_url(url):
    if ',' in url:
        url = url.split(',')[0]
    return url.strip()


def extract_mp4_links(text):
    links = re.findall(
        r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*',
        text
    )
    return list(dict.fromkeys(clean_url(x) for x in links))


def get_quality(link):
    q = re.search(r'(\d{3,4}p)', link.lower())
    if q:
        return q.group(1)
    if "original" in link.lower():
        return "original"
    return "unknown"


def group_by_quality(mp4_links):
    """Returns an ordered dict: {quality: link}, first occurrence wins."""
    qualities = {}
    for link in mp4_links:
        q = get_quality(link)
        if q not in qualities:
            qualities[q] = link
    return qualities


async def fetch_page(session, url):
    async with session.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as r:
        return await r.text()


async def scan_url(url):
    """Fetch a single URL and return its {quality: link} dict."""
    async with aiohttp.ClientSession() as session:
        text = await fetch_page(session, url)
        mp4s = extract_mp4_links(text)
        return group_by_quality(mp4s)


async def scan_urls(urls):
    """Fetch multiple URLs, return list of (url, {quality: link} or None)."""
    results = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                text = await fetch_page(session, url)
                mp4s = extract_mp4_links(text)
                results.append((url, group_by_quality(mp4s)))
            except Exception as e:
                results.append((url, {"__error__": str(e)}))
    return results
