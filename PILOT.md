# VerityThink blog: Ring-only manual publishing pilot

## What works

**Build archival pilot** reads the private publishing Sheet and the approved Humanitarian Ring Google Doc, imports its article and two embedded images, and deploys this isolated GitHub Pages preview:

https://andrejverity.github.io/veritythink_blog/

It preserves the original date, 14 October 2013, stable ID `64003052404`, wording, links and images. This is an archival test, not a new post. No RSS or email is emitted. The other historical rows and the New posts tab are not published.

## Matching post folders

The private Drive layout is:

```text
Publishing folder/
  verity-think blog posts [Sheet]
  Posts/
    2013-10-14-the-humanitarian-ring/
      Article [Google Doc, with its two embedded images]
    2026-11-22-pilot-test-post/
      Article [Google Doc, labelled pipeline test]
```

The same post folder appears in this public repository after a successful manual publish:

```text
content/posts/2013-10-14-the-humanitarian-ring/
  post.json
  images/
    ring-1.png
    ring-2.png
content/posts/2026-11-22-pilot-test-post/
  post.json   [only after the gated test publish]
```

The Google Doc is the writing source. The repository folder is a generated, public-ready snapshot, not a second place to edit the article. Private source links, IDs, account settings, credentials and notes are not stored there. Keep the folder name stable when changing a headline. No separate Source images folder is needed for this test because both images remain embedded in Article.

## Publish or correct Ring

1. Edit Article below its three pilot header paragraphs. Keep those headers, the original date, stable ID and source link intact.
2. In the Sheet's Redirects tab, set the Ring Migration status to exactly `Publish test`.
3. Open **Actions > Build archival pilot > Run workflow**, select `main`, and run it.
4. Check that build, save_snapshot and deploy succeed. The manual run saves the approved Ring export in its GitHub folder, then deploys the preview. If the snapshot is unchanged, no new snapshot commit is made.
5. Open the preview. Its `build-manifest.json` records the current import time, source version, original date and image hashes without private source identifiers.

A correction uses the same Doc, ID and original date. Set Migration status to `Draft` to pause future updates; this does not withdraw the existing public preview or remove its saved snapshot. Read/validation failures also leave the last successful preview online.

The existing hourly schedule remains configured at minute 37 UTC, but unattended operation has not been verified. Manual Run workflow is the tested route. Only manual runs save snapshots to the repository. Source-code pushes can still build/deploy the Ring test. No timer repair is part of this folder change.

## New-post test (vt-0001)

A clearly labelled test post verifies the new-post path. Its registry row is in the Sheet's New posts tab with Post ID `vt-0001`; its writing Doc is Article inside `Posts/2026-11-22-pilot-test-post`. While the row's Editorial status is not exactly `Publish test`, the post is skipped entirely. When set to `Publish test`, a manual **Run workflow** imports it (fixed title, zero images, the same sanitization and blocked-content rules), saves its `post.json` snapshot, and deploys the preview. The preview index then lists both posts; the test page is at `post/vt-0001/pilot-test-post/`. Editing the Doc and running the workflow again tests a correction. The test post emits no RSS or email, and its RSS/email eligibility must stay `Not eligible`. Ring's gates and checks are unchanged. The test post's internal ID `vt-0001` is permanent and independent of its editable title; its folder name follows the date-first convention and stays fixed once publishing starts.

## Scope and safety

The importer accepts only the configured Sheet, configured Ring Doc, exact archival ID/date/original URL, the gated vt-0001 test post with its fixed identity and folder, and `Publish test` gates. The Sheet stays directly in the approved publishing folder. The Doc may be there during transition or in the exact `Posts/2013-10-14-the-humanitarian-ring` path below it. The importer verifies every folder in that path, rather than allowing arbitrary Drive sources.

Google access remains keyless and read-only, using short-lived credentials restricted to this repository, main branch and exact workflow. No long-lived service-account keys, billing, free trial or broader Google access were added.

The build job has repository read access and Google identity-token access. A separate manual-only save_snapshot job has repository contents write access but no Google identity-token permission or source configuration. It receives only the sanitised three-file Ring artifact, checks its fixed identity and file list, and stages only those files plus removal of the superseded root snapshots and ID-first post folder. It rejects stale requests if main changed after the run started. Its repository token does not start another workflow when it commits the snapshot. A separate Pages job deploys only `_site`; no private raw export is uploaded.

All third-party Actions are pinned to verified commits. The repository and preview are visible to anyone. `noindex,nofollow` and robots.txt discourage indexing but are not access controls.

## Offline build from the saved snapshot

After a successful manual publish:

```sh
cp 1-build.py build.py
python3 build.py
```

Open `_site/index.html` or `_site/post/64003052404/the-humanitarian-ring/index.html`. The saved snapshot is a fallback for this local build, not a replacement for the private Google source during manual publishing.

Live blog, DNS, Publii, Mailchimp, redirects, other repositories and other posts remain unchanged. General new-post publishing and live cutover require separate work and approval.
