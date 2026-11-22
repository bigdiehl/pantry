#!/usr/bin/env python3
"""
List available Gemini models and test connectivity.

Usage:
    export GEMINI_API_KEY="your-key-here"
    uv run python scripts/list_gemini_models.py

Or to test a specific model:
    uv run python scripts/list_gemini_models.py --test gemini-2.5-flash
"""

import argparse
import os
import sys
from google import genai


def list_models(api_key: str, verbose: bool = False):
    """List all available Gemini models."""
    try:
        client = genai.Client(api_key=api_key)

        print("=" * 70)
        print("Available Gemini Models")
        print("=" * 70)

        models = list(client.models.list())

        if not models:
            print("No models found.")
            return []

        # Group models by type
        text_models = []
        embedding_models = []
        image_models = []
        other_models = []

        for model in models:
            name = model.name
            if 'embedding' in name.lower():
                embedding_models.append(name)
            elif 'imagen' in name.lower() or 'veo' in name.lower():
                image_models.append(name)
            elif any(x in name.lower() for x in ['gemini', 'gemma']):
                text_models.append(name)
            else:
                other_models.append(name)

        if text_models:
            print("\n📝 Text Generation Models:")
            for name in sorted(text_models):
                print(f"  • {name}")

        if embedding_models:
            print("\n🔢 Embedding Models:")
            for name in sorted(embedding_models):
                print(f"  • {name}")

        if image_models:
            print("\n🖼️  Image/Video Models:")
            for name in sorted(image_models):
                print(f"  • {name}")

        if other_models:
            print("\n🔧 Other Models:")
            for name in sorted(other_models):
                print(f"  • {name}")

        print(f"\n📊 Total: {len(models)} models available")
        print("=" * 70)

        if verbose:
            print("\n📋 Detailed Information:")
            for model in models[:5]:  # Show details for first 5
                print(f"\n  Model: {model.name}")
                if hasattr(model, 'display_name'):
                    print(f"    Display: {model.display_name}")
                if hasattr(model, 'description'):
                    print(f"    Description: {model.description[:100]}...")
                if hasattr(model, 'supported_generation_methods'):
                    print(f"    Methods: {model.supported_generation_methods}")

        return text_models

    except Exception as e:
        print(f"❌ Error listing models: {e}")
        return []


def test_model(api_key: str, model_name: str):
    """Test a specific model with a simple generation."""
    try:
        client = genai.Client(api_key=api_key)

        print(f"\n🧪 Testing model: {model_name}")
        print("-" * 70)

        response = client.models.generate_content(
            model=model_name,
            contents="Say 'Hello from Gemini!' in a friendly way."
        )

        print(f"✅ Success! Model is working.")
        print(f"\nResponse: {response.text}")
        print("-" * 70)
        return True

    except Exception as e:
        print(f"❌ Error testing model: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="List and test Gemini API models",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--test',
        metavar='MODEL',
        help='Test a specific model (e.g., gemini-2.5-flash)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed model information'
    )
    parser.add_argument(
        '--recommended',
        action='store_true',
        help='Show recommended models for recipe extraction'
    )

    args = parser.parse_args()

    # Get API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export GEMINI_API_KEY='your-key-here'")
        sys.exit(1)

    # List models
    text_models = list_models(api_key, verbose=args.verbose)

    # Show recommendations
    if args.recommended and text_models:
        print("\n💡 Recommended Models for Recipe Extraction:")
        recommended = [
            ('gemini-2.5-flash', 'Fast and efficient (CURRENT)'),
            ('gemini-2.5-pro', 'More accurate, slower'),
            ('gemini-flash-latest', 'Always latest flash version'),
        ]
        for model, desc in recommended:
            available = any(model in m for m in text_models)
            status = "✅" if available else "❌"
            print(f"  {status} {model:30s} - {desc}")

    # Test specific model if requested
    if args.test:
        test_model(api_key, args.test)


if __name__ == "__main__":
    main()
