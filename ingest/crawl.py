"""Crawl a prospect's public website into a tenant corpus.

    python -m ingest.crawl --slug cahanlaw --url https://www.cahanlaw.com
    python -m ingest.crawl --slug cahanlaw --url https://www.cahanlaw.com --max-pages 40 \
        --exclude "/blog/" --include "/(probate|estate|contact|about)"
    python -m ingest.crawl --slug cahanlaw --urls urls.txt      # explicit list, one per line

What it does:
  1. Discovers pages: sitemap.xml / sitemap_index.xml / wp-sitemap.xml, falling
     back to a breadth-first crawl of same-host links from the homepage.
     Core pages (shallow paths) come first; blog/tag/category/feed/admin
     URLs are skipped by default. robots.txt is respected.
  2. Extracts the main content with trafilatura (boilerplate, nav and footer
     removed) as markdown with headings preserved, so the header-aware chunker
     gets real sections.
  3. Writes tenants/<slug>/corpus/NN-<path>.md with frontmatter (title, url,
     type: page) — the url is what citations link back to.
  4. Writes a draft tenants/<slug>/tenant.json if none exists. EDIT IT before
     ingesting: name, description, contact line, starters, welcome, disclaimer.

Then: review the .md files (delete junk pages), `python -m ingest.ingest --tenant <slug>`,
and `python -m evals.tenant_eval --tenant <slug>` once you've written 8-10 golden questions.
"""

import argparse
import json
import re
import sys
import time
import urllib.robotparser
from collections import deque
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree

import httpx

ROOT = Path(__file__).resolve().parents[1]
TENANTS_DIR = ROOT / "tenants"
UA = "Mozilla/5.0 (compatible; AnshDemoBot/1.0; +https://anshmangukiya.vercel.app)"
DEFAULT_EXCLUDE = (
    r"/(tag|tags|category|categories|author|feed|rss|wp-json|wp-admin|wp-login|wp-content|"
    r"cart|checkout|my-account|privacy|privacy-policy|terms|cookie|sitemap|search|xmlrpc)(/|$)"
    r"|/page/\d+|\?s=|\?p=|#|\.(pdf|jpe?g|png|gif|svg|webp|mp4|zip|docx?|xlsx?)$"
)
MIN_CHARS = 200


# ── URL helpers ──────────────────────────────────────────────────────────

def normalize(url: str) -> str:
    p = urlparse(url)
    path = re.sub(r"/{2,}", "/", p.path) or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunparse((p.scheme, p.netloc.lower(), path, "", "", ""))


def same_host(a: str, b: str) -> bool:
    ha, hb = urlparse(a).netloc.lower(), urlparse(b).netloc.lower()
    return ha.removeprefix("www.") == hb.removeprefix("www.")


def depth(url: str) -> int:
    return len([s for s in urlparse(url).path.split("/") if s])


def slugify(url: str) -> str:
    path = urlparse(url).path.strip("/") or "home"
    return re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")[:60]


# ── discovery ────────────────────────────────────────────────────────────

def fetch(client: httpx.Client, url: str) -> tuple[int, str, str]:
    """→ (status, content_type, text). Never raises."""
    try:
        r = client.get(url, follow_redirects=True, timeout=20)
        return r.status_code, r.headers.get("content-type", ""), r.text
    except Exception as exc:  # DNS, TLS, timeout …
        return 0, "", str(exc)


def sitemap_urls(client: httpx.Client, base: str, seen: set[str] | None = None) -> list[str]:
    seen = seen if seen is not None else set()
    found: list[str] = []
    for cand in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap-index.xml"):
        sm = urljoin(base, cand)
        if sm in seen:
            continue
        seen.add(sm)
        status, ctype, text = fetch(client, sm)
        if status != 200 or ("<urlset" not in text and "<sitemapindex" not in text):
            continue
        found.extend(_parse_sitemap(client, text, seen))
        if found:
            break
    return found


def _locs(root) -> list[str]:
    """All <loc> texts regardless of namespace."""
    return [el.text.strip() for el in root.iter() if el.tag.lower().endswith("loc") and el.text and el.text.strip()]


def _parse_sitemap(client: httpx.Client, xml: str, seen: set[str]) -> list[str]:
    urls: list[str] = []
    try:
        root = ElementTree.fromstring(xml.encode("utf-8", "ignore"))
    except ElementTree.ParseError:
        return urls
    if root.tag.lower().endswith("sitemapindex"):
        for child in _locs(root):
            if child in seen or not child.startswith("http"):
                continue
            seen.add(child)
            if re.search(r"(category|tag|author|attachment|product_cat|taxonom)", child, re.I):
                continue  # taxonomy sitemaps are noise
            status, _, text = fetch(client, child)
            if status == 200:
                urls.extend(_parse_sitemap(client, text, seen))
    else:
        urls = _locs(root)
    return urls


LINK_RE = re.compile(r"""<a\s[^>]*href\s*=\s*["']([^"'#]+)["']""", re.I)


def crawl_links(client: httpx.Client, base: str, limit: int, exclude: re.Pattern) -> list[str]:
    start = normalize(base)
    queue, seen, order = deque([start]), {start}, []
    while queue and len(seen) < limit * 3:
        url = queue.popleft()
        status, ctype, html = fetch(client, url)
        if status != 200 or "html" not in ctype:
            continue
        order.append(url)
        for href in LINK_RE.findall(html):
            absu = normalize(urljoin(url, href))
            if absu in seen or not same_host(absu, start) or exclude.search(absu):
                continue
            seen.add(absu)
            queue.append(absu)
        if len(order) >= limit:
            break
    return order


# ── extraction ───────────────────────────────────────────────────────────

def extract(html: str, url: str) -> tuple[str, str]:
    """→ (title, markdown). Uses trafilatura; falls back to a crude tag-strip."""
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
        title = re.split(r"\s+[|\-–—]\s+", title)[0].strip() or title
    try:
        import trafilatura

        try:
            md = trafilatura.extract(
                html, url=url, output_format="markdown", include_tables=True,
                include_links=False, include_comments=False, favor_precision=True,
            )
        except (TypeError, ValueError):  # older trafilatura without markdown output
            md = trafilatura.extract(
                html, url=url, include_tables=True, include_links=False,
                include_comments=False, include_formatting=True, favor_precision=True,
            )
        meta = trafilatura.extract_metadata(html, default_url=url)
        if meta and meta.title:
            title = meta.title
    except ImportError:
        sys.exit("trafilatura is required: pip install -r requirements.txt")
    md = (md or "").strip()
    if not md:
        return title, ""
    # Normalise headings: demote H1s (the page title carries that), keep H2+.
    md = re.sub(r"^# +(.+)$", r"## \1", md, flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return title or slugify(url).replace("-", " ").title(), md


# ── main ─────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True, help="tenant slug, e.g. cahanlaw (lowercase, a-z0-9-)")
    ap.add_argument("--url", help="site root, e.g. https://www.cahanlaw.com")
    ap.add_argument("--urls", help="file with explicit URLs, one per line (skips discovery)")
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--include", help="regex — only keep URLs matching")
    ap.add_argument("--exclude", help="regex — drop URLs matching (added to the defaults)")
    ap.add_argument("--delay", type=float, default=0.7, help="seconds between requests")
    ap.add_argument("--ignore-robots", action="store_true")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", args.slug):
        sys.exit("slug must be lowercase letters, digits, hyphens")
    if not args.url and not args.urls:
        sys.exit("give --url or --urls")

    exclude = re.compile(DEFAULT_EXCLUDE + (f"|{args.exclude}" if args.exclude else ""), re.I)
    include = re.compile(args.include, re.I) if args.include else None

    out_dir = TENANTS_DIR / args.slug / "corpus"
    out_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}) as client:
        base = args.url
        if args.urls:
            urls = [normalize(u.strip()) for u in Path(args.urls).read_text().splitlines() if u.strip()]
            base = base or urls[0]
        else:
            base = normalize(base)
            print(f"Discovering pages on {base} …")
            urls = [normalize(u) for u in sitemap_urls(client, base)]
            src = "sitemap"
            if not urls:
                urls = crawl_links(client, base, args.max_pages, exclude)
                src = "link crawl"
            print(f"  {len(urls)} candidate URLs via {src}")

        # robots.txt
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(urljoin(base, "/robots.txt"))
        try:
            rp.read()
        except Exception:
            rp = None

        # filter + order: same host, not excluded, shallow first, homepage first
        keep: list[str] = []
        for u in dict.fromkeys(urls):  # dedupe, keep order
            if not same_host(u, base) or exclude.search(u):
                continue
            if include and not include.search(u):
                continue
            if rp and not args.ignore_robots and not rp.can_fetch(UA, u):
                continue
            keep.append(u)
        keep.sort(key=lambda u: (depth(u), len(u)))
        keep = keep[: args.max_pages]
        print(f"  fetching {len(keep)} pages (max {args.max_pages})")

        written, skipped = 0, []
        for i, u in enumerate(keep, 1):
            status, ctype, html = fetch(client, u)
            if status != 200 or "html" not in ctype:
                skipped.append((u, f"http {status}" if status else html[:60]))
                continue
            title, md = extract(html, u)
            if len(md) < MIN_CHARS:
                skipped.append((u, f"thin ({len(md)} chars)"))
                continue
            fname = f"{written + 1:02d}-{slugify(u)}.md"
            (out_dir / fname).write_text(
                "---\n"
                f"title: {json.dumps(title)}\n"
                "type: page\n"
                f"url: {u}\n"
                f"updated: {date.today().isoformat()}\n"
                "---\n\n"
                f"{md}\n",
                encoding="utf-8",
            )
            written += 1
            print(f"  [{i:2d}/{len(keep)}] {len(md):5d} chars  {title[:50]:50s} {u}")
            time.sleep(args.delay)

    print(f"\n{written} pages → {out_dir}")
    if skipped:
        print(f"skipped {len(skipped)}:")
        for u, why in skipped[:15]:
            print(f"  - {u}  ({why})")

    cfg = TENANTS_DIR / args.slug / "tenant.json"
    if not cfg.exists():
        home = next(iter(sorted(out_dir.glob("01-*.md"))), None)
        name = args.slug
        if home:
            m = re.search(r'^title: "(.*)"', home.read_text(encoding="utf-8"), re.M)
            if m:
                name = m.group(1)
        cfg.write_text(json.dumps({
            "slug": args.slug,
            "name": name,
            "short_name": name.split(" — ")[0][:40],
            "site": base,
            "industry": "law",
            "description": "EDIT ME: e.g. estate planning and probate law in Round Rock, Texas",
            "languages": ["en"],
            "accent": "#7c3aed",
            "contact": f"EDIT ME: the contact page at {base}/contact or (512) 000-0000",
            "lead_email": "",
            "starters": [
                "What does the firm help with?",
                "How much is a consultation?",
                "What should I bring to a first meeting?",
                "How do I get in touch?",
            ],
            "welcome": f"Hi — I'm the AI assistant for {name}. I answer from the firm's website and can help you get in touch. This is general information, not legal advice.",
            "disclaimer": "This assistant answers from the firm's published website content. It provides general information only — not legal advice — and does not create an attorney-client relationship.",
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nDraft config written → {cfg}   ← EDIT description / contact / starters before ingesting")
    print(f"\nNext: review {out_dir}/, then  python -m ingest.ingest --tenant {args.slug}")


if __name__ == "__main__":
    main()
