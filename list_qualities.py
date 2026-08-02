"""
Step 1: Scan URLs and print available qualities, numbered.
Reads links from the LINKS environment variable (one per line).
Writes a machine-readable map to qualities.json so step 2 can reuse it
without re-scraping.
"""

import os
import json
import asyncio
from scraper import scan_urls


def main():
    raw = os.environ.get("LINKS", "")
    urls = [x.strip() for x in raw.splitlines() if x.strip()]

    if not urls:
        print("No links provided (set the LINKS input).")
        return

    print(f"Scanning {len(urls)} link(s)...\n")

    results = asyncio.run(scan_urls(urls))

    manifest = []

    for i, (url, qualities) in enumerate(results, 1):
        print(f"[{i}] {url}")

        if "__error__" in qualities:
            print(f"    ERROR: {qualities['__error__']}\n")
            manifest.append({"url": url, "qualities": {}, "error": qualities["__error__"]})
            continue

        if not qualities:
            print("    No MP4 found\n")
            manifest.append({"url": url, "qualities": {}})
            continue

        items = list(qualities.items())
        for n, (q, link) in enumerate(items, 1):
            print(f"    {n}. {q}  ->  {link}")
        print()

        manifest.append({
            "url": url,
            "qualities": [{"index": n, "quality": q, "link": link}
                           for n, (q, link) in enumerate(items, 1)]
        })

    with open("qualities.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("=" * 40)
    print("Saved qualities.json")
    print("Now run the Resolve workflow, giving for each link")
    print("the quality NUMBER shown above (e.g. '1,2,1' for 3 links).")


if __name__ == "__main__":
    main()
