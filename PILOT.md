# VerityThink blog: archive publishing pipeline

## What this does

**Build blog preview** reads the private publishing Sheet and the per-post Google Docs, imports every gated post, and deploys the full archive to an isolated GitHub Pages preview:

https://andrejverity.github.io/veritythink_blog/

All 104 original posts are live on the preview with their original dates, wording, links and images. Each post gets a canonical date-first URL `/post/YYYY-MM-DD-slug/`, and every old Tumblr URL (`/post/<id>/` and `/post/<id>/<slug>/`) serves a redirect stub page. A full-post `feed.xml` is regenerated at each publish. Post-to-post (previous/next) and top navigation to the main VerityThink site are built in; the top links are configured from the Sheet's Site tab.

This is still a preview: every page carries a preview banner and `noindex`, and the live blog, its domain, DNS and Mailchimp are untouched. The redirect stubs are browser redirects (meta refresh), because GitHub Pages cannot send server 301s. Real redirects arrive only at cutover.

## Source layout (private)

```text
Publishing folder/
  verity-think blog posts [Sheet: Redirects, New posts, Site, Guide tabs]
  Posts/
    2013-10-14-the-humanitarian-ring/
      Article [Google Doc, images embedded]
      ring-1.png, ring-2.png [source images]
    2015-03-14-time-to-cut-the-creative-red-tape/
      Article
      image-1.png ... image-6.png
    ... one date-first folder per post, 104 in total ...
    2026-11-22-pilot-test-post/
      Article [Google Doc, labelled pipeline test]
```

The public repository mirrors each published post:

```text
content/posts/<date-first folder>/
  post.json
  images/
    image-1.png ...
content/site.json        [from the Sheet's Site tab]
```

The Google Doc is the writing source. The repository folder is a generated, public-ready snapshot, not a second place to edit. Private source links, IDs, account settings, credentials and notes are never stored there: the importer and builder both block the Sheet ID, the Posts folder ID and every source Doc ID from public output. Keep folder names stable when changing headlines.

## Publishing a correction or new import

1. Edit the post's Article Doc below its three header paragraphs (title, `Original post: <date>`, `Original blog post` link). Keep those headers intact.
2. In the Sheet's Redirects tab, the row's Migration status must be `Publish` or `Published` (`Publish test` for the Ring pilot row). `Doc created` means the source is ready but not yet queued. Any other value, such as `Draft`, skips the post.
3. Open **Actions > Build blog preview > Run workflow**, select `main`, and run it.
4. The workflow imports all gated rows (about 2-3 minutes), validates the build, saves the approved snapshots to `content/`, and deploys. A failed run leaves the last successful preview online.
5. The Sheet is never written by the workflow: Google access from Actions is keyless and read-only. Status changes (for example marking rows `Published`) are made by people or by Instinct's own tools.

There is no automatic schedule: the hourly timer was removed. Run the workflow manually when you want to publish.

## Redirect stubs

Each published post creates two stub pages mapping its old Tumblr URLs to the canonical one. They are HTML meta-refresh pages labelled as preview redirects. During cutover, the same mapping drives real server-side redirects on the live domain; until then, old URLs on the live blog keep working as they are.

## RSS

`feed.xml` lists archive posts with their original dates and stable IDs, newest first. It is rebuilt on every publish, so corrections flow through. The vt-0001 test post never appears in the feed. No email is sent anywhere in this pipeline.

## New-post test (vt-0001)

A clearly labelled test post verifies the new-post path. Its registry row is in the Sheet's New posts tab with Post ID `vt-0001`; its writing Doc is Article inside `Posts/2026-11-22-pilot-test-post`. While the row's Editorial status is not exactly `Publish test`, the post is skipped entirely. When set to `Publish test`, a manual **Run workflow** imports it (fixed identity, the same sanitization and blocked-content rules), saves its snapshot, and deploys. The page lives at `post/vt-0001/pilot-test-post/` but is excluded from the index, post navigation and RSS. Its internal ID `vt-0001` is permanent and independent of its editable title.

## Site tab

The Sheet's Site tab controls preview chrome without code changes: `nav_1`/`nav_2` (top-right links), `rss_enabled`, and `preview_banner` text. The next build picks up changes.

## Scope and safety

The importer accepts only the configured Sheet, source Docs inside verified `Posts/<date-first folder>` paths, registry rows whose identity (original URL, Tumblr ID, date) matches, and the gated vt-0001 test post. Article HTML is sanitized to a small tag allowlist; embedded images are verified by content; scripts, iframes and forms never pass. Legacy posts keep their original outbound links, including old public links to Google-hosted documents, exactly as published on the original blog.

Google access remains keyless and read-only, using short-lived credentials restricted to this repository, main branch and exact workflow. No long-lived service-account keys, billing, free trial or broader Google access were added.
