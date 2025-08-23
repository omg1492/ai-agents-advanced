"""Process PDFs to extract Markdown and summarize product info.

Single-file utility that:
1. Loads configuration from `.env` (in the same folder) using unified OpenAI env vars.
2. Resolves an input folder containing PDFs (env `PDF_INPUT_DIR` or default `../PDFs`).
3. Iterates all `*.pdf` files, converts each to Markdown via the `markitdown` library.
4. Sends the Markdown to the OpenAI Responses API (works with OpenAI or Azure OpenAI
   through unified configuration) asking for:
	  - product_name: concise inferred product name
	  - short_description: 2–3 sentence friendly description grounded ONLY in the PDF text
5. Prints a clearly delimited block for each file with extracted Markdown (truncated for readability)
   and the model-derived name + description.

Environment variables (already used elsewhere in repo):
  OPENAI_API_KEY          (required)
  OPENAI_MODEL            (default: gpt-5)
  OPENAI_BASE_URL         (Azure style endpoint ending with /openai/v1/)
  OPENAI_API_VERSION      (Azure API version, e.g. 2024-10-21 or preview)
  PDF_INPUT_DIR           (optional override path to PDFs)

Run:
  uv run process_pdfs.py
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from markitdown import MarkItDown


class ProductSummary(BaseModel):
	"""Structured response schema for model output."""

	product_name: str = Field(..., description="Concise product name inferred from the PDF")
	short_description: str = Field(
		..., description="2-3 sentence friendly description grounded ONLY in the PDF content"
	)


def build_client() -> tuple[OpenAI, str]:
	"""Build a unified OpenAI client (supports OpenAI & Azure) and resolve model name."""
	load_dotenv()
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise ValueError("OPENAI_API_KEY missing in environment")

	base_url = os.getenv("OPENAI_BASE_URL")
	api_version = os.getenv("OPENAI_API_VERSION") or "2024-10-21"
	model = os.getenv("OPENAI_MODEL", "gpt-5")

	default_query = {"api-version": api_version} if base_url else None
	client = OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)
	return client, model


def extract_markdown(pdf_path: Path) -> str:
	"""Convert a single PDF to Markdown text."""
	md = MarkItDown()
	result = md.convert(pdf_path)
	# markitdown returns an object with .text / .markdown depending on version; handle both.
	content = getattr(result, "text", None) or getattr(result, "markdown", "")
	return content or ""


def summarize_pdf(client: OpenAI, model: str, markdown: str) -> Dict[str, Any]:
	"""Call Responses API to extract product name & description using structured output.

	No truncation is applied; full Markdown is sent.
	"""
	system_prompt = (
		"You extract concise product metadata from PDF-derived Markdown."
		" Respond ONLY with grounded facts—never invent content."
	)
	user_prompt = textwrap.dedent(
		f"""
		From the following FULL Markdown extracted from a product PDF, infer:
		- product_name (concise)
		- short_description (2-3 sentences, friendly, grounded ONLY in the text)

		Markdown:
		---
		{markdown}
		---
		"""
	).strip()

	response = client.beta.chat.completions.parse(
		model=model,
		messages=[
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": user_prompt},
		],
		response_format=ProductSummary
	)
	parsed: ProductSummary = response.choices[0].message.parsed  # type: ignore[attr-defined]
	return parsed.model_dump()


def print_block(title: str, body: str) -> None:
	"""Pretty-print a delimited block to the console."""
	line = "=" * 90
	print(f"\n{line}\n{title}\n{line}\n{body}\n{line}\n")


def main() -> int:
	"""Entrypoint: process all PDFs and print summaries."""
	try:
		client, model = build_client()
		base_dir = Path(__file__).parent
		input_dir = os.getenv("PDF_INPUT_DIR") or str((base_dir / "../PDFs").resolve())
		pdf_dir = Path(input_dir)
		if not pdf_dir.exists() or not pdf_dir.is_dir():
			raise FileNotFoundError(f"PDF directory not found: {pdf_dir}")

		pdf_files = sorted(p for p in pdf_dir.glob("*.pdf") if p.is_file())
		if not pdf_files:
			print(f"No PDF files found in {pdf_dir}")
			return 0

		all_summaries = []  # collect per-file summaries for final overview

		for pdf in pdf_files:
			print_block("PROCESSING", f"File: {pdf.name}")
			try:
				md = extract_markdown(pdf)
				if not md.strip():
					print("(Empty markdown extracted) Skipping model call.")
					continue
				# Print full markdown (no truncation as requested)
				print_block("MARKDOWN EXTRACT (full)", md)
				summary = summarize_pdf(client, model, md)
				summary_text = (
					f"Product Name: {summary['product_name']}\n\n"
					f"Description:\n{summary['short_description']}"
				)
				print_block("LLM SUMMARY", summary_text)
				all_summaries.append({
					"file": pdf.name,
					"product_name": summary["product_name"],
					"short_description": summary["short_description"],
				})
			except Exception as e:  # Continue with next file
				print_block("ERROR", f"Failed processing {pdf.name}: {e}")

		# Final consolidated summary
		if all_summaries:
			lines = []
			for idx, item in enumerate(all_summaries, start=1):
				lines.append(
					f"{idx}. {item['product_name']} (source: {item['file']})\n"
					f"\n{item['short_description'].strip()}\n\n"
				)
			print_block("CONSOLIDATED PRODUCT SUMMARIES", "\n".join(lines))
		return 0
	except Exception as outer:
		print(f"Fatal error: {outer}", file=sys.stderr)
		return 1


if __name__ == "__main__":
	raise SystemExit(main())
