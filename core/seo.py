"""
core/seo.py
===========
Generates all SEO-critical HTML head elements and static files for any site.

Responsibilities:
  1. build_head_tags()  → <meta>, <link canonical>, <link hreflang>, Ahrefs analytics
  2. build_robots_txt() → robots.txt content (allows all crawlers incl. AI bots)
  3. build_sitemap_xml()→ sitemap.xml with lastmod
  4. build_htaccess()   → _headers file for Vercel (security + cache headers)

Usage:
    from core.seo import build_head_tags, build_robots_txt, build_sitemap_xml

    head_html   = build_head_tags(config)
    robots_txt  = build_robots_txt(config)
    sitemap_xml = build_sitemap_xml(config)
"""

from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# 1. HTML <head> tags
# ---------------------------------------------------------------------------

def build_head_tags(config: dict, content: dict) -> str:
    """
    Returns a string of HTML tags to inject inside <head>.
    Includes: charset, viewport, title, meta description,
              robots, canonical, hreflang, OG, Twitter Card,
              Ahrefs Web Analytics snippet.
    """
    seo      = config.get("seo", {})
    site     = config["site"]
    analytics = config.get("analytics", {})

    page_url     = _page_url(config)
    title        = seo.get("title", site["name"])
    description  = seo.get("description", "")
    lang         = site.get("lang", "en")
    date_modified = seo.get("date_modified", _now_iso())

    # Derive OG image — fallback to /og.png
    og_image = seo.get("og_image", f"{_site_url(config)}/og.png")

    lines = [
        "<!-- ── Encoding & Viewport ── -->",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "",

        "<!-- ── Primary Meta ── -->",
        f"<title>{_esc(title)}</title>",
        f'<meta name="description" content="{_esc(description)}">',
        f'<meta name="language" content="{_esc(lang)}">',
        f'<meta name="revised" content="{_esc(date_modified)}">',
        "",

        "<!-- ── Crawling & Indexing ── -->",
        '<meta name="robots" content="index, follow, max-snippet:-1, '
        'max-image-preview:large, max-video-preview:-1">',
        "",

        "<!-- ── Canonical ── -->",
        f'<link rel="canonical" href="{page_url}">',
        "",
    ]

    # hreflang tags
    hreflang_entries = seo.get("hreflang", [])
    if hreflang_entries:
        lines.append("<!-- ── hreflang ── -->")
        for entry in hreflang_entries:
            lines.append(
                f'<link rel="alternate" hreflang="{_esc(entry["lang"])}" '
                f'href="{_esc(entry["url"])}">'
            )
        # x-default always points to canonical
        lines.append(
            f'<link rel="alternate" hreflang="x-default" href="{page_url}">'
        )
        lines.append("")

    # Open Graph
    lines += [
        "<!-- ── Open Graph ── -->",
        '<meta property="og:type" content="website">',
        f'<meta property="og:url" content="{page_url}">',
        f'<meta property="og:title" content="{_esc(title)}">',
        f'<meta property="og:description" content="{_esc(description)}">',
        f'<meta property="og:image" content="{_esc(og_image)}">',
        f'<meta property="og:locale" content="{_esc(_lang_to_locale(lang))}">',
        f'<meta property="og:site_name" content="{_esc(site["name"])}">',
        "",

        "<!-- ── Twitter Card ── -->",
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:url" content="{page_url}">',
        f'<meta name="twitter:title" content="{_esc(title)}">',
        f'<meta name="twitter:description" content="{_esc(description)}">',
        f'<meta name="twitter:image" content="{_esc(og_image)}">',
        "",

        "<!-- ── Favicon ── -->",
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg">',
        '<link rel="icon" type="image/png" href="/favicon.png">',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
        "",
    ]

    # Ahrefs Web Analytics
    ahrefs_id = analytics.get("ahrefs_site_id", "")
    if ahrefs_id:
        lines += [
            "<!-- ── Ahrefs Web Analytics ── -->",
            f'<script src="https://analytics.ahrefs.com/analytics.js" '
            f'data-key="{_esc(ahrefs_id)}" defer></script>',
            "",
        ]

    # Tailwind CSS (CDN — fine for MVP, swap for PostCSS build later)
    lines += [
        "<!-- ── Tailwind CSS ── -->",
        '<script src="https://cdn.tailwindcss.com"></script>',
        "<script>",
        "  tailwind.config = {",
        "    theme: { extend: {} }",
        "  }",
        "</script>",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. robots.txt
# ---------------------------------------------------------------------------

def build_robots_txt(config: dict) -> str:
    """
    Permissive robots.txt that allows all crawlers — including AI bots
    (GPTBot, ClaudeBot, PerplexityBot, Googlebot-Extended, etc.)
    so the site qualifies for AI-generated traffic.

    Sitemap URL is injected automatically from config.
    """
    site_url    = _site_url(config)
    sitemap_url = f"{site_url}/sitemap.xml"

    return f"""# robots.txt — generated by sites-factory/core/seo.py
# Allow all crawlers including AI training and AI answer bots

User-agent: *
Allow: /

# Google
User-agent: Googlebot
Allow: /

User-agent: Googlebot-Image
Allow: /

# Bing / Microsoft Copilot
User-agent: Bingbot
Allow: /

# OpenAI / ChatGPT
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

# Anthropic / Claude
User-agent: ClaudeBot
Allow: /

User-agent: anthropic-ai
Allow: /

# Perplexity
User-agent: PerplexityBot
Allow: /

# Common Crawl (used by many LLMs)
User-agent: CCBot
Allow: /

# Apple
User-agent: Applebot
Allow: /

# Meta
User-agent: Meta-ExternalAgent
Allow: /

Sitemap: {sitemap_url}
"""


# ---------------------------------------------------------------------------
# 3. sitemap.xml
# ---------------------------------------------------------------------------

def build_sitemap_xml(config: dict) -> str:
    """
    Generates a sitemap.xml.
    For a single-page landing, this contains one <url> entry.
    For multi-page sites, extend config.seo.sitemap_pages.
    """
    site_url      = _site_url(config)
    seo           = config.get("seo", {})
    date_modified = seo.get("date_modified", _now_iso())[:10]   # YYYY-MM-DD

    # Support optional extra pages defined in config
    pages = seo.get("sitemap_pages", [])

    # Root page is always first
    entries = [{"url": f"{site_url}/", "lastmod": date_modified, "priority": "1.0"}]

    for page in pages:
        entries.append({
            "url":      page.get("url", ""),
            "lastmod":  page.get("lastmod", date_modified),
            "priority": str(page.get("priority", "0.8")),
        })

    url_blocks = []
    for entry in entries:
        url_blocks.append(
            f"  <url>\n"
            f"    <loc>{entry['url']}</loc>\n"
            f"    <lastmod>{entry['lastmod']}</lastmod>\n"
            f"    <changefreq>monthly</changefreq>\n"
            f"    <priority>{entry['priority']}</priority>\n"
            f"  </url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(url_blocks)
        + "\n</urlset>"
    )


# ---------------------------------------------------------------------------
# 4. Vercel _headers (security + cache)
# ---------------------------------------------------------------------------

def build_vercel_headers() -> str:
    """
    Returns content for a `_headers` file (Vercel / Netlify compatible).
    Sets security headers and caching rules.
    """
    return """\
/*
  X-Frame-Options: SAMEORIGIN
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: geolocation=(), microphone=(), camera=()
  X-XSS-Protection: 1; mode=block

/sitemap.xml
  Cache-Control: public, max-age=86400

/robots.txt
  Cache-Control: public, max-age=86400

/*.css
  Cache-Control: public, max-age=31536000, immutable

/*.js
  Cache-Control: public, max-age=31536000, immutable

/*.png
  Cache-Control: public, max-age=31536000, immutable

/*.svg
  Cache-Control: public, max-age=31536000, immutable
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _site_url(config: dict) -> str:
    domain = config["site"]["domain"].rstrip("/")
    if domain.startswith("http"):
        return domain
    return f"https://{domain}"


def _page_url(config: dict) -> str:
    return _site_url(config) + "/"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _esc(text: str) -> str:
    """Minimal HTML attribute escaping."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _lang_to_locale(lang: str) -> str:
    """Convert 2-letter lang code to OG locale format."""
    mapping = {
        "en": "en_US",
        "uk": "uk_UA",
        "de": "de_DE",
        "fr": "fr_FR",
        "es": "es_ES",
        "pt": "pt_BR",
        "pl": "pl_PL",
    }
    return mapping.get(lang.lower(), f"{lang}_{lang.upper()}")


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _demo_config = {
        "site": {
            "name":   "eSign Pro",
            "domain": "esign-pro.vercel.app",
            "lang":   "en",
        },
        "seo": {
            "title":          "Free eSignature Tool | eSign Pro",
            "description":    "Sign documents online — fast, secure, legally binding.",
            "date_published": "2025-01-15T10:00:00Z",
            "date_modified":  "2025-04-14T10:00:00Z",
            "og_image":       "https://esign-pro.vercel.app/og.png",
            "hreflang": [
                {"lang": "en", "url": "https://esign-pro.vercel.app/"},
            ],
        },
        "analytics": {
            "ahrefs_site_id": "ABC123",
        },
    }

    _demo_content = {"sections": []}

    SEP = "\n" + "=" * 60 + "\n"

    print("── HEAD TAGS ──")
    print(build_head_tags(_demo_config, _demo_content))
    print(SEP)

    print("── ROBOTS.TXT ──")
    print(build_robots_txt(_demo_config))
    print(SEP)

    print("── SITEMAP.XML ──")
    print(build_sitemap_xml(_demo_config))
    print(SEP)

    print("── VERCEL _HEADERS ──")
    print(build_vercel_headers())
