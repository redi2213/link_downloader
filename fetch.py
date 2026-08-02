"""
Step 3 (fetch): Given RESOLVED_LINKS (one direct mp4 link per line),
actually download the file(s) and save them to the output folder so the
workflow can upload them to a GitHub Release.
"""

import os
import re
import asyncio
import aiohttp


def safe_filename(url, index):
    name = url.split("/")[-1].split("?")[0]
    name = re.sub(r'[^A-Za-z0-9._-]', '_', name)
    if not name.lower().endswith(".mp4"):
        name += ".mp4"
    if not name or name == ".mp4":
        name = f"video_{index}.mp4"
    return name


async def download_file(session, url, path):
    async with session.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=aiohttp.ClientTimeout(total=None),
    ) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            async for chunk in r.content.iter_chunked(1024 * 1024):
                f.write(chunk)


async def main_async():
    raw = os.environ.get("RESOLVED_LINKS", "")
    urls = [x.strip() for x in raw.splitlines() if x.strip()]

    if not urls:
        print("No links provided (set the RESOLVED_LINKS input).")
        return

    os.makedirs("downloads", exist_ok=True)

    downloaded = []
    failed = []

    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(urls, 1):
            fname = safe_filename(url, i)
            path = os.path.join("downloads", fname)
            print(f"[{i}/{len(urls)}] Downloading: {url}")
            print(f"    -> {path}")
            try:
                await download_file(session, url, path)
                size = os.path.getsize(path)
                print(f"    OK ({size / (1024*1024):.1f} MB)\n")
                downloaded.append(path)
            except Exception as e:
                print(f"    ERROR: {e}\n")
                failed.append(url)

    print("=" * 40)
    print(f"Downloaded {len(downloaded)} file(s), {len(failed)} failed.")

    with open("failed.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(failed))


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
