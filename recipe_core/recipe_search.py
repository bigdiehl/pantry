"""
DESCRIPTION: Find real recipes on the web for a chat request. Gemini's Google Search
tool finds pages; each page is fetched once with a short timeout and its schema.org
Recipe data (name, photo, time) is read. Sites that refuse the fetch (bot protection)
still get a basic card (title from the URL, no photo). We do not try to get around that.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from google.genai import types
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SEARCH_MODEL = "gemini-2.5-flash"
MAX_RESULTS = 4
CANDIDATES = 8
FETCH_TIMEOUT = 3
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


class WebRecipe(BaseModel):
    title: str
    url: str
    site: str
    image: Optional[str] = None
    summary: str = ""
    total_time: str = ""


# ---------------------------------------------------------------------------
# Page parsing
# ---------------------------------------------------------------------------

def _iter_jsonld(soup: BeautifulSoup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                yield item
                if "@graph" in item:
                    stack.extend(item["@graph"] if isinstance(item["@graph"], list) else [item["@graph"]])


def _is_recipe(item: dict) -> bool:
    t = item.get("@type")
    return t == "Recipe" or (isinstance(t, list) and "Recipe" in t)


def _first_image(value) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return _first_image(value[0])
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl")
    return None


def format_duration(iso: str) -> str:
    """'PT1H15M' -> '1 hr 15 min'. Returns '' if unparseable."""
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", (iso or "").strip())
    if not m or not (m.group(1) or m.group(2)):
        return ""
    hours, minutes = int(m.group(1) or 0), int(m.group(2) or 0)
    hours, minutes = hours + minutes // 60, minutes % 60
    parts = ([f"{hours} hr"] if hours else []) + ([f"{minutes} min"] if minutes else [])
    return " ".join(parts)


def parse_recipe_page(html: str, url: str) -> Optional[WebRecipe]:
    """Extract a WebRecipe from a page's schema.org Recipe JSON-LD, or None if it has none."""
    soup = BeautifulSoup(html, "html.parser")
    recipe = next((i for i in _iter_jsonld(soup) if _is_recipe(i)), None)
    if not recipe:
        return None

    og_image = soup.find("meta", property="og:image")
    image = _first_image(recipe.get("image")) or (og_image.get("content") if og_image else None)
    site_meta = soup.find("meta", property="og:site_name")
    host = urlparse(url).netloc.removeprefix("www.")
    summary = re.sub(r"\s+", " ", BeautifulSoup(str(recipe.get("description") or ""), "html.parser").get_text()).strip()

    return WebRecipe(
        title=re.sub(r"\s+", " ", str(recipe.get("name") or "")).strip() or host,
        url=url,
        site=(site_meta.get("content") if site_meta else None) or host,
        image=urljoin(url, image) if image else None,
        summary=summary[:200] + ("..." if len(summary) > 200 else ""),
        total_time=format_duration(str(recipe.get("totalTime") or recipe.get("cookTime") or "")),
    )


def _title_from_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"\.(html?|php|aspx?)$", "", slug)
    slug = re.sub(r"(^|-)(recipe|\d+)(?=-|$)", " ", slug)
    words = re.sub(r"[-_]+", " ", slug).split()
    return " ".join(w.capitalize() for w in words)


def _resolve(url: str) -> str:
    """Search results are Google redirect links; find where they point without
    downloading the target."""
    if "grounding-api-redirect" not in url:
        return url
    try:
        res = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT, allow_redirects=False)
        return res.headers.get("Location") or url
    except Exception:
        return url


def _fetch(url: str) -> Optional[WebRecipe]:
    """Resolve, fetch, parse. Full card when the page has Recipe data; basic card when
    the site refuses the request; None when it is clearly not a recipe."""
    target = _resolve(url)
    if "grounding-api-redirect" in target:
        return None
    host = urlparse(target).netloc.removeprefix("www.")
    try:
        res = requests.get(target, headers=HEADERS, timeout=FETCH_TIMEOUT, allow_redirects=True)
        if res.status_code == 200 and "html" in res.headers.get("Content-Type", ""):
            return parse_recipe_page(res.text, res.url)
        if res.status_code not in (401, 403, 429, 503):
            return None
    except Exception as e:
        logger.info("Recipe fetch failed for %s: %s", target[:80], e)
    title = _title_from_url(target)
    # Without the page we can't confirm it's a single recipe; skip obvious roundups.
    if not title or re.search(r"\b(recipes|ideas|best|ways)\b", title, re.I):
        return None
    return WebRecipe(title=title, url=target, site=host)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _grounding_urls(response) -> List[str]:
    urls = []
    for cand in getattr(response, "candidates", None) or []:
        meta = getattr(cand, "grounding_metadata", None)
        for chunk in (getattr(meta, "grounding_chunks", None) or []):
            web = getattr(chunk, "web", None)
            if web and web.uri and web.uri not in urls:
                urls.append(web.uri)
    return urls


def search_recipes(query: str, client, exclude: Optional[List[str]] = None) -> List[WebRecipe]:
    """Up to MAX_RESULTS real recipe pages for `query`, de-duplicated by URL and title."""
    avoid = f" Avoid these, already suggested: {', '.join(exclude)}." if exclude else ""
    response = client.models.generate_content(
        model=SEARCH_MODEL,
        contents=(f"Find {CANDIDATES} different recipes on the web for: {query}. "
                  f"Prefer well-known recipe sites and blogs with full recipes.{avoid} "
                  "List each recipe's name and site."),
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
    )
    urls = _grounding_urls(response)[:CANDIDATES]
    if not urls:
        return []

    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        found = list(pool.map(_fetch, urls))

    # Cards with photos first; keep search order otherwise.
    found = sorted((r for r in found if r), key=lambda r: r.image is None)
    results, seen = [], set()
    for r in found:
        key = (urlparse(r.url).netloc + urlparse(r.url).path).rstrip("/").lower()
        if key in seen or r.title.lower() in seen:
            continue
        seen.update({key, r.title.lower()})
        results.append(r)
        if len(results) == MAX_RESULTS:
            break
    return results
