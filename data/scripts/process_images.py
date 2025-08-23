"""Process images to infer product name and description using vision-capable model.

Behavior:
1. Loads unified OpenAI/Azure configuration from `.env` (same folder).
2. Resolves images directory from env `IMAGES_INPUT_DIR` or default `../images`.
3. Iterates supported image files (jpg, jpeg, png, webp, gif) and sends each with a prompt
   to the Chat Completions (beta parse) API requesting structured output.
4. Prints per-image blocks plus a final consolidated summary.

Run:
  uv run process_images.py

Environment:
  OPENAI_API_KEY (required)
  OPENAI_MODEL (default gpt-5)
  OPENAI_BASE_URL / OPENAI_API_VERSION (Azure)
  IMAGES_INPUT_DIR (optional)
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


class ImageProductSummary(BaseModel):
    """Structured response for a single image."""

    product_name: str = Field(..., description="Concise product name inferred from the image")
    short_description: str = Field(
        ..., description="2-3 sentence vivid, grounded description (appearance, likely usage, qualities)"
    )


def build_client() -> tuple[OpenAI, str]:
    """Initialize OpenAI client supporting Azure variant via unified env vars."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY missing")
    base_url = os.getenv("OPENAI_BASE_URL")
    api_version = os.getenv("OPENAI_API_VERSION") or "2024-10-21"
    model = os.getenv("OPENAI_MODEL", "gpt-5")
    default_query = {"api-version": api_version} if base_url else None
    client = OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)
    return client, model


def encode_image_b64(path: Path) -> str:
    """Return data URI base64 string for a local image file."""
    mime = "image/jpeg"
    ext = path.suffix.lower()
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    elif ext == ".gif":
        mime = "image/gif"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def summarize_image(client: OpenAI, model: str, path: Path) -> Dict[str, Any]:
    """Send image + prompt to model and return structured summary."""
    data_uri = encode_image_b64(path)
    system_prompt = (
        "You identify farm or food-related products from images. Provide a concise product name and a grounded description."
        " Don't speculate beyond visible cues; if uncertain choose the most plausible concise name."
    )
    user_instruction = (
        "Analyze this product image and extract: product_name (concise) and short_description (2-3 sentences)"
        " focusing on notable visual attributes (color, texture, form, packaging) and likely culinary or usage context."
    )

    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_instruction},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
        response_format=ImageProductSummary,
    )
    parsed: ImageProductSummary = response.choices[0].message.parsed  # type: ignore[attr-defined]
    return parsed.model_dump()


def print_block(title: str, body: str) -> None:
    line = "=" * 90
    print(f"\n{line}\n{title}\n{line}\n{body}\n{line}\n")


def main() -> int:
    try:
        client, model = build_client()
        base_dir = Path(__file__).parent
        images_dir = Path(os.getenv("IMAGES_INPUT_DIR") or (base_dir / "../images").resolve())
        if not images_dir.exists():
            raise FileNotFoundError(f"Images directory not found: {images_dir}")
        files = [p for p in sorted(images_dir.iterdir()) if p.suffix.lower() in SUPPORTED_EXT and p.is_file()]
        if not files:
            print(f"No supported image files in {images_dir}")
            return 0
        summaries: List[Dict[str, Any]] = []
        for img in files:
            print_block("PROCESSING IMAGE", f"File: {img.name}")
            try:
                summary = summarize_image(client, model, img)
                body = (
                    f"Product Name: {summary['product_name']}\n\n"
                    f"Description:\n{summary['short_description']}"
                )
                print_block("LLM SUMMARY", body)
                summaries.append({"file": img.name, **summary})
            except Exception as e:  # continue on error
                print_block("ERROR", f"Failed processing {img.name}: {e}")
        if summaries:
            lines = []
            for i, s in enumerate(summaries, start=1):
                lines.append(
                    f"{i}. {s['product_name']} (source: {s['file']})\n"
                    f"   {s['short_description'].strip()}\n"
                )
            print_block("CONSOLIDATED IMAGE PRODUCT SUMMARIES", "\n".join(lines))
        return 0
    except Exception as outer:
        print(f"Fatal error: {outer}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
