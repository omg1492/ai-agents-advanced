"""Generate generic first‑turn Q&A pairs for semantic caching.

This script uses the OpenAI Responses API with structured output (Pydantic
schema) and GPT‑5 (or the configured unified model) to synthesize 50 very
common, generic user questions and short neutral answers for the Dream Farm
assistant. The resulting dataset (``qna.json``) is intended for a *semantic
cache* that accelerates the very first user turn of a session.

Design constraints:
* Questions represent greetings, small talk, capability / help requests, and
  broad intent discovery ("help me find farm products"), but NEVER specific
  product, farmer, price, stock, certification, or allergen details.
* Answers are concise (1–3 sentences, <= ~260 chars), generic, and avoid
  hallucinating concrete catalog data. They encourage next clarifying steps.
* Exactly 50 unique question/answer pairs are produced.
* Embeddings (generated elsewhere) will be created from the question text.

Usage:
	uv run gen_qna.py

Output:
	../source_json/qna.json (array[ {"question": str, "answer": str}, ... ])
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


class QnAItem(BaseModel):
	"""Single generic question & answer pair.

	Question: realistic first message a user may send with no prior context.
	Answer: short neutral reply that does not invent specific product data.
	"""

	question: str = Field(..., description="Common initial user message (generic; no specific product names)")
	answer: str = Field(..., description="Short 1-3 sentence neutral answer inviting next step")


class QnABatch(BaseModel):
	"""Container for structured output from the model."""

	items: List[QnAItem] = Field(..., min_length=40, max_length=60, description="List of generic Q&A pairs (~50)")


def get_client() -> OpenAI:
	"""Instantiate the unified OpenAI client honoring Azure/OpenAI env vars."""

	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise ValueError("OPENAI_API_KEY not set")
	base_url = os.getenv("OPENAI_BASE_URL")
	default_query = {"api-version": os.getenv("OPENAI_API_VERSION", "preview")} if base_url else None
	return OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)


def generate_qna() -> list[dict]:
	"""Call the Responses API with structured parsing to produce Q&A items."""

	client = get_client()
	model = os.getenv("OPENAI_MODEL", "gpt-5")
	instructions = """You are generating a semantic cache seed for the Dream Farm AI assistant, a virtual farmers' marketplace helper.

Produce EXACTLY 50 UNIQUE generic (first-turn) user questions with concise neutral assistant answers.

Rules:
1. QUESTIONS MUST BE GENERIC: greetings, small talk, platform capability inquiries, help finding products (general), dietary / allergy inquiry (general), sustainability curiosity, pricing/how it works, seasonal availability (general), how to start, data privacy concern, supported languages, returning user intent, etc.
2. NO SPECIFIC product names, farmer names, prices, stock counts, certifications, allergens by name, or locations. Use only generic references (e.g., 'your products', 'local produce', 'seasonal items').
3. Keep question length 5-70 characters; natural conversational phrasing.
4. ANSWERS: 1-3 sentences, <= 260 characters, inviting next step or offering help; never invent catalog details, never claim an item is available, never list specific products.
5. Avoid duplicates or near-duplicates; vary phrasing categories.
6. Do not number the questions; provide them only as structured objects.
7. Tone: friendly, helpful, trustworthy, sustainable-food focused.
8. Answers may briefly mention we can look up products with search/RAG once the user asks something specific.

Return ONLY valid structured data for the provided schema.
"""

	response = client.responses.parse(
		model=model,
		input="Generate the semantic cache seed now.",
		instructions=instructions,
		text_format=QnABatch,
	)
	parsed: QnABatch | None = getattr(response, "output_parsed", None)
	if not parsed:
		raise RuntimeError("Model did not return parsable QnABatch")

	items = parsed.items
	return [it.model_dump() for it in items]


def write_output(data: list[dict]) -> Path:
	"""Persist Q&A list to ../source_json/qna.json."""

	out_path = Path("../source_json/qna.json")
	out_path.parent.mkdir(exist_ok=True)
	with out_path.open("w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)
	return out_path


def main() -> None:
	"""Entrypoint: load env, generate structured Q&A, write JSON file."""

	load_dotenv()

	qna = generate_qna()
	path = write_output(qna)
	print(f"✅ Generated {len(qna)} Q&A pairs -> {path}")


if __name__ == "__main__":  # pragma: no cover - manual execution script
	main()
