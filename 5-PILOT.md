# VerityThink blog: isolated migration pilot

## What this proves

This repository builds a static test copy of **The Humanitarian Ring**, originally published on 14 October 2013. `ring.json` is a sanitized snapshot exported from the authoring Google Doc. Both images are copied into this repository. Private source links and credentials are not included.

Run locally with Python 3:

```sh
python build.py
```

Open `_site/index.html`, or the generated original-path test page under `_site/post/64003052404/the-humanitarian-ring/`.

The **Build archival pilot** GitHub Actions workflow runs the same build and retains its output as a downloadable artifact. It has read-only repository permissions. It does not deploy a website, change DNS, publish RSS, contact Mailchimp, or modify Google files.

## Important boundary

This is a **Google Doc snapshot → Actions build** pilot, not yet an unattended connection to Google. Editing the private Google Doc or spreadsheet will not change the next build until an authenticated importer is configured. No polling is active.

The next stage needs a separate, explicitly approved Google access setup. Preferred design: a dedicated read-only Google service account, shared only into the publishing folder, authenticated through keyless GitHub Workload Identity Federation restricted to this repository and its main branch. No account-wide OAuth token or long-lived service-account key should be committed.

Before activating an importer, it must validate document membership in the approved folder, obey an explicit publish/update status, preserve stable IDs and original dates, copy images locally, and keep legacy migration posts out of new-post email distribution. Draft and test rows must never become eligible just because they exist.

## Safety checks

The build verifies the archival ID/date, exactly two local images, no embedded data-image URLs, no scripts in the article, no private Google links, and no emitted XML feed. It creates a build manifest with image hashes. The test page includes `noindex,nofollow`; this is a search-engine request, not an access control. This repository is public.

Live blog, DNS, Publii, other repositories and Mailchimp are unchanged. GitHub Pages is not enabled by this workflow.
