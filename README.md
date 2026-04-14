# sites-factory

A Python-based static site factory for deploying SEO-optimised landing pages at scale.
Each site is an independent folder with its own config, content, and Vercel deployment.

---

## Project Structure

```
sites-factory/
├── core/
│   ├── schema_builder.py   # Schema.org @graph JSON-LD
│   └── seo.py              # meta tags, canonical, hreflang, robots.txt, sitemap.xml
├── themes/
│   └── theme_alpha/        # Jinja2 + Tailwind CSS template (all 27 BLOCK_IDs)
│       └── index.html.j2
├── sites/
│   └── esign_001/          # One site = one folder
│       ├── config.yaml     # Domain, SEO, schema config
│       ├── content.json    # Generated content (source of truth)
│       ├── vercel.json     # Vercel deployment config
│       ├── output/         # Built HTML + static files (git-ignored)
│       └── content_history/  # All previous content variants (git-ignored)
├── build.py                # Assembles config + content → output/
├── generate_content.py     # LiteLLM → content.json
├── requirements.txt
└── .gitignore
```

---

## Quickstart: New Site in 5 Steps

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create a new site folder
```bash
cp -r sites/esign_001 sites/esign_002
```

### 3. Edit `sites/esign_002/config.yaml`
Set your domain, keyword, SEO title, description, schema params.

### 4. Generate content
```bash
# Single generation
python generate_content.py --site sites/esign_002 --keyword "NDA template"

# Generate 3 variants and pick the best
python generate_content.py --site sites/esign_002 --keyword "NDA template" --variants 3

# Preview the prompt without calling the API
python generate_content.py --site sites/esign_002 --dry-run
```

### 5. Build
```bash
python build.py --site sites/esign_002
```

Output is in `sites/esign_002/output/` — ready to deploy.

---

## Two Independent Pipelines

```
PIPELINE 1 — Content generation
config.yaml ──► generate_content.py ──► content.json
                      │
               LiteLLM proxy
               (regenerate as many times as needed)

PIPELINE 2 — Build & deploy
config.yaml + content.json ──► build.py ──► output/ ──► Vercel
```

You can regenerate content without touching the build, and build without regenerating content.

---

## Deploy to Vercel

### Option A: Vercel CLI (recommended for corporate account)
```bash
cd sites/esign_001
vercel --prod
```

### Option B: GitHub → Vercel (auto-deploy on push)

1. Push this repo to GitHub
2. In Vercel dashboard → Import project → select repo
3. Set:
   - **Root Directory**: `sites/esign_001`
   - **Build Command**: `cd ../.. && pip install -r requirements.txt && python build.py --site sites/esign_001`
   - **Output Directory**: `output`
4. Every `git push` triggers a rebuild

### Option C: Deploy all sites at once
```bash
python build.py --all
# then deploy each output/ folder separately
```

---

## Adding a New Site

1. Copy `sites/esign_001/` → `sites/your_new_site/`
2. Edit `config.yaml` — update domain, keyword, SEO fields
3. Update `vercel.json` — change `--site` path
4. Run `generate_content.py` with your keyword
5. Run `build.py`
6. Deploy with Vercel CLI or GitHub integration

**Time to new site: ~5 minutes** (excl. generation time)

---

## Content Regeneration Workflow

```bash
# Not happy with current content? Regenerate:
python generate_content.py --site sites/esign_001 --keyword "electronic signature"

# Want options? Generate 3 variants:
python generate_content.py --site sites/esign_001 --variants 3
# → CLI asks which variant to activate

# All previous versions are in:
sites/esign_001/content_history/content_20250414_153022.json

# To restore a previous version manually:
cp sites/esign_001/content_history/content_20250414_153022.json \
   sites/esign_001/content.json
python build.py --site sites/esign_001
```

---

## config.yaml Reference

```yaml
site:
  name: "My Site"              # Brand name (used in navbar, footer, schema)
  domain: "my-site.vercel.app" # Full domain or Vercel subdomain
  lang: "en"                   # 2-letter language code
  theme: "theme_alpha"         # Theme folder name

seo:
  title: "Page Title | My Site"
  description: "Meta description — 120–160 characters."
  date_published: "2025-01-15T10:00:00Z"
  date_modified:  "2025-04-14T10:00:00Z"
  og_image: "https://my-site.vercel.app/og.png"
  hreflang:
    - lang: "en"
      url:  "https://my-site.vercel.app/"

content:
  keyword: "electronic signature"   # default keyword for generate_content.py

schema:
  product_name: "My Product"
  product_description: "One sentence."
  product_category: "Productivity"
  rating_value: 4.7
  rating_count: 1240
  breadcrumbs:
    - name: "Home"
      url:  "https://my-site.vercel.app/"

organization:
  name: "My Site"
  logo: "https://my-site.vercel.app/logo.png"
  same_as: []

analytics:
  ahrefs_site_id: ""    # Paste Ahrefs Web Analytics site ID here
```

---

## Anti-Fingerprint Design

Each site avoids pattern detection through:

- **Different themes** — `theme_alpha`, `theme_beta`, `theme_gamma` (different fonts, layouts, color systems)
- **Different content** — LiteLLM generates unique text per keyword per run; `--variants 3` gives additional variety
- **Different schema** — each site has its own `@id` namespace, org, and product nodes
- **Different domain** — each Vercel subdomain is independent

---

## SEO Checklist (auto-generated per build)

| Element | Status |
|---|---|
| `<title>` and `<meta description>` | ✅ from config.yaml |
| `<link rel="canonical">` | ✅ self-referencing |
| `<link rel="alternate" hreflang>` | ✅ + x-default |
| Open Graph tags | ✅ |
| Twitter Card tags | ✅ |
| Schema.org `@graph` JSON-LD | ✅ WebPage + Product + Breadcrumb + FAQ |
| `robots.txt` with AI bot allowlist | ✅ GPTBot, ClaudeBot, PerplexityBot... |
| `sitemap.xml` with lastmod | ✅ |
| Security headers (`_headers`) | ✅ |
| Ahrefs Web Analytics | ✅ if `ahrefs_site_id` set |

---

## LiteLLM Proxy

Default endpoint: `https://litellm-proxy.infrateam-dev.xyz/v1/chat/completions`
Default model: `gemini/gemini-2.5-flash`

To change: edit `LITELLM_URL` and `LITELLM_MODEL` at the top of `generate_content.py`.
