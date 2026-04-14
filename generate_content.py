#!/usr/bin/env python3
"""
generate_content.py
===================
Generates content.json for a site by sending the Dynamic Prompt to LiteLLM.

Usage:
    # Generate for one site (keyword from config.yaml)
    python generate_content.py --site sites/esign_001

    # Override keyword
    python generate_content.py --site sites/esign_001 --keyword "NDA template"

    # Generate N variants and pick manually
    python generate_content.py --site sites/esign_001 --variants 3

    # Dry-run: print prompt only, don't call API
    python generate_content.py --site sites/esign_001 --dry-run

Output:
    sites/xxx/content.json          ← active content (used by build.py)
    sites/xxx/content_history/      ← all previous variants (never overwritten)
        content_20250414_153022.json
        content_20250414_160811.json
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).parent

# ── LiteLLM proxy config ──────────────────────────────────────────────────────

LITELLM_URL   = "https://litellm-proxy.infrateam-dev.xyz/v1/chat/completions"
LITELLM_MODEL = "gemini/gemini-2.5-flash"
MAX_TOKENS    = 16000        # enough for 15–20 blocks of JSON
TEMPERATURE   = 1.0          # higher = more variety between runs


# ── Dynamic Prompt template ───────────────────────────────────────────────────
# This is your prompt with {cleaned_keyword} as the only variable.
# The Add-on (full schema rules) is appended automatically from ADDON_PATH.

PROMPT_TEMPLATE = """You create structured, SEO-optimised content.

The document keyword for this page is: "{cleaned_keyword}"

This is an eSignature / electronic signature platform similar to signNow.
The platform is secure, compliant, and cost-effective, used across industries in the United States.
The tone must remain factual, neutral, and slightly positive toward the platform without promotional or sales-oriented language.
Avoid exaggerated claims, marketing language, slogans, or subjective praise.
Maintain a U.S.-centric perspective for legal references (ESIGN, UETA, HIPAA, FERPA, etc.).
Style: clear, concise, professional, and easy to read. Avoid jargon and overly technical language unless needed for accuracy.
No calls to action, no promotional messaging, no marketing copy.
The platform must always appear first in comparison tables and vendor sections and be labeled as "Recommended" or "Featured".

If the document (form or template) has a commonly used or official shorthand name (e.g., "DS-11", "W-9", "RFI"), you may standardize the formatting and use that version consistently throughout the content.

The list of blocks below is unordered and all blocks are equally important initially. Your task is to analyze the document "{cleaned_keyword}" and select at least 15 blocks — you may select more if clearly relevant. Ignore the order — focus only on what provides the most depth, utility, and relevance for this specific template or form.

You don't need to use the exact phrasing of each block title below. Instead, rewrite the titles into more natural, varied, and engaging section headings — while preserving their intended meaning.

If you can infer a specific document type (e.g., tax form, legal agreement, real estate contract, business application, power of attorney), use that to inform which blocks are most relevant.

Always prioritize blocks that provide the highest utility, legal clarity, and relevance for this specific document.

Do not include markdown heading prefixes (such as #, ##, ###) in section titles. Only use plain text for headings.

Each selected topic must be written as a fully developed content block according to the structure and geometry specified in the Dynamic Prompt Add-on. Each block must consist of a section heading and content divided into:
1. "paragraphs" — an array of informative plain text paragraphs.
2. "bullets" — an array of key points, list items, or objects (per the Bullet Structure in the Add-on).

Strict Requirements:
- Use ONLY plain text. No bolding (**), italics (_), or any markdown symbols within content strings.
- No markdown heading levels (#).
- No list markers inside the "bullets" array.
- The output MUST be a valid JSON object. Any text before or after the JSON is prohibited.

Topics to consider:
What is the {cleaned_keyword}
Purpose and Key Benefits of the {cleaned_keyword}
Who Should Use or Complete the {cleaned_keyword}
When to Use or Issue the {cleaned_keyword}
Key Components of a Professional {cleaned_keyword}
Required Information and Fields in the {cleaned_keyword}
Step-by-Step Instructions to Fill Out the {cleaned_keyword}
How to Customize and Complete the {cleaned_keyword} Online
Where to File, Send, or Submit the {cleaned_keyword}
Distribution Methods: How to Share the {cleaned_keyword}
Timelines, Deadlines, and Processing Expectations
Common Mistakes When Preparing the {cleaned_keyword}
Penalties and Risks of an Incorrect {cleaned_keyword}
Legal Validity and Enforceability of the {cleaned_keyword}
State-Specific Rules and Variations for the {cleaned_keyword}
Digital Signing and eSubmission of the {cleaned_keyword}
How to Download and Save the {cleaned_keyword} in Various Formats
Supporting Documents to Include with the {cleaned_keyword}
How to Update or Revise the {cleaned_keyword}
Tips for Accurate and Efficient Completion of the {cleaned_keyword}
Industry and Use Case Examples for the {cleaned_keyword}
Who Has Authority to Sign the {cleaned_keyword}
Notarization and Witness Requirements for the {cleaned_keyword}
How to Revoke or Cancel the {cleaned_keyword}
Differences Between Similar Document Types
How to Store and Retain the {cleaned_keyword} Securely
FAQs About the {cleaned_keyword}
Fillable Fields Guide for the {cleaned_keyword}
Cost and Fee Estimates for the {cleaned_keyword}
ROI and Time Savings with the {cleaned_keyword}
State-by-State Requirements for the {cleaned_keyword}
Industry-Specific Notes for the {cleaned_keyword}
Retention and Storage Periods for the {cleaned_keyword}
Key Milestones and Processing Stages for the {cleaned_keyword}
eSignature Solution Pricing Comparison for the {cleaned_keyword}

Follow the Dynamic Prompt Add-on rules below for output structure:

---

# Dynamic Prompt Add-on: Structured JSON Output
Version 2.2

## 1. Hard Rules

The entire response MUST be a single valid JSON object. No HTML, no Markdown outside the JSON. Response starts with {{ and ends with }}.

Output format: single JSON object only.
No HTML tags. No Markdown inside JSON. Plain text only.
FAQs block (troubleshooting_accordion) MUST appear in every response.
No citations or placeholder text.

## 2. Block IDs and Intent

Map each topic to its BLOCK_ID:

intro_what_is — define the document
why_should_you_box — explain why it matters (30-50 word paragraph, no bullets)
who_uses_checkmarks_blue — identify user profiles (2 paragraphs with [INTRO]/[OUTRO] prefix, 3 text-only bullets)
user_profiles_green — signatory roles (0 paragraphs, 2 label+text bullets)
security_data_green — list essential data elements (0 paragraphs, 6 label+text bullets)
penalties_risks_red — consequences of errors (0 paragraphs, 6 label+text bullets)
challenges_orange_bullets — avoidable errors (0 paragraphs, 4 text-only bullets)
step_guide_vertical — sequential completion guide (1 paragraph, 4 label+text bullets)
how_it_works_arrows — destination and routing (1 paragraph, 4 label+text bullets)
key_features_4_cards — export options or companion docs (1 paragraph, 4 label+text bullets)
best_practices_list — quality guidance (1 paragraph, 4 label+text bullets)
deadlines_dated_list — time-critical info (1 paragraph, 5 label+text bullets)
key_features_6_cards — anatomy of the document (1 paragraph, 6 label+text bullets)
step_guide_grid — amendment workflow (1 paragraph, 6 label+text bullets)
troubleshooting_accordion — FAQs MANDATORY (1 paragraph, 6 label+text bullets)
deadlines_horizontal_steps — authentication steps (1 paragraph, 8 label+text bullets)
platform_requirements_box — delivery channels (2 paragraphs [INTRO]/[OUTRO], 3 label+text bullets)
workflow_setup_table — digital workflow (1 paragraph, 5 label+text bullets — first is header row)
comparison_check_table — jurisdiction differences (1 paragraph, 5 table-row bullets — first is header)
examples_case_cards — real-world scenarios (1 paragraph, 2 label+text bullets with :: separator)
pricing_comparison_table — multi-vendor pricing (1 paragraph with date, 6 table-row bullets — first is header, signNow first column)
fillable_fields_guide — per-field instructions (1 paragraph, 6 label+text bullets)
cost_calculator_box — filing fees (2 paragraphs [INTRO]/[OUTRO], 4 label+text bullets)
roi_stats_banner — efficiency statistics (1 paragraph, 3 label+text bullets with concrete numbers)
state_requirements_table — jurisdiction rules (1 paragraph, 6 table-row bullets — first is header)
industry_notes_cards — industry-specific notes (1 paragraph, 4 label+text bullets)
retention_timeline — retention periods (1 paragraph, 5 label+text bullets)
deadlines_vertical_dashed — sequential milestones (1 paragraph, 4 label+text bullets)

## 3. Bullet Structures

text only: "Text string"
label + text: {{"label": "Short Title", "text": "Detailed description"}}
table row: {{"label": "Row Name", "text": "Col1 | Col2 | Col3"}}

For blocks with [INTRO]/[OUTRO]: prefix paragraphs[0] with [INTRO] and paragraphs[1] with [OUTRO].
For examples_case_cards: text field = "[intro 15-30w] :: [point 5-15w] :: [outro 30-50w]"
For all table blocks: first bullet MUST be a header row.
For pricing_comparison_table: signNow must be in the first data column, labeled "signNow (Recommended)".

## 4. JSON Output Schema

{{
  "title": "Main Page Title",
  "sections": [
    {{
      "id": "BLOCK_ID",
      "heading": "Section Heading",
      "paragraphs": ["..."],
      "bullets": []
    }}
  ]
}}

Always include troubleshooting_accordion as the last section.
Select at least 15 blocks. Order by logical information hierarchy.
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate content.json via LiteLLM")
    parser.add_argument("--site",     required=True, metavar="SITE_PATH",
                        help="Path to site folder, e.g. sites/esign_001")
    parser.add_argument("--keyword",  metavar="KEYWORD",
                        help="Override cleaned_keyword (default: from config.yaml)")
    parser.add_argument("--variants", type=int, default=1, metavar="N",
                        help="Generate N variants (saved to history, you pick the best)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Print the prompt without calling the API")
    args = parser.parse_args()

    site_path = Path(args.site)
    if not site_path.exists():
        print(f"❌  Site not found: {site_path}")
        sys.exit(1)

    # Load config
    config = yaml.safe_load((site_path / "config.yaml").read_text(encoding="utf-8"))
    keyword = args.keyword or config.get("content", {}).get("keyword") or config["site"]["name"]

    print(f"\n📝  Keyword    : {keyword}")
    print(f"🌐  Site       : {site_path.name}")
    print(f"🤖  Model      : {LITELLM_MODEL}")
    print(f"🔢  Variants   : {args.variants}")

    prompt = PROMPT_TEMPLATE.format(cleaned_keyword=keyword)

    if args.dry_run:
        print("\n── DRY RUN — prompt only ──\n")
        print(prompt[:3000], "...[truncated]")
        return

    # History folder
    history_dir = site_path / "content_history"
    history_dir.mkdir(exist_ok=True)

    results = []
    for i in range(args.variants):
        if args.variants > 1:
            print(f"\n── Variant {i + 1}/{args.variants} ──")
        content = generate_content(prompt, keyword)
        if content is None:
            print(f"  ❌  Generation failed for variant {i + 1}")
            continue

        # Save to history with timestamp
        ts        = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        hist_path = history_dir / f"content_{ts}.json"
        _write_json(hist_path, content)
        print(f"  💾  Saved to history: {hist_path.name}")

        # Validate structure
        issues = validate_content(content)
        if issues:
            print(f"  ⚠️   Validation warnings ({len(issues)}):")
            for issue in issues[:5]:
                print(f"       - {issue}")
        else:
            print(f"  ✅  Structure valid — {len(content.get('sections', []))} sections")

        results.append((hist_path, content))

    if not results:
        print("\n❌  No content generated. Check your LiteLLM proxy.")
        sys.exit(1)

    # If multiple variants: ask user which one to activate
    if len(results) > 1:
        active_path, active_content = _pick_variant(results)
    else:
        active_path, active_content = results[0]

    # Write active content.json
    output_path = site_path / "content.json"
    _write_json(output_path, active_content)
    print(f"\n✅  content.json written → {output_path}")
    print(f"   Sections   : {len(active_content.get('sections', []))}")
    print(f"   Title      : {active_content.get('title', '(no title)')}")
    print(f"\n   Run next   : python build.py --site {site_path}")


# ── LiteLLM API call ──────────────────────────────────────────────────────────

def generate_content(prompt: str, keyword: str) -> dict | None:
    """
    Sends prompt to LiteLLM proxy and returns parsed content dict.
    Returns None on failure.
    """
    print(f"  🚀  Calling LiteLLM proxy...")
    t0 = time.time()

    payload = {
        "model":       LITELLM_MODEL,
        "max_tokens":  MAX_TOKENS,
        "temperature": TEMPERATURE,
        "messages": [
            {
                "role":    "system",
                "content": (
                    "You are a structured content generation system. "
                    "Your response must be a single valid JSON object only — "
                    "no preamble, no markdown fences, no explanation. "
                    "Start your response with { and end with }."
                ),
            },
            {
                "role":    "user",
                "content": prompt,
            },
        ],
    }

    try:
        resp = requests.post(
            LITELLM_URL,
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        print("  ❌  Request timed out (180s)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ❌  Request error: {e}")
        return None

    elapsed = time.time() - t0
    print(f"  ⏱️   Response in {elapsed:.1f}s")

    data = resp.json()

    # Extract text from response
    try:
        raw_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"  ❌  Unexpected response shape: {e}")
        print(f"       Response: {str(data)[:500]}")
        return None

    # Log token usage if available
    usage = data.get("usage", {})
    if usage:
        print(f"  📊  Tokens — prompt: {usage.get('prompt_tokens', '?')} / "
              f"completion: {usage.get('completion_tokens', '?')}")

    # Parse JSON — strip markdown fences if model added them
    return _parse_json(raw_text)


# ── JSON parsing ──────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict | None:
    """
    Robustly parse JSON from model output.
    Handles: plain JSON, ```json fenced, leading/trailing whitespace.
    """
    text = raw.strip()

    # Strip ```json ... ``` fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        text = "\n".join(lines).strip()

    # Find first { and last }
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1:
        print("  ❌  No JSON object found in response")
        print(f"       Preview: {text[:300]}")
        return None

    text = text[start : end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  ❌  JSON parse error: {e}")
        print(f"       Near: ...{text[max(0, e.pos-80):e.pos+80]}...")
        return None


# ── Validation ────────────────────────────────────────────────────────────────

# Expected geometry per block: (min_paragraphs, max_paragraphs, min_bullets, max_bullets)
BLOCK_GEOMETRY = {
    "intro_what_is":            (1, 1, 0, 0),
    "why_should_you_box":       (1, 1, 0, 0),
    "who_uses_checkmarks_blue": (2, 2, 3, 3),
    "user_profiles_green":      (0, 0, 2, 2),
    "security_data_green":      (0, 0, 6, 6),
    "penalties_risks_red":      (0, 0, 6, 6),
    "challenges_orange_bullets":(0, 0, 4, 4),
    "step_guide_vertical":      (1, 1, 4, 4),
    "how_it_works_arrows":      (1, 1, 4, 4),
    "key_features_4_cards":     (1, 1, 4, 4),
    "best_practices_list":      (1, 1, 4, 4),
    "deadlines_dated_list":     (1, 1, 5, 5),
    "key_features_6_cards":     (1, 1, 6, 6),
    "step_guide_grid":          (1, 1, 6, 6),
    "troubleshooting_accordion":(1, 1, 6, 6),
    "deadlines_horizontal_steps":(1,1, 8, 8),
    "platform_requirements_box":(2, 2, 3, 3),
    "workflow_setup_table":     (1, 1, 5, 5),
    "comparison_check_table":   (1, 1, 5, 5),
    "examples_case_cards":      (1, 1, 2, 2),
    "pricing_comparison_table": (1, 1, 6, 6),
    "fillable_fields_guide":    (1, 1, 6, 6),
    "cost_calculator_box":      (2, 2, 4, 4),
    "roi_stats_banner":         (1, 1, 3, 3),
    "state_requirements_table": (1, 1, 6, 6),
    "industry_notes_cards":     (1, 1, 4, 4),
    "retention_timeline":       (1, 1, 5, 5),
    "deadlines_vertical_dashed":(1, 1, 4, 4),
}

def validate_content(content: dict) -> list[str]:
    """
    Validates content.json structure against block geometry rules.
    Returns list of warning strings (empty = all good).
    """
    issues = []

    if "title" not in content:
        issues.append("Missing 'title' field")

    sections = content.get("sections", [])
    if not sections:
        issues.append("No sections found")
        return issues

    if len(sections) < 15:
        issues.append(f"Only {len(sections)} sections (minimum 15 required)")

    # Check for mandatory troubleshooting_accordion
    ids = [s.get("id") for s in sections]
    if "troubleshooting_accordion" not in ids:
        issues.append("MANDATORY block 'troubleshooting_accordion' is missing")

    # Check last section is FAQ
    if sections and sections[-1].get("id") != "troubleshooting_accordion":
        issues.append("'troubleshooting_accordion' should be the last section")

    # Geometry checks
    for section in sections:
        block_id = section.get("id", "unknown")
        geometry = BLOCK_GEOMETRY.get(block_id)
        if geometry is None:
            issues.append(f"Unknown BLOCK_ID: '{block_id}'")
            continue

        min_p, max_p, min_b, max_b = geometry
        paras   = section.get("paragraphs", [])
        bullets = section.get("bullets", [])

        if not (min_p <= len(paras) <= max_p):
            issues.append(
                f"[{block_id}] paragraphs: expected {min_p}–{max_p}, got {len(paras)}"
            )
        if not (min_b <= len(bullets) <= max_b):
            issues.append(
                f"[{block_id}] bullets: expected {min_b}–{max_b}, got {len(bullets)}"
            )

    return issues


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _pick_variant(results: list) -> tuple:
    """Interactive picker when multiple variants were generated."""
    print("\n── Multiple variants generated ──")
    for i, (path, content) in enumerate(results, 1):
        n_sections = len(content.get("sections", []))
        title      = content.get("title", "(no title)")[:60]
        print(f"  [{i}] {path.name} — {n_sections} sections — {title}")

    while True:
        raw = input("\nWhich variant to activate? (number, or 'q' to quit): ").strip()
        if raw.lower() == "q":
            print("Aborted — no content.json written.")
            sys.exit(0)
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(results):
                return results[idx]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(results)}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
