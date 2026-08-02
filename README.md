# link_downloader

Three-step MP4 pipeline that runs on GitHub Actions and is triggered
from Termux via the GitHub CLI (gh).

1. List - scan page(s), print available qualities with numbers
2. Resolve - pick a quality number per link, get back the direct MP4 link(s) (no download)
3. Fetch - actually download the file(s) and publish them to a GitHub Release

## Setup (once, in Termux)

    pkg install gh -y
    gh auth login

## Step 1 - List available qualities

    gh workflow run list.yml -R redi2213/link_downloader -f links="LINK1
LINK2"

Check logs:

    gh run list -R redi2213/link_downloader -w list.yml -L 1
    gh run view -R redi2213/link_downloader --log <run-id>

## Step 2 - Resolve chosen qualities

    gh workflow run resolve.yml -R redi2213/link_downloader -f links="LINK1
LINK2" -f choices="1,2"

Check logs:

    gh run list -R redi2213/link_downloader -w resolve.yml -L 1
    gh run view -R redi2213/link_downloader --log <run-id>

## Step 3 - Fetch and upload to Release

    gh workflow run fetch.yml -R redi2213/link_downloader -f resolved_links="DIRECT_MP4_LINK1
DIRECT_MP4_LINK2"

Check logs for Release URL:

    gh run list -R redi2213/link_downloader -w fetch.yml -L 1
    gh run view -R redi2213/link_downloader --log <run-id>

Download the file:

    curl -L -O https://github.com/redi2213/link_downloader/releases/download/run-<id>/video1.mp4
