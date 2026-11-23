#!/usr/bin/env python3
"""
DESCRIPTION: Extract recipe data from URLs or text using Google Gemini API.
"""

import logging
import os
import re
import sys
import requests
from dataclasses import dataclass
from typing import Callable, Optional, List, Tuple

from google import genai
from google.genai import types

from recipe_core.gemini import RETRYABLE, friendly_error, generate
from bs4 import BeautifulSoup
from readability import Document
import yaml

from recipe_core.recipe_lib import RecipeData

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

@dataclass
class ValidationError:
    """Validation error for recipe extraction."""
    field: str
    message: str

@dataclass
class ImportResult:
    """Result of recipe extraction."""
    recipe_data: RecipeData
    markdown: str
    slug: str
    source: str
    validation_errors: List[ValidationError] = None

# Called with a dict describing one step of the extract/validate/retry loop, so
# callers (e.g. the web UI) can show progress while extract_recipe() runs.
# Common "type" values: attempt_start, validation_failed, retry, success,
# giving_up, failed. See the call sites in extract_recipe() for the exact
# payload shape of each.
ProgressCallback = Callable[[dict], None]

def _err_dicts(errors: List[ValidationError]) -> List[dict]:
    """Convert ValidationErrors to plain dicts for progress events / JSON."""
    return [{"field": e.field, "message": e.message} for e in errors]

def _fetch_url(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error("Failed to fetch URL %s: %s", url, e)
        raise ValueError(f"Failed to fetch URL: {e}")

def _read_url_with_gemini(client, url: str) -> str:
    """Fallback when a site refuses our direct fetch (bot protection, TLS errors):
    let Gemini's URL context tool read the page and return the recipe as plain text."""
    response = generate(
        client,
        contents=(f"Read the recipe at {url} and return its full text: title, servings, the "
                  "complete ingredient list with quantities, every instruction step, and notes. "
                  "Plain text only, no commentary. If there is a main photo, add a line "
                  "'Image URL: <url>'."),
        config=types.GenerateContentConfig(tools=[types.Tool(url_context=types.UrlContext())]),
    )
    text = (response.text or "").strip()
    if len(text) < 100:
        raise ValueError("Could not read the recipe page")
    return text

def _clean_html_for_llm(html_content: str) -> str:
    """Clean HTML content to make it more suitable for LLM processing."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove non-visible/irrelevant elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()

    # Extract image URLs and place them in the text flow
    for img in soup.find_all("img"):
        src = img.get("src")
        alt = img.get("alt", "image")
        if src:
            img.replace_with(f"\n[Image: {alt} (URL: {src})]\n")

    # Get text and clean up whitespace
    text = soup.get_text(separator="\n")

    # Clean up excessive newlines
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(chunk for chunk in lines if chunk)

def _extract_main_content(html_bytes: bytes) -> str:
    html_str = html_bytes.decode('utf-8', errors='ignore')
    return _clean_html_for_llm(html_str)

def _generate_slug(name: str) -> str:
    """Generate a slug from a recipe name."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = slug.strip('_')
    return slug

def _validate_recipe(recipe_dict: dict, yaml_text: str, markdown_text: str) -> List[ValidationError]:
    """
    Validate extracted recipe data.

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Required fields
    if not recipe_dict.get('name'):
        errors.append(ValidationError('name', 'Recipe name is missing'))

    if not recipe_dict.get('servings'):
        errors.append(ValidationError('servings', 'Servings count is missing'))
    elif not isinstance(recipe_dict['servings'], int):
        errors.append(ValidationError('servings', 'Servings must be an integer'))

    if not recipe_dict.get('meal'):
        errors.append(ValidationError('meal', 'Meal type is missing'))
    elif recipe_dict['meal'] not in ['BREAKFAST', 'LUNCH', 'DINNER']:
        errors.append(ValidationError('meal', f"Meal must be BREAKFAST, LUNCH, or DINNER (got '{recipe_dict['meal']}')"))

    if not recipe_dict.get('category'):
        errors.append(ValidationError('category', 'Category is missing'))
    elif recipe_dict['category'] not in ['ENTREE', 'SALAD', 'DESSERT', 'SIDE']:
        errors.append(ValidationError('category', f"Category must be ENTREE, SALAD, DESSERT, or SIDE (got '{recipe_dict['category']}')"))

    # Ingredients validation
    ingredients = recipe_dict.get('ingredients', [])
    if not ingredients:
        errors.append(ValidationError('ingredients', 'No ingredients found'))
    else:
        for i, ing in enumerate(ingredients):
            if not isinstance(ing, dict):
                errors.append(ValidationError(f'ingredients[{i}]', 'Ingredient must be a dictionary'))
                continue

            if not ing.get('food'):
                errors.append(ValidationError(f'ingredients[{i}]', 'Ingredient missing "food" field'))

            # Quantity is optional, but if present should be reasonable
            if 'quantity' in ing and ing['quantity']:
                qty = str(ing['quantity'])
                if len(qty) > 50:
                    errors.append(ValidationError(f'ingredients[{i}]', f'Quantity too long: "{qty[:30]}..."'))

    # Markdown validation
    if not markdown_text or len(markdown_text) < 50:
        errors.append(ValidationError('markdown', 'Instructions are missing or too short'))

    if '## Ingredients' not in markdown_text and '## ingredients' not in markdown_text.lower():
        errors.append(ValidationError('markdown', 'Markdown missing "## Ingredients" section'))

    if '## Instructions' not in markdown_text and '## instructions' not in markdown_text.lower():
        errors.append(ValidationError('markdown', 'Markdown missing "## Instructions" section'))

    return errors

def _format_validation_errors(errors: List[ValidationError]) -> str:
    """Format validation errors for Gemini feedback."""
    if not errors:
        return ""

    lines = ["The extracted recipe has the following errors:"]
    for err in errors:
        lines.append(f"- {err.field}: {err.message}")

    return "\n".join(lines)

PHOTO_INSTRUCTIONS = """

-----------------------------
The recipe is in the attached photo(s) (e.g. a cookbook page, recipe card, or handwritten note),
in order if there is more than one. Transcribe it faithfully: keep the original quantities and steps,
and read handwriting carefully. Any text above is an optional note from the user about the photos.
Do not include an image tag in the MARKDOWN section for photo imports.
"""

def _extract_with_gemini(client, content: str, feedback: Optional[str] = None,
                         images: Optional[List[Tuple[bytes, str]]] = None) -> str:
    """
    Call Gemini API to extract recipe.

    Args:
        client: Gemini API client
        content: Recipe content to extract
        feedback: Optional feedback from previous validation failure
        images: Optional (bytes, mime_type) photos of the recipe, sent alongside the prompt

    Returns:
        Raw response text from Gemini
    """
    base_prompt = """Extract recipe information from the following content and return ONLY valid YAML and Markdown.

Your response must follow the following format, with the YAML section containing structured recipe
data and the Markdown section containing formatted instructions:

---YAML---
name: Recipe Name
servings: <number of servings>
meal: <meal_type>
category: <meal_category>
min_period_weeks: 4
enabled: true
ingredients:
  - food: <food name>
    quantity: <quantity>
  - food: <food name>
    quantity: <quantity>
 ... more ingredients

---MARKDOWN---
# Recipe Name

Servings: <number of servings>
<img style="float: right;" src="image.png" width=400>

## Ingredients
- 1 cup ingredient 1
- 2 tbsp ingredient 2

## Instructions

1. Step 1
2. Step 2

### Subheading (optional. e.g., for a sauce or marinade)
1. Step 1
2. Step 2

## Notes
Optional notes here

-----------------------------
IMPORTANT RULES:
- meal_type must be one of: BREAKFAST, LUNCH, DINNER
- meal_category must be one of: ENTREE, SALAD, DESSERT, SIDE
- ingredients must use simple food names (e.g., "chicken breast", "onion", "olive oil")
- quantities should use standard units when possible (cup, tbsp, tsp, oz, lb, gram, etc.). Other
  formats are also acceptable (e.g., "1 can", "2 cloves", "3 slices")
- If no quantity is specified, omit the quantity field for that ingredient
- Return ONLY the YAML and Markdown sections, nothing else
- In the recipes directions, try to be concise and avoid unnecessary commentary. Focus on clear,
  actionable steps.
- In the MARKDOWN section, try to capture the main recipe image and replace "image.png" with the
  actual image URL if available. If no image is found, you can omit the image tag or use a placeholder.
"""

    if feedback:
        prompt = f"""{base_prompt}

-----------------------------
PREVIOUS ATTEMPT FAILED WITH THESE ERRORS:
{feedback}

Please fix these errors and try again.

-----------------------------
Content to extract:

{content[:10000]}"""
    else:
        prompt = f"""{base_prompt}

-----------------------------
Content to extract:

{content[:10000]}"""

    contents = prompt
    if images:
        prompt += PHOTO_INSTRUCTIONS
        contents = [prompt] + [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images]

    logger.debug("Sending prompt to Gemini API...")
    response = generate(
        client,
        contents=contents
    )

    # Extract text from response
    if hasattr(response, 'text'):
        return response.text
    elif hasattr(response, 'candidates') and response.candidates:
        return response.candidates[0].content.parts[0].text
    else:
        raise ValueError("Unable to extract text from response")

def extract_recipe(
    url: Optional[str] = None,
    text: Optional[str] = None,
    images: Optional[List[Tuple[bytes, str]]] = None,
    api_key: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> ImportResult:
    """
    Extract recipe data from a URL or text using Gemini API with validation and retry.

    Args:
        url: URL to extract recipe from (optional)
        text: Text containing recipe (optional). With images, an optional note about them.
        images: (bytes, mime_type) photos of a recipe (optional)
        api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
        on_progress: Optional callback invoked with a dict at each step of the
            attempt/validate/retry loop, so a caller can surface progress
            (e.g. "attempt 2/3", validation errors being fed back) as it runs.

    Returns:
        ImportResult with recipe data, markdown, slug, source, and any validation errors
    """
    def notify(**event):
        if on_progress:
            on_progress(event)

    if not url and not text and not images:
        raise ValueError("Must provide a url, text, or images")

    # Get API key
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    # Create Gemini client
    client = genai.Client(api_key=api_key)

    # Get recipe content
    if images:
        source = f"photo ({len(images)} image{'s' if len(images) != 1 else ''})"
        content = text or ""
    elif url:
        source = url
        try:
            content = _extract_main_content(_fetch_url(url))
        except ValueError:
            logger.info("Direct fetch of %s failed; reading it with Gemini URL context", url)
            notify(type="fetch_fallback", max_attempts=MAX_RETRIES)
            content = _read_url_with_gemini(client, url)
        logger.debug(f"Fetched content from URL {url}: Length: {len(content)}")
    else:
        source = "pasted text"
        content = text
        logger.debug(f"Using provided text content. Length: {len(content)}")

    # Retry loop with validation
    feedback = None
    last_error = None

    for attempt in range(MAX_RETRIES):
        attempt_num = attempt + 1
        logger.info(f"Extraction attempt {attempt_num}/{MAX_RETRIES}")
        notify(type="attempt_start", attempt=attempt_num, max_attempts=MAX_RETRIES)

        try:
            # Call Gemini
            result = _extract_with_gemini(client, content, feedback, images=images)

            logger.debug("Received text response from Gemini API")
            logger.debug("=" * 50)
            logger.debug(result)

            # Parse response
            yaml_match = re.search(r'---YAML---(.*?)---MARKDOWN---', result, re.DOTALL)
            markdown_match = re.search(r'---MARKDOWN---(.*)', result, re.DOTALL)

            if not yaml_match or not markdown_match:
                feedback = "Response format invalid - missing YAML or MARKDOWN sections. Make sure to include both ---YAML--- and ---MARKDOWN--- markers."
                last_error = ValueError("Response format invalid")
                notify(type="retry", attempt=attempt_num, max_attempts=MAX_RETRIES, reason=feedback)
                continue

            yaml_text = yaml_match.group(1).strip()
            markdown_text = markdown_match.group(1).strip()

            # Parse YAML
            try:
                recipe_dict = yaml.safe_load(yaml_text)
            except yaml.YAMLError as e:
                feedback = f"YAML parsing failed: {e}\n\nMake sure the YAML is properly formatted with correct indentation."
                last_error = e
                notify(type="retry", attempt=attempt_num, max_attempts=MAX_RETRIES, reason=feedback)
                continue

            # Validate
            validation_errors = _validate_recipe(recipe_dict, yaml_text, markdown_text)

            if validation_errors:
                logger.warning(f"Validation failed with {len(validation_errors)} errors")
                feedback = _format_validation_errors(validation_errors)
                last_error = ValueError(f"Validation failed: {validation_errors}")

                # On last attempt, return with errors
                if attempt == MAX_RETRIES - 1:
                    logger.error("Max retries reached, returning with validation errors")
                    notify(type="giving_up", attempt=attempt_num, max_attempts=MAX_RETRIES, errors=_err_dicts(validation_errors))
                    # Try to create RecipeData anyway for partial data
                    try:
                        recipe_data = RecipeData(**recipe_dict)
                        slug = _generate_slug(recipe_data.name)
                        return ImportResult(
                            recipe_data=recipe_data,
                            markdown=markdown_text,
                            slug=slug,
                            source=source,
                            validation_errors=validation_errors
                        )
                    except Exception:
                        # Can't even construct partial data
                        raise ValueError(f"Failed after {MAX_RETRIES} attempts: {_format_validation_errors(validation_errors)}")

                notify(type="validation_failed", attempt=attempt_num, max_attempts=MAX_RETRIES, errors=_err_dicts(validation_errors))
                continue

            # Success! Create RecipeData
            recipe_data = RecipeData(**recipe_dict)
            slug = _generate_slug(recipe_data.name)

            logger.info("Recipe extraction successful")
            notify(type="success", attempt=attempt_num, max_attempts=MAX_RETRIES)
            return ImportResult(
                recipe_data=recipe_data,
                markdown=markdown_text,
                slug=slug,
                source=source,
                validation_errors=[]
            )

        except Exception as e:
            logger.error(f"Attempt {attempt_num} failed: {e}")
            last_error = e
            # Over quota or overloaded even after model fallback: retrying only burns quota.
            if getattr(e, "code", None) in RETRYABLE:
                notify(type="failed", attempt=attempt_num, max_attempts=MAX_RETRIES, reason=friendly_error(e))
                raise ValueError(friendly_error(e))

            if attempt < MAX_RETRIES - 1:
                feedback = f"Extraction failed: {e}\n\nPlease try again and ensure all required fields are present."
                notify(type="retry", attempt=attempt_num, max_attempts=MAX_RETRIES, reason=str(e))
            else:
                notify(type="failed", attempt=attempt_num, max_attempts=MAX_RETRIES, reason=str(e))
                raise ValueError(f"Failed to extract recipe after {MAX_RETRIES} attempts: {e}")

    # Should not reach here, but just in case
    raise last_error or ValueError("Extraction failed for unknown reason")

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Extract recipe data using Gemini API")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="URL to extract recipe from")
    group.add_argument("--text", help="Text containing recipe to extract")
    parser.add_argument("--api-key", help="Gemini API key (defaults to GEMINI_API_KEY env var)")
    parser.add_argument("--verbose", '-v', action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('[%(name)s][%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    logger.propagate = False

    logger.debug("Starting recipe extraction with args: %s", args)
    try:
        result = extract_recipe(url=args.url, text=args.text, api_key=args.api_key)

        if result.validation_errors:
            print("\n⚠ WARNING: Recipe extracted with validation errors:")
            for err in result.validation_errors:
                print(f"  - {err.field}: {err.message}")

        print("\nExtracted Recipe Data:")
        print(result.recipe_data)
        print("\nMarkdown:")
        print(result.markdown)
        print("\nSlug:", result.slug)
        print("Source:", result.source)
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
