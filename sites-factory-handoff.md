# Sites Factory — Handoff Document
**Date:** April 15, 2026  
**Project:** sites-factory (multi-site SEO landing page pipeline)  
**GitHub:** https://github.com/logvinsergii/sites-factory  
**User:** Sergii (SEO specialist, Antigravity/airSlate, Uman, Ukraine)

---

## ⚠️ Vercel Project Mapping (CRITICAL — read before any deploy)

| Site folder | Vercel project name | Alias URL | Vercel account | project.json location |
|-------------|--------------------|---------------------------------|----------------|----------------------|
| esign_001 | esign-001 | esign-001.vercel.app | airSlate | sites/esign_001/.vercel/project.json |
| esign_002 | esign-002-v2 | esign-002-v2.vercel.app | logvinsergii-5973 | sites/esign_002/.vercel/project.json |
| esign_003 | signature-gen | signature-gen-one.vercel.app | logvinsergii-5973 | sites/esign_003/.vercel/project.json |

### Deploy rule — ЗАВЖДИ деплоїти з папки сайту, НЕ з кореня

```bash
# ✅ ПРАВИЛЬНО
cd ~/sites-factory/sites/esign_003 && vercel --prod
cd ~/sites-factory/sites/esign_002 && vercel --prod
cd ~/sites-factory/sites/esign_001 && vercel --prod

# ❌ НЕПРАВИЛЬНО — з кореня ~/sites-factory — переплутає проєкти!
cd ~/sites-factory && vercel --prod
```

Кожна папка `sites/esign_00X/.vercel/project.json` містить правильний `projectId` і `orgId` для свого Vercel проєкту. Файл `.vercel/project.json` в корені репо — не використовується і може бути відсутнім.

---

## What Was Built

A Python-based static site factory that generates SEO-optimised landing pages at scale.
Each site has its own folder, config, and content. One command generates + deploys.

### Architecture

```
sites-factory/
├── core/
│   ├── schema_builder.py     # Schema.org @graph JSON-LD (WebPage, Product, FAQ, BreadcrumbList, Organization, VideoObject)
│   └── seo.py                # meta tags, canonical, hreflang, robots.txt, sitemap.xml, _headers
├── themes/
│   ├── theme_alpha/          # Light editorial (DM Serif Display + DM Sans, blue accent)
│   ├── theme_beta/           # Dark industrial (Syne + Instrument Sans, amber accent)
│   └── theme_tool/           # Clean product UI (Plus Jakarta Sans, blue) — for interactive tools
├── sites/
│   ├── esign_001/            # Electronic signature — theme_alpha — esign-001.vercel.app (airSlate Vercel)
│   ├── esign_002/            # Online document signing — theme_beta — esign-002-v2.vercel.app (personal Vercel)
│   └── esign_003/            # Signature generator — theme_tool — signature-gen-one.vercel.app (personal Vercel)
├── build.py                  # config.yaml + content.json → output/ (index.html, robots.txt, sitemap.xml, _headers)
├── generate_content.py       # LiteLLM → content.json (Dynamic Prompt pipeline)
├── build.sh                  # Vercel build script (creates venv, installs deps, runs build.py)
├── requirements.txt          # jinja2, pyyaml, requests
├── key.txt                   # LiteLLM API key (git-ignored!)
└── vercel.json               # Root Vercel config (for esign_003 / signature-gen project)
```

---

## Three Live Sites

| Site | URL | Theme | Keyword | Vercel Account |
|------|-----|-------|---------|----------------|
| esign_001 | esign-001.vercel.app | theme_alpha (light) | electronic signature | airSlate |
| esign_002 | esign-002-v2.vercel.app | theme_beta (dark) | online document signing | logvinsergii-5973 (personal) |
| esign_003 | signature-gen-one.vercel.app | theme_tool | online signature generator | logvinsergii-5973 (personal) |

**esign_003 is special:** has a static Draw/Type signature tool (canvas + fonts) at top + dynamic content sections from Dynamic Prompt below.

---

## LiteLLM Config

- **Endpoint:** `https://litellm-proxy.infrateam-dev.xyz/v1/chat/completions`
- **Model:** `gemini/gemini-2.5-flash`
- **Key file:** `~/sites-factory/key.txt` (plain text, one line, git-ignored)
- **VPN required** to reach the proxy

---

## Content Generation Pipeline

```bash
# Generate content for a site
cd ~/sites-factory
source venv/bin/activate
python generate_content.py --site sites/esign_001 --keyword "electronic signature"

# Options:
# --variants 3     → generate 3 variants, pick the best interactively
# --dry-run        → print prompt only, no API call
```

### Dynamic Prompt Rules (in generate_content.py PROMPT_TEMPLATE)

Five critical rules were added beyond the base Dynamic Prompt:

1. **W5H1 Framework** — every block answers Who/What/When/Where/Why/How
2. **ELI5/ELI10** — complex terms explained simply, embedded naturally in text
3. **Real data only** — comparison tables use real platforms (signNow, DocuSign, Adobe Sign, PandaDoc, HelloSign) with real prices
4. **Block selection** — only blocks relevant to the keyword; no filler
5. **No placeholder text** — never "Header Row", "Column Name", "Competitor A"

### Known Issue: Model adds trailing text after JSON

Fixed in `_parse_json()` using **balanced brace matching** instead of `rfind("}")`.
This correctly finds the first complete JSON object and ignores anything after it.

### Known Issue: Model stuffs full text into `label` fields

In blocks like `examples_case_cards`, the model sometimes writes the full paragraph text into the `label` field using `::` separators (e.g. `"Real Estate :: Streamlining property transactions :: Real estate agents use..."`), causing the label to render in uppercase and duplicate the `text` field below it.

**Fix:** Manually edit `content.json` after generation and shorten labels to just the category name:
```python
python3 -c "
import json
data = json.load(open('/Users/sergii/sites-factory/sites/esign_003/content.json'))
for s in data['sections']:
    if s.get('id') == 'examples_case_cards':
        s['bullets'][0]['label'] = 'Real Estate'
        s['bullets'][1]['label'] = 'Human Resources (HR)'
json.dump(data, open('/Users/sergii/sites-factory/sites/esign_003/content.json', 'w'), indent=2)
"
```
Then rebuild and redeploy. This should also be added as a validation rule in `generate_content.py`.

---

## Build & Deploy

### Local build
```bash
cd ~/sites-factory
source venv/bin/activate
python build.py --site sites/esign_001
# Output: sites/esign_001/output/ (index.html, robots.txt, sitemap.xml, _headers)
```

### Deploy to Vercel

**IMPORTANT: Always deploy from the site subfolder, not from ~/sites-factory root.**

```bash
# Build + deploy esign_003
cd ~/sites-factory && source venv/bin/activate && python build.py --site sites/esign_003
cd ~/sites-factory/sites/esign_003 && vercel --prod

# Build + deploy esign_002
cd ~/sites-factory && source venv/bin/activate && python build.py --site sites/esign_002
cd ~/sites-factory/sites/esign_002 && vercel --prod

# Build + deploy esign_001
cd ~/sites-factory && source venv/bin/activate && python build.py --site sites/esign_001
cd ~/sites-factory/sites/esign_001 && vercel --prod
```

**Vercel answers:**
- Scope: `logvinsergii-5973's projects` (personal, works reliably)
- Scope: `airSlate` (corporate — has pip restrictions, only `esign_001` works there)
- Link to existing project: `y` (project already exists — always say yes!)

**airSlate Vercel restriction:** blocks `pip install` in many configurations.
Only `python -m pip --break-system-packages` worked for esign_001.
For new sites, use personal Vercel account.

---

## Adding a New Site (5-minute workflow)

```bash
cd ~/sites-factory

# 1. Copy an existing site
cp -r sites/esign_001 sites/esign_004

# 2. Edit config.yaml
nano sites/esign_004/config.yaml
# Change: name, domain, theme, keyword, SEO fields

# 3. Generate content (VPN on!)
source venv/bin/activate
python generate_content.py --site sites/esign_004 --keyword "your keyword"

# 4. Build locally
python build.py --site sites/esign_004

# 5. Deploy (from site subfolder!)
cd ~/sites-factory/sites/esign_004 && vercel --prod
# Answer: create new project → n (new), pick scope, set name
# After first deploy, .vercel/project.json is created automatically in sites/esign_004/
```

---

## config.yaml Structure

```yaml
site:
  name: "Brand Name"
  domain: "site.vercel.app"
  lang: "en"
  theme: "theme_alpha"          # theme_alpha | theme_beta | theme_tool

seo:
  title: "Page Title | Brand"
  description: "120-160 char description"
  date_published: "2025-01-15T10:00:00Z"
  date_modified:  "2025-04-15T10:00:00Z"
  hreflang:
    - lang: "en"
      url: "https://site.vercel.app/"

content:
  keyword: "your target keyword"   # used by generate_content.py

schema:
  product_name: "Brand Name"
  product_description: "One sentence."
  product_category: "Productivity"
  rating_value: 4.7
  rating_count: 1240
  breadcrumbs:
    - name: "Home"
      url: "https://site.vercel.app/"

organization:
  name: "Brand Name"
  logo: "https://site.vercel.app/logo.png"
  same_as: []

analytics:
  ahrefs_site_id: ""    # paste Ahrefs Web Analytics site ID here
```

---

## Content Regeneration Workflow

```bash
# Not happy? Regenerate:
python generate_content.py --site sites/esign_002 --keyword "online document signing"

# Previous versions saved in:
sites/esign_002/content_history/content_20260415_070218.json

# Restore a previous version:
cp sites/esign_002/content_history/content_20260415_XXXXXX.json sites/esign_002/content.json
python build.py --site sites/esign_002
```

---

## BLOCK_IDs — Dynamic Prompt

All 27 block types are supported in all themes. Key ones:

| BLOCK_ID | UI Component |
|----------|-------------|
| `intro_what_is` | Full-width prose paragraph |
| `why_should_you_box` | Blue highlight card |
| `who_uses_checkmarks_blue` | Checklist with intro/outro |
| `key_features_6_cards` | 3-column card grid |
| `step_guide_vertical` | Numbered vertical steps |
| `comparison_check_table` | Yes/No table (real platform names!) |
| `pricing_comparison_table` | Pricing table (signNow first, highlighted) |
| `roi_stats_banner` | Dark stats banner |
| `troubleshooting_accordion` | FAQ accordion — MANDATORY in every response |
| `best_practices_list` | Practice cards (supports both string and label+text bullets) |

---

## Theme Summary

### theme_alpha (Light Editorial)
- Fonts: DM Serif Display + DM Sans + DM Mono
- Colors: cream white, #2a5cff blue accent
- Best for: informational landing pages

### theme_beta (Dark Industrial)
- Fonts: Syne + Instrument Sans + Roboto Mono
- Colors: #0c0c0e near-black, #f0a500 amber accent
- Best for: informational landing pages (different aesthetic)

### theme_tool (Clean Product UI)
- Fonts: Plus Jakarta Sans
- Colors: #f8f9fc light grey, #2563eb blue
- Best for: sites with interactive tools (signature generator, calculators)
- Special: has static Draw/Type tool section + dynamic content sections below

---

## theme_tool CSS — Key Rules (as of April 15, 2026)

After a full UI polish session on esign_003, the following CSS rules were tuned in `themes/theme_tool/index.html.j2`:

```css
/* Section headings */
h2 {
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 8px;
  margin-top: 0;
  line-height: 1.25;
}

/* Universal gap between h2 and any following element */
h2+p, h2+.sec-sub, h2+.block-intro, h2+div, h2+ul, h2+ol {
  margin-top: 12px;
}

/* Block intro wrapper (used in intro_what_is) */
.block-intro {
  margin-top: 12px;
}
.block-intro p {
  font-size: 1.05rem;
  color: var(--text-2);
  max-width: 780px;
  line-height: 1.8;
}

/* Section subtitle */
.sec-sub {
  font-size: .95rem;
  color: var(--text-2);
  max-width: 580px;
  margin-top: 12px;
  margin-bottom: 36px;
  line-height: 1.7;
}

/* Section label (uppercase tag above heading) */
.sec-lbl {
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--blue);
  margin-bottom: 10px;
}

/* Text width fix — who/platform intro paragraphs */
.who-intro, .who-outro { max-width: 100%; }
.platform-intro, .platform-outro { max-width: 100%; }

/* FAQ accordion — centered */
.wrap[style*="max-width:720px"] { margin: 0 auto; }
```

**Important:** `h2` in theme_tool is a plain tag (no class). theme_alpha uses `.section-heading` class with DM Serif Display font instead — don't confuse the two when copying CSS between themes.

---

## SEO Checklist (auto-generated per build)

- ✅ `<title>` and `<meta description>` from config.yaml
- ✅ `<link rel="canonical">` self-referencing
- ✅ `<link rel="alternate" hreflang>` + x-default
- ✅ Open Graph + Twitter Card tags
- ✅ Schema.org `@graph` JSON-LD: WebPage + Product + BreadcrumbList + Organization + WebSite + FAQPage (if accordion present)
- ✅ `robots.txt` with AI bot allowlist (GPTBot, ClaudeBot, PerplexityBot, CCBot, anthropic-ai, Meta-ExternalAgent)
- ✅ `sitemap.xml` with lastmod from config
- ✅ `_headers` security headers + cache rules

---

## UI Issues Fixed on esign_003 (April 15, 2026 session)

The following fixes were applied to `themes/theme_tool/index.html.j2` and `sites/esign_003/content.json`:

| # | Problem | Fix | Where |
|---|---------|-----|-------|
| 1 | `h2` too small, same visual weight as body text | Increased to `clamp(1.5rem,3vw,2rem)`, `font-weight:800`, `color:#0f172a` | theme_tool CSS |
| 2 | No gap between `h2` and first paragraph | Added `margin-top:12px` to all `h2+*` siblings | theme_tool CSS |
| 3 | `.block-intro` not covered by `h2+*` selector | Added `.block-intro{margin-top:12px}` directly | theme_tool CSS |
| 4 | `.sec-sub` had no top margin | Added `margin-top:12px` to `.sec-sub` | theme_tool CSS |
| 5 | `best_practices_list` bullets rendering as `+` icon | Fixed flexible bullet rendering | theme_tool template |
| 6 | `examples_case_cards` — text duplicated in CAPS | Model stuffed full text into `label` field; shortened labels to `"Real Estate"` / `"Human Resources (HR)"` in content.json | esign_003/content.json |
| 7 | Blue left-border on h2 (unwanted) | Removed border-left style, reverted to clean h2 | theme_tool CSS |
| 8 | FAQ accordion left-shifted | Added `margin:0 auto` to `.wrap[style*="max-width:720px"]` | theme_tool CSS |
| 9 | Text paragraphs cut at ~55% width | Set `.who-intro,.who-outro,.platform-intro,.platform-outro` to `max-width:100%` | theme_tool CSS |

**Remaining issues (not yet fixed):**
- `intro_what_is` first block — heading may still be close to text in some browser renders (verify after latest deploy)
- esign_001 and esign_002 content not yet regenerated with updated W5H1/ELI5 rules

---

## Next Steps (updated)

1. **Verify esign_003 CSS fixes** — check FAQ centering and text width in browser after latest deploy
2. **Regenerate esign_003 content** — regenerate with updated prompt to get better W5H1/ELI5 content and fix `label` field issues at the source
3. **Add label validation to generate_content.py** — post-process `bullets[].label` to strip `::` separators and truncate to first segment only
4. **Google Search Console** — add each site, submit sitemap
5. **Bing Webmaster Tools** — add each site for Bing/Copilot traffic
6. **Ahrefs Web Analytics** — add `ahrefs_site_id` to each config.yaml
7. **Custom domains** — if traffic validates, upgrade from vercel.app subdomains
8. **theme_gamma** — a third distinct aesthetic for more anti-fingerprint diversity
9. **esign_001 content regeneration** — regenerate with updated W5H1/ELI5 rules
10. **esign_002 content regeneration** — same as above
11. **Batch generation script** — `python generate_content.py --all` (not yet built)

---

## Local Environment

- **OS:** macOS (Apple Silicon)
- **Terminal:** Warp
- **Python:** 3.14.4 via Homebrew (`/opt/homebrew/bin/python3`)
- **Venv:** `~/sites-factory/venv/` — activate with `source venv/bin/activate`
- **Git remote:** `https://github.com/logvinsergii/sites-factory.git`
- **Vercel CLI:** 51.2.1 (`vercel --prod` from site subfolder)

---

## Key Files NOT in Git

```
key.txt                          # LiteLLM API key
sites/*/output/                  # Built HTML (regenerated on deploy)
sites/*/content_history/         # Content generation history
venv/                            # Python virtual environment
.DS_Store
```
