#!/usr/bin/env python3
"""
build.py
========
Entry point: assembles a complete static site from config.yaml + content.json.

Usage:
    python build.py --site sites/esign_001
    python build.py --site sites/esign_001 --theme theme_beta   # override theme
    python build.py --all                                         # build all sites

Output (per site):
    sites/xxx/output/index.html
    sites/xxx/output/robots.txt
    sites/xxx/output/sitemap.xml
    sites/xxx/output/_headers

Vercel reads from sites/xxx/output/ via vercel.json outputDirectory setting.
"""

import argparse
import json
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Project-local imports
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from core.schema_builder import build_schema
from core.seo import (
    build_head_tags,
    build_robots_txt,
    build_sitemap_xml,
    build_vercel_headers,
)


# ── Constants ────────────────────────────────────────────────────────────────

THEMES_DIR  = ROOT / "themes"
SITES_DIR   = ROOT / "sites"
DEFAULT_THEME = "theme_alpha"


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="sites-factory build tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--site", metavar="SITE_PATH",
                       help="Path to site folder, e.g. sites/esign_001")
    group.add_argument("--all", action="store_true",
                       help="Build all sites under sites/")
    parser.add_argument("--theme", metavar="THEME_NAME",
                        help="Override theme defined in config.yaml")
    args = parser.parse_args()

    if args.all:
        sites = sorted(SITES_DIR.iterdir())
        results = []
        for site_path in sites:
            if site_path.is_dir() and (site_path / "config.yaml").exists():
                ok = build_site(site_path, theme_override=args.theme)
                results.append((site_path.name, ok))
        print("\n── Build summary ──")
        for name, ok in results:
            status = "✅" if ok else "❌"
            print(f"  {status}  {name}")
    else:
        site_path = Path(args.site)
        if not site_path.exists():
            print(f"❌  Site not found: {site_path}")
            sys.exit(1)
        ok = build_site(site_path, theme_override=args.theme)
        sys.exit(0 if ok else 1)


# ── Build one site ────────────────────────────────────────────────────────────

def build_site(site_path: Path, theme_override: str | None = None) -> bool:
    """
    Build a single site. Returns True on success, False on error.
    """
    print(f"\n🔨  Building: {site_path.name}")

    # ── 1. Load config ──────────────────────────────────────────────────────
    config_path = site_path / "config.yaml"
    if not config_path.exists():
        print(f"  ❌  Missing config.yaml in {site_path}")
        return False

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # ── 2. Load content ─────────────────────────────────────────────────────
    content_path = site_path / "content.json"
    if not content_path.exists():
        print(f"  ⚠️   No content.json found — using empty content skeleton")
        content = {"title": config["site"]["name"], "sections": [], "footer": {}}
    else:
        with open(content_path, encoding="utf-8") as f:
            content = json.load(f)

    # ── 3. Resolve theme ────────────────────────────────────────────────────
    theme_name = theme_override or config["site"].get("theme", DEFAULT_THEME)
    theme_dir  = THEMES_DIR / theme_name
    if not theme_dir.exists():
        print(f"  ❌  Theme not found: {theme_dir}")
        return False

    # ── 4. Prepare output directory ─────────────────────────────────────────
    output_dir = site_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 5. Generate SEO components ──────────────────────────────────────────
    head_tags = build_head_tags(config, content)
    schema_ld = build_schema(config, content)
    robots    = build_robots_txt(config)
    sitemap   = build_sitemap_xml(config)
    headers   = build_vercel_headers()

    # ── 6. Render HTML via Jinja2 ───────────────────────────────────────────
    env = Environment(
        loader=FileSystemLoader(str(theme_dir)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("index.html.j2")

    # Extract hero block from content if present
    hero = _extract_hero(content)

    # Date helpers
    now        = datetime.now(timezone.utc)
    last_updated = _format_last_updated(config, now)
    now_year   = now.year

    html = template.render(
        config       = config,
        content      = content,
        head_tags    = head_tags,
        schema_ld    = schema_ld,
        hero         = hero,
        last_updated = last_updated,
        now_year     = now_year,
    )

    # ── 7. Write output files ───────────────────────────────────────────────
    _write(output_dir / "index.html", html)
    _write(output_dir / "robots.txt", robots)
    _write(output_dir / "sitemap.xml", sitemap)
    _write(output_dir / "_headers", headers)

    # ── 8. Copy static assets from theme (fonts, images, icons) ─────────────
    static_src = theme_dir / "static"
    if static_src.exists():
        static_dst = output_dir / "static"
        if static_dst.exists():
            shutil.rmtree(static_dst)
        shutil.copytree(static_src, static_dst)
        print(f"  📁  Static assets copied from theme")

    # ── 9. Report ────────────────────────────────────────────────────────────
    index_kb = (output_dir / "index.html").stat().st_size // 1024
    print(f"  ✅  index.html    {index_kb} KB")
    print(f"  ✅  robots.txt")
    print(f"  ✅  sitemap.xml")
    print(f"  ✅  _headers")
    print(f"  📂  Output: {output_dir.resolve()}")
    return True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_hero(content: dict) -> dict | None:
    """
    If content.json has a top-level 'hero' key, return it.
    Otherwise derive a minimal hero from the page title.
    """
    if "hero" in content:
        return content["hero"]
    # Fallback: build minimal hero from title
    title = content.get("title", "")
    if title:
        return {
            "subheadline": "",
            "cta_text":    "Get Started Free",
            "cta_url":     "#get-started",
        }
    return None


def _format_last_updated(config: dict, now: datetime) -> str:
    """
    Returns a human-readable date string for the 'Last updated' badge.
    Uses date_modified from config if present, otherwise today.
    """
    raw = config.get("seo", {}).get("date_modified", "")
    if raw:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%B %d, %Y")
        except ValueError:
            pass
    return now.strftime("%B %d, %Y")


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
