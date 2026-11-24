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

There is no hourly schedule. A manual Run workflow reads fresh Docs, builds, saves snapshots and deploys. Code pushes to main also read fresh Docs and build/deploy, but do not save snapshots. No separate export step is needed for ordinary edits.

## Redirect stubs

Each published post creates two stub pages mapping its old Tumblr URLs to the canonical one. They are HTML meta-refresh pages labelled as preview redirects. During cutover, the same mapping drives real server-side redirects on the live domain; until then, old URLs on the live blog keep working as they are.

## RSS

`feed.xml` lists archive posts with their original dates and stable IDs, newest first. It is rebuilt on every publish, so corrections flow through. The vt-0001 test post never appears in the feed. No email is sent anywhere in this pipeline.

## New posts from copied Docs

1. Open the private blog template and choose File > Make a copy. Save the copy inside the existing publishing folder or one of its subfolders. Rename the Doc freely: the importer uses its link, not its filename.
2. Replace the guide/placeholders with your post. The first paragraph must be the post title, exactly matching the Sheet title. The remaining paragraphs are the article body. Use Heading 2/3, real lists and inline images; the importer strips the title to avoid repeating it.
3. Add a row in **New posts**. Use the next unused permanent Post ID (`vt-0002`, `vt-0003`, etc.), title, Doc link, Draft status, publish date and stable URL slug. Date format is `YYYY-MM-DD` or `YYYY-MM-DD HH:MM` in Europe/Amsterdam. The URL is `/post/YYYY-MM-DD-slug/`. Teaser and SEO description are optional.
4. Choose `RSS` or `Not eligible`. This controls the generated preview feed only; there is no email integration or email send. Set status to `Publish` when the article is approved. `Published` also refreshes it; `Draft` pauses updates but does not remove an already published snapshot.
5. Manually run **Actions > Build blog preview > Run workflow** on main. It reads the Sheet and fresh Docs, validates, saves snapshots and deploys. Future-dated rows wait until a later manual run when due, not an automatic timer. A code push also rebuilds but does not save snapshots.
6. Keep Post ID, date and URL slug unchanged after first publishing. Headline, Doc filename, body and teaser can change. A duplicate ID, duplicate Doc, changed permanent URL, inaccessible Doc, invalid metadata or missing date/slug stops the build instead of silently replacing another post. GitHub's successful run and deployed page are the completion checks; the read-only workflow does not fill Sheet status, URL, revision or last-build cells.

The existing labelled vt-0001 test uses the same general row/Doc reader but keeps its fixed pilot URL, and remains excluded from index, navigation and RSS. It is the only row allowed to use `Publish test`. Existing archive Docs keep their original three source-header paragraphs and stricter per-post folder validation. New Docs are accepted only beneath the private publishing folder, even if renamed.

## Site tab

The Sheet's Site tab controls preview chrome without code changes: `nav_1`/`nav_2` (top-right links), `rss_enabled`, and `preview_banner` text. The next build picks up changes.

## Scope and safety

The importer accepts only the configured Sheet, source Docs inside verified `Posts/<date-first folder>` paths, registry rows whose identity (original URL, Tumblr ID, date) matches, and approved New posts rows inside the publishing folder. Article HTML is sanitized to a small tag allowlist; embedded images are verified by content; scripts, iframes and forms never pass. Legacy posts keep their original outbound links, including old public links to Google-hosted documents, exactly as published on the original blog.

Google access remains keyless and read-only, using short-lived credentials restricted to this repository, main branch and exact workflow. No long-lived service-account keys, billing, free trial or broader Google access were added.

## Editorial metadata and teasers

Redirects columns O (Teaser) and P (SEO description), and New posts columns L/M with the same names, are optional public-text fields. Teaser is shown in full beneath the archive headline with natural wrapping, no line clamp, substring cut or ellipsis. Blank means no teaser. SEO description overrides Teaser for the description and social metadata; if both are blank, the existing title is used. The workflow reads these fields on the next manual publish or code deployment. Keep private notes and source links out of both fields.

Article pages emit a unique title, description, self-canonical URL, author, original publication date, Open Graph/Twitter text metadata and BlogPosting structured data. No modified date is invented. Preview noindex/nofollow and robots blocking remain unchanged. Canonicals use the preview origin, not the live blog; live URL/indexing/redirect/sitemap checks remain a separate cutover task. Social images and per-image descriptive alt text are not completed by this change.

Copying the reusable Google Doc is an authoring step, not a publishing trigger. Duplicate it with File > Make a copy, replace placeholders and use native Heading 2/Heading 3, real lists, inline images and descriptive links. Put title/date/tags/status and teaser/SEO description in the registry. The New posts instructions above describe the implemented manual publishing route. Existing archive Docs retain their special three-paragraph source headers unchanged.
