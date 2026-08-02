"""
Step 2 (resolve only): Given LINKS (one per line) and CHOICES
(comma-separated quality numbers matching the order printed by
list_qualities.py), re-scan and print the chosen mp4 link for each URL.
Writes resolved.txt with just the final links (no download, no upload).
"""

import os
import asyncio
from scraper import scan_urls


def main():
    raw_links = os.environ.get("LINKS", "")
    raw_choices = os.environ.get("CHOICES", "")

    urls = [x.strip() for x in raw_links.splitlines() if x.strip()]
    choices = [x.strip() for x in raw_choices.split(",") if x.strip()]

    if not urls:
        print("No links provided (set the LINKS input).")
        return

    if len(choices) != len(urls):
        print(f"ERROR: got {len(urls)} link(s) but {len(choices)} choice(s). "
              f"CHOICES must have exactly one number per link, comma-separated.")
        return

    print(f"Re-scanning {len(urls)} link(s) to resolve chosen quality...\n")
    results = asyncio.run(scan_urls(urls))

    resolved = []
    failed = []

    for (url, qualities), choice in zip(results, choices):
        print(f"URL: {url}")

        if "__error__" in qualities:
            print(f"    ERROR scanning: {qualities['__error__']}\n")
            failed.append(url)
            continue

        if not qualities:
            print("    No MP4 found\n")
            failed.append(url)
            continue

        items = list(qualities.items())

        try:
            idx = int(choice)
            if idx < 1 or idx > len(items):
                raise ValueError
        except ValueError:
            print(f"    Invalid choice '{choice}' (valid range 1-{len(items)})\n")
            failed.append(url)
            continue

        quality, link = items[idx - 1]
        print(f"    Chosen: {quality}")
        print(f"    LINK: {link}\n")
        resolved.append(link)

    with open("resolved.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(resolved))

    with open("failed.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(failed))

    print("=" * 40)
    print(f"Resolved {len(resolved)} link(s), {len(failed)} failed.")
    print()
    print("FINAL MP4 LINKS:")
    for link in resolved:
        print(link)
    print()
    print("If you want the actual file downloaded and uploaded to a")
    print("Release, run the 'Fetch' workflow with these link(s) as input.")


if __name__ == "__main__":
    main()
