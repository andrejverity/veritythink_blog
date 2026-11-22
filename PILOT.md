# VerityThink blog: isolated migration pilot

## What this proves

This repository builds a static test copy of **The Humanitarian Ring**, originally published on 14 October 2013. `2-ring.json` is a sanitized snapshot exported from the authoring Google Doc. Both images are copied into this repository. Private source links and credentials are not included.

Run locally with Python 3:

```sh
cp 1-build.py build.py
cp 2-ring.json ring.json
cp 3-ring-1.png ring-1.png
cp 4-ring-2.png ring-2.png
python3 build.py
```

Open `_site/index.html`, or the generated original-path test page under `_site/post/64003052404/the-humanitarian-ring/`.

The **Build archival pilot** GitHub Actions workflow runs the same build and retains its output as a downloadable artifact. The build job has read-only repository permissions. A separate deploy job has only Pages deployment permissions and deploys the test to GitHub Pages. Neither job changes DNS, publishes RSS, contacts Mailchimp, or modifies Google files.

## Important boundary

This is a **Google Doc snapshot → Actions build** pilot, not yet an unattended connection to Google. Editing the private Google Doc or spreadsheet will not change the next build until an authenticated importer is configured. No polling is active.

The next stage needs a separate, explicitly approved Google access setup. Preferred design: a dedicated read-only Google service account, shared only into the publishing folder, authenticated through keyless GitHub Workload Identity Federation restricted to this repository and its main branch. No account-wide OAuth token or long-lived service-account key should be committed.

Before activating an importer, it must validate document membership in the approved folder, obey an explicit publish/update status, preserve stable IDs and original dates, copy images locally, and keep legacy migration posts out of new-post email distribution. Draft and test rows must never become eligible just because they exist.

## Safety checks

The build verifies the archival ID/date, exactly two local images, no embedded data-image URLs, no scripts in the article, no private Google links, and no emitted XML feed. It creates a build manifest with image hashes. The test page includes `noindex,nofollow`; this is a search-engine request, not an access control. This repository is public.

Live blog, DNS, Publii, other repositories and Mailchimp are unchanged. The owner enabled GitHub Pages with GitHub Actions as its source. The isolated preview is https://andrejverity.github.io/veritythink_blog/ .
