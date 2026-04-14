"""
core/schema_builder.py
======================
Builds a complete Schema.org JSON-LD @graph block for any site in the factory.

Supported node types:
  - WebPage        (always)
  - Product        (always)
  - BreadcrumbList (always)
  - WebSite        (always, site-wide reference)
  - Organization   (always, site-wide reference)
  - FAQPage        (optional — only if config has faq entries)
  - VideoObject    (optional — only if config has video data)

Usage:
    from core.schema_builder import build_schema
    json_ld_string = build_schema(config, content)

    config  — dict loaded from sites/xxx/config.yaml
    content — dict loaded from sites/xxx/content.json
              (used only to pull FAQ Q&A so schema stays in sync with visible text)
"""

import json
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_schema(config: dict, content: dict) -> str:
    """
    Returns a <script type="application/ld+json"> string with the full @graph.
    Inject this string verbatim into the <head> of the rendered HTML page.
    """
    graph = []

    site_url   = _site_url(config)          # e.g. "https://esign.vercel.app"
    page_url   = _page_url(config)          # e.g. "https://esign.vercel.app/"
    org_id     = f"{site_url}/#organization"
    website_id = f"{site_url}/#website"

    # Build optional nodes first so we know which @ids to wire into WebPage.hasPart
    faq_node   = _build_faq(page_url, content)
    video_node = _build_video(page_url, config)

    has_part = []
    if faq_node:
        has_part.append({"@id": f"{page_url}#faq"})
    if video_node:
        has_part.append({"@id": f"{page_url}#video"})

    # Core nodes — order matters for readability in <head>
    graph.append(_build_webpage(page_url, website_id, org_id, config, has_part))
    graph.append(_build_product(page_url, org_id, config))
    graph.append(_build_breadcrumbs(page_url, config))
    graph.append(_build_website(site_url, website_id, org_id, config))
    graph.append(_build_organization(site_url, org_id, config))

    # Optional nodes
    if faq_node:
        graph.append(faq_node)
    if video_node:
        graph.append(video_node)

    payload = {"@context": "https://schema.org", "@graph": graph}
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{json_str}\n</script>'


# ---------------------------------------------------------------------------
# Node builders
# ---------------------------------------------------------------------------

def _build_webpage(page_url: str, website_id: str, org_id: str,
                   config: dict, has_part: list) -> dict:
    seo  = config.get("seo", {})
    node = {
        "@type":         "WebPage",
        "@id":           f"{page_url}#webpage",
        "url":           page_url,
        "name":          seo.get("title", config["site"]["name"]),
        "inLanguage":    config["site"].get("lang", "en"),
        "datePublished": seo.get("date_published", _now_iso()),
        "dateModified":  seo.get("date_modified",  _now_iso()),
        "isPartOf":      {"@id": website_id},
        "publisher":     {"@id": org_id},
        "about":         {"@id": f"{page_url}#product"},
        "breadcrumb":    {"@id": f"{page_url}#breadcrumbs"},
    }
    if has_part:
        node["hasPart"] = has_part
    return node


def _build_product(page_url: str, org_id: str, config: dict) -> dict:
    schema  = config.get("schema", {})
    seo     = config.get("seo", {})
    node = {
        "@type":       "Product",
        "@id":         f"{page_url}#product",
        "name":        schema.get("product_name", config["site"]["name"]),
        "url":         page_url,
        "description": schema.get("product_description",
                                  seo.get("description", "")),
        "category":    schema.get("product_category", "Productivity"),
        "brand":       {"@id": org_id},
    }

    # AggregateRating — only include if both values are present
    rating_value = schema.get("rating_value")
    rating_count = schema.get("rating_count")
    if rating_value is not None and rating_count is not None:
        node["aggregateRating"] = {
            "@type":       "AggregateRating",
            "ratingValue": float(rating_value),
            "ratingCount": int(rating_count),
        }

    return node


def _build_breadcrumbs(page_url: str, config: dict) -> dict:
    crumbs = config.get("schema", {}).get("breadcrumbs", [])
    items  = []
    for i, crumb in enumerate(crumbs, start=1):
        items.append({
            "@type":    "ListItem",
            "position": i,
            "item": {
                "@id":  crumb["url"],
                "name": crumb["name"],
            },
        })

    # Always add current page as last crumb if not already present
    if not crumbs or crumbs[-1].get("url") != page_url:
        seo = config.get("seo", {})
        items.append({
            "@type":    "ListItem",
            "position": len(items) + 1,
            "item": {
                "@id":  page_url,
                "name": seo.get("title", config["site"]["name"]),
            },
        })

    return {
        "@type":           "BreadcrumbList",
        "@id":             f"{page_url}#breadcrumbs",
        "itemListElement": items,
    }


def _build_website(site_url: str, website_id: str,
                   org_id: str, config: dict) -> dict:
    return {
        "@type":     "WebSite",
        "@id":       website_id,
        "name":      config["site"]["name"],
        "url":       f"{site_url}/",
        "publisher": {"@id": org_id},
    }


def _build_organization(site_url: str, org_id: str, config: dict) -> dict:
    org_cfg = config.get("organization", {})
    node = {
        "@type": "Organization",
        "@id":   org_id,
        "name":  org_cfg.get("name", config["site"]["name"]),
        "url":   f"{site_url}/",
    }
    if org_cfg.get("logo"):
        node["logo"] = {
            "@type":       "ImageObject",
            "url":         org_cfg["logo"],
            "contentUrl":  org_cfg["logo"],
        }
    if org_cfg.get("same_as"):
        node["sameAs"] = org_cfg["same_as"]   # list of social/profile URLs
    return node


def _build_faq(page_url: str, content: dict) -> Optional[dict]:
    """
    Pulls FAQ data from content.json (troubleshooting_accordion block).
    Returns None if no FAQ section found.
    """
    sections = content.get("sections", [])
    faq_section = next(
        (s for s in sections if s.get("id") == "troubleshooting_accordion"),
        None,
    )
    if not faq_section:
        return None

    bullets = faq_section.get("bullets", [])
    entities = []
    for bullet in bullets:
        if isinstance(bullet, dict) and bullet.get("label") and bullet.get("text"):
            entities.append({
                "@type": "Question",
                "name":  bullet["label"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text":  bullet["text"],
                },
            })

    if not entities:
        return None

    return {
        "@type":       "FAQPage",
        "@id":         f"{page_url}#faq",
        "mainEntity":  entities,
    }


def _build_video(page_url: str, config: dict) -> Optional[dict]:
    """
    Builds VideoObject only if config.schema.video is present and has required fields.
    """
    video = config.get("schema", {}).get("video")
    if not video:
        return None

    # Required fields check
    required = ["name", "upload_date", "watch_url", "embed_url", "thumbnail_urls"]
    if not all(video.get(f) for f in required):
        return None

    node = {
        "@type":        "VideoObject",
        "@id":          f"{page_url}#video",
        "name":         video["name"],
        "uploadDate":   video["upload_date"],
        "url":          video["watch_url"],
        "embedUrl":     video["embed_url"],
        "thumbnailUrl": video["thumbnail_urls"],   # list of URLs
        "publisher":    {"@id": f"{_site_url_from_page(page_url)}/#organization"},
    }
    if video.get("description"):
        node["description"] = video["description"]
    if video.get("duration"):
        node["duration"] = video["duration"]       # ISO 8601, e.g. "PT2M30S"

    return node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _site_url(config: dict) -> str:
    domain   = config["site"]["domain"].rstrip("/")
    protocol = "https"
    if domain.startswith("http"):
        return domain
    return f"{protocol}://{domain}"


def _page_url(config: dict) -> str:
    """For a single-page landing, page URL == site root."""
    return _site_url(config) + "/"


def _site_url_from_page(page_url: str) -> str:
    """Strip trailing slash and path to get site root."""
    from urllib.parse import urlparse
    parsed = urlparse(page_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Minimal config to verify output without loading real files
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
        },
        "schema": {
            "product_name":        "eSign Pro",
            "product_description": "A secure eSignature platform for individuals and teams.",
            "product_category":    "Productivity",
            "rating_value":        4.7,
            "rating_count":        1240,
            "breadcrumbs": [
                {"name": "Home", "url": "https://esign-pro.vercel.app/"},
            ],
        },
        "organization": {
            "name":    "eSign Pro",
            "logo":    "https://esign-pro.vercel.app/logo.png",
            "same_as": ["https://twitter.com/esignpro"],
        },
    }

    _demo_content = {
        "title": "Free eSignature Tool",
        "sections": [
            {
                "id":      "troubleshooting_accordion",
                "heading": "Frequently Asked Questions",
                "paragraphs": ["Common questions about electronic signatures."],
                "bullets": [
                    {"label": "Is an eSignature legally binding?",
                     "text":  "Yes. Under the ESIGN Act and UETA, electronic signatures carry the same legal weight as handwritten ones in all 50 U.S. states."},
                    {"label": "What file formats are supported?",
                     "text":  "Most platforms support PDF, DOCX, and image formats. PDF is recommended for final signed documents due to its fixed layout."},
                ],
            }
        ],
    }

    print(build_schema(_demo_config, _demo_content))
