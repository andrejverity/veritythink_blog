# VerityThink blog: isolated migration pilot

## What works

The **Build archival pilot** workflow reads the private publishing spreadsheet and the approved **Humanitarian Ring** Google Doc, copies both embedded images, builds a static page, and deploys only this repository's GitHub Pages preview:

https://andrejverity.github.io/veritythink_blog/

The original article date, 14 October 2013, and stable post ID, `64003052404`, remain unchanged. This is an archival test, not a new post.

## Editing and publishing the test

1. Edit the article body in the Ring Google Doc, below its three pilot header paragraphs. Keep those header paragraphs in place.
2. In the spreadsheet's **Redirects** tab, set the Ring row's **Migration status** to exactly `Publish test`.
3. GitHub Actions checks hourly, at minute 17 UTC. GitHub may queue or delay scheduled runs. For an immediate request, open **Actions → Build archival pilot → Run workflow**, use `main`, and run it.
4. Check the completed workflow and preview. `build-manifest.json` records the source version, import time, original date, and image hashes, without private source identifiers.

GitHub can delay scheduled runs and can automatically disable them after 60 days without repository activity. Editing a Google Doc does not create a repository commit. If the schedule is disabled, re-enable it in Actions before relying on hourly checks. This pilot is not a guaranteed real-time or maintenance-free production publisher. GitHub documents this behavior at https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows .

Set the status to `Draft`, or any value other than `Publish test`, to pause future updates. Pausing does **not** remove the already-published preview. Source access errors or validation failures also leave the last successful preview unchanged.

Only the one approved Ring row and its configured Doc can publish. The other historical rows and the **New posts** tab are not published by this pilot. The importer refuses changes to the archival ID, original URL, date, configured source, or folder membership. This is not yet a general new-post publishing system.

## Private access and deployment

Google access uses keyless Workload Identity Federation and a dedicated read-only service account. Admission is restricted to this repository's immutable ID, its owner's immutable ID, the `main` branch, and this exact workflow file. The identity has no project resource roles, no long-lived keys, and Reader access only through the approved publishing folder.

Source identifiers and connection settings are encrypted repository Actions secrets, not public files. Each build requests a short-lived token with only Drive and Sheets read scopes. No credentials file is created. Raw source data and tokens are not uploaded. The importer writes only sanitized article data and local images for the static builder.

The build has repository read permission and permission to request its identity token. A separate deploy job has Pages deployment permissions. Neither job changes Google files, DNS, RSS, Mailchimp, Publii, or any other repository.

All third-party Actions are pinned to verified commit IDs. Routine checks use standard public-repository runners. No Google billing account, free trial, paid resource, or quota increase was enabled for this pilot.

## Safety checks

The importer validates that the Doc and Sheet are active files in the approved folder. It requires exactly one approved archival row, preserves the original date and ID, strips the private pilot header, copies exactly two embedded PNG images, and rejects unsafe or private Google links.

The builder verifies two local images, no scripts, no embedded data-image URLs, no private Google links, and no XML feed. It creates the root preview and an original-path test page. Search-engine indexing is discouraged with `noindex,nofollow` and `robots.txt`; these are requests, not access controls. This repository and the preview are public.

## Offline snapshot fallback

The originally approved static snapshot remains in the repository for a local, offline build. It is not the input to the automated Google workflow:

```sh
cp 1-build.py build.py
cp 2-ring.json ring.json
cp 3-ring-1.png ring-1.png
cp 4-ring-2.png ring-2.png
python3 build.py
```

Open `_site/index.html`, or `_site/post/64003052404/the-humanitarian-ring/index.html`.

Live blog, DNS, Publii, Mailchimp, and other repositories remain unchanged. The preview emits no RSS and sends no email.
