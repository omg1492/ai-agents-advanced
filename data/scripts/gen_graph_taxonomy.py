"""Generate taxonomy (Category & Cuisine) concepts and product assignments via LLM.

Pipeline Goals (Phase L04):
 1. Derive ~50 Category concepts and ~20 Cuisine concepts from existing product catalog.
 2. Produce concise description for each concept.
 3. Assign each product (by product_id) to 1..N categories (typically 1-3) and 0..2 cuisines.
 4. Persist results in an idempotent, resumable fashion to avoid re‑paying token costs.
 5. Provide progress & token usage reporting (input + output tokens) and ETA estimation.

Output Artifacts (all under ../processed):
  - taxonomy_concepts.parquet : rows (kind: 'category'|'cuisine', code, name, description)
  - taxonomy_assignments.parquet : rows (product_id, category_codes[list[str]], cuisine_codes[list[str]])
  - taxonomy_state.json : state & token accounting for resuming (concepts + partial batches)

Resumable Strategy:
  - Step A (concept synthesis) stored once; if present in state file, we reuse.
  - Step B (batch product assignment) processes products in deterministic batches (default 40 products)
    and stores a checkpoint after every successful LLM call.
  - On restart, incomplete batches are retried; completed batches skipped.

Token Accounting:
  - Each LLM call returns usage (prompt_tokens, completion_tokens, total_tokens) when available.
  - Aggregate per stage; stored in state. If provider does not return usage, values remain None.

LLM Call Design:
  - Larger context approach: Provide the full list of synthesized concepts (categories + cuisines)
    with their descriptions per batch assignment call; restrict number of product descriptions per call
    (batch_size) to balance quality vs. context limits.
  - Uses a single "medium reasoning" model for controllable cost (model name from OPENAI_MODEL or fallback).

Environment Variables:
  OPENAI_API_KEY (required) unified OpenAI / Azure
  OPENAI_BASE_URL (optional; Azure endpoint ending with /openai/v1/ )
  OPENAI_API_VERSION (optional; Azure API version)
  OPENAI_MODEL (optional; default gpt-4o-mini or similar)  # deliberately not a very large expensive model
  TAXONOMY_BATCH_SIZE (optional; default 40)
  TAXONOMY_STATE_PATH (optional; default ../processed/taxonomy_state.json)
  TAXONOMY_FORCE_REGENERATE_CONCEPTS=true to ignore existing concepts

CLI:
  uv run python data/scripts/gen_graph_taxonomy.py            # normal (resume if state exists)
  uv run python data/scripts/gen_graph_taxonomy.py --rebuild-concepts  # force concepts regeneration
  uv run python data/scripts/gen_graph_taxonomy.py --batch-size 30

NOTE: Import into AGE graph will be a separate script (not implemented here per instructions).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI, APIStatusError, RateLimitError
 # tenacity no longer needed after refactor (structured parse without custom retry)
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ------------------------------- Data Structures ---------------------------------

@dataclass
class Concept:
    kind: str  # 'category' | 'cuisine'
    code: str
    name: str
    description: str

@dataclass
class AssignmentBatchResult:
    product_ids: List[str]
    category_codes: Dict[str, List[str]]  # product_id -> list of category codes
    cuisine_codes: Dict[str, List[str]]   # product_id -> list of cuisine codes
    usage: Optional[dict] = None

@dataclass
class State:
    concepts: List[Concept]
    completed_batches: int
    total_batches: int
    batch_size: int
    product_ids: List[str]
    token_usage: Dict[str, Dict[str, int]]  # stage -> {prompt, completion, total}


# ------------------------------- OpenAI Helpers ----------------------------------

def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in (429, 500, 502, 503, 504)
    return False


def _init_client() -> tuple[OpenAI, str]:
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError('OPENAI_API_KEY not set')
    base_url = os.getenv('OPENAI_BASE_URL')
    api_version = os.getenv('OPENAI_API_VERSION') or '2024-10-21'
    model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    default_query = {'api-version': api_version} if base_url else None
    client = OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)
    return client, model


@dataclass
class _Unused:  # Placeholder to keep section header alignment (removed legacy _chat_json). 
    pass


# ------------------------------- Concept Generation ------------------------------

class ConceptItem(BaseModel):
    code: str = Field(..., description="Stable lower_snake_case code")
    name: str
    description: str


class ConceptResponse(BaseModel):
    categories: List[ConceptItem] = Field(..., min_length=30, max_length=60)
    cuisines: List[ConceptItem] = Field(..., min_length=10, max_length=30)


def _load_products() -> pd.DataFrame:
    # Prefer richer products parquet if present; fallback to simple_products
    base = Path(__file__).parent / '../processed'
    rich = (base / 'products.parquet').resolve()
    simple = (base / 'simple_products.parquet').resolve()
    path = rich if rich.exists() else simple
    if not path.exists():
        raise FileNotFoundError('No products parquet found (expected products.parquet or simple_products.parquet)')
    df = pd.read_parquet(path)
    # Expect columns product_id, product_name, product_description, producer_name
    # Normalize some possible alternate names
    rename_map = {}
    if 'id' in df.columns and 'product_id' not in df.columns:
        rename_map['id'] = 'product_id'
    if rename_map:
        df = df.rename(columns=rename_map)
    needed = {'product_id', 'product_name'}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f'Missing required columns in product parquet: {missing}')
    return df


def _generate_concepts(client: OpenAI, model: str, products_df: pd.DataFrame) -> tuple[List[Concept], dict]:
    sample_rows = products_df.sample(n=min(200, len(products_df)), random_state=42)
    # Pack concise lines to stay within context; avoid embedding full descriptions if huge.
    lines = []
    for _, r in sample_rows.iterrows():
        desc = (r.get('product_description') or '')
        if len(desc) > 140:  # keep snippet short
            desc = desc[:140].rsplit(' ', 1)[0] + '…'
        lines.append(f"{r['product_name']} :: {desc}")
    catalog_snippet = '\n'.join(lines)
    instructions = (
        "You are a food taxonomy expert. Derive concise, disjoint yet comprehensive product Categories (~50) and Cuisines (~20). "
        "Each has: stable lower_snake_case code, short human name, 1-2 sentence description. "
        "Avoid overlaps; ensure coverage across produce, proteins, dairy, grains, beverages, preserved goods, spices, regional traditions."
    )
    prompt_input = (
        "Sample product catalogue lines (name :: truncated description):\n" + catalog_snippet + "\n\n" +
        "Generate the taxonomy now."
    )
    resp = client.responses.parse(
        model=model,
        input=prompt_input,
        instructions=instructions,
        text_format=ConceptResponse,
    )
    parsed: ConceptResponse | None = getattr(resp, 'output_parsed', None)
    if not parsed:
        raise RuntimeError('Failed to parse taxonomy concepts output')
    usage_attr = getattr(resp, 'usage', None)
    usage: dict = {}
    if usage_attr:
        usage = {
            'prompt': getattr(usage_attr, 'prompt_tokens', None) or getattr(usage_attr, 'input_tokens', None),
            'completion': getattr(usage_attr, 'completion_tokens', None) or getattr(usage_attr, 'output_tokens', None),
        }
        if usage.get('prompt') is not None and usage.get('completion') is not None:
            usage['total'] = (usage['prompt'] or 0) + (usage['completion'] or 0)
    concepts: List[Concept] = []
    for c in parsed.categories:
        concepts.append(Concept(kind='category', code=c.code, name=c.name, description=c.description))
    for c in parsed.cuisines:
        concepts.append(Concept(kind='cuisine', code=c.code, name=c.name, description=c.description))
    return concepts, usage


# ------------------------------- Assignments --------------------------------------

class AssignmentItem(BaseModel):
    product_id: str
    categories: List[str] = Field(default_factory=list, max_length=5)
    cuisines: List[str] = Field(default_factory=list, max_length=3)


class AssignmentResponse(BaseModel):
    assignments: List[AssignmentItem]


def _concepts_markdown(concepts: Sequence[Concept]) -> str:
    lines = []
    for c in concepts:
        lines.append(f"[{c.kind.upper()}] {c.code} :: {c.name} :: {c.description[:160]}")
    return '\n'.join(lines)


def _assignment_call(client: OpenAI, model: str, concepts: Sequence[Concept], products: pd.DataFrame) -> AssignmentBatchResult:
    subset = products[['product_id', 'product_name', 'product_description']].copy()
    records = []
    for _, r in subset.iterrows():
        desc = (r.get('product_description') or '')
        if len(desc) > 220:
            desc = desc[:220].rsplit(' ', 1)[0] + '…'
        records.append(f"{r['product_id']} || {r['product_name']} || {desc}")
    products_block = '\n'.join(records)
    instructions = (
        'Assign each product to 0-3 precise category codes and 0-2 cuisine codes using ONLY the provided concept list. '
        'Return empty lists when no suitable concept applies. Prefer precision over recall. Use codes verbatim.'
    )
    assignment_input = (
        'Concept reference list (kind code name description):\n' + _concepts_markdown(concepts) + '\n\n' +
        'Products (product_id || name || description):\n' + products_block + '\n\n' +
        'Generate assignments now.'
    )
    resp = client.responses.parse(
        model=model,
        input=assignment_input,
        instructions=instructions,
        text_format=AssignmentResponse,
    )
    parsed: AssignmentResponse | None = getattr(resp, 'output_parsed', None)
    if not parsed:
        raise RuntimeError('Failed to parse assignment batch output')
    usage_attr = getattr(resp, 'usage', None)
    usage: dict = {}
    if usage_attr:
        usage = {
            'prompt': getattr(usage_attr, 'prompt_tokens', None) or getattr(usage_attr, 'input_tokens', None),
            'completion': getattr(usage_attr, 'completion_tokens', None) or getattr(usage_attr, 'output_tokens', None),
        }
        if usage.get('prompt') is not None and usage.get('completion') is not None:
            usage['total'] = (usage['prompt'] or 0) + (usage['completion'] or 0)
    product_ids: List[str] = []
    cat_map: Dict[str, List[str]] = {}
    cui_map: Dict[str, List[str]] = {}
    for item in parsed.assignments:
        pid = item.product_id
        product_ids.append(pid)
        cat_map[pid] = [c for c in item.categories if c]
        cui_map[pid] = [c for c in item.cuisines if c]
    return AssignmentBatchResult(product_ids=product_ids, category_codes=cat_map, cuisine_codes=cui_map, usage=usage)


# ------------------------------- State Persistence --------------------------------

def _load_state(path: Path) -> Optional[State]:
    if not path.exists():
        return None
    with path.open('r', encoding='utf-8') as f:
        raw = json.load(f)
    concepts = [Concept(**c) for c in raw['concepts']]
    return State(
        concepts=concepts,
        completed_batches=raw['completed_batches'],
        total_batches=raw['total_batches'],
        batch_size=raw['batch_size'],
        product_ids=raw['product_ids'],
        token_usage=raw.get('token_usage', {}),
    )


def _save_state(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serial = asdict(state)
    serial['concepts'] = [asdict(c) for c in state.concepts]
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(serial, f, indent=2)
    tmp.replace(path)


def _accumulate_usage(state: State, stage: str, usage: dict) -> None:
    if not usage:
        return
    stage_totals = state.token_usage.setdefault(stage, {'prompt': 0, 'completion': 0, 'total': 0})
    for k in ('prompt', 'completion', 'total'):
        if usage.get(k) is not None:
            stage_totals[k] += usage[k]


# ------------------------------- Main Orchestration -------------------------------

def _estimate_eta(done_batches: int, total_batches: int, start_ts: float, now_ts: float) -> str:
    if done_batches == 0:
        return 'n/a'
    elapsed = now_ts - start_ts
    per = elapsed / done_batches
    remaining = (total_batches - done_batches) * per
    return f"~{remaining/60:.1f}m remaining" if remaining > 90 else f"~{int(remaining)}s remaining"


def run(rebuild_concepts: bool, batch_size_cli: Optional[int]) -> bool:
    client, model = _init_client()
    products_df = _load_products()
    batch_size = int(os.getenv('TAXONOMY_BATCH_SIZE', str(batch_size_cli or 40)))
    state_path = Path(os.getenv('TAXONOMY_STATE_PATH', str((Path(__file__).parent / '../processed/taxonomy_state.json').resolve())))

    state = _load_state(state_path)
    if state and batch_size_cli and batch_size_cli != state.batch_size:
        logger.warning('Ignoring --batch-size change; existing state locked to %d', state.batch_size)
    if state and rebuild_concepts:
        logger.info('Rebuild concepts requested; discarding previous concept state.')
        state = None

    if state is None:
        logger.info('No prior state – generating concepts...')
        concepts, usage = _generate_concepts(client, model, products_df)
        total_products = len(products_df)
        total_batches = math.ceil(total_products / batch_size)
        state = State(
            concepts=concepts,
            completed_batches=0,
            total_batches=total_batches,
            batch_size=batch_size,
            product_ids=products_df['product_id'].tolist(),
            token_usage={},
        )
        _accumulate_usage(state, 'concept_generation', usage)
        _save_state(state_path, state)
        logger.info('Generated %d concepts (%d categories + %d cuisines).',
                    len([c for c in concepts if c.kind == 'category']),
                    len([c for c in concepts if c.kind == 'cuisine']),
                    len(concepts))
    else:
        logger.info('Loaded existing state: %d/%d batches complete', state.completed_batches, state.total_batches)

    # Persist concepts parquet immediately (idempotent)
    concepts_out = (Path(__file__).parent / '../processed/taxonomy_concepts.parquet').resolve()
    if not concepts_out.exists():
        pd.DataFrame([asdict(c) for c in state.concepts]).to_parquet(concepts_out, index=False)
        logger.info('Wrote concepts parquet: %s', concepts_out)

    # Prepare assignment accumulation (we might resume mid-way)
    assignments_out = (Path(__file__).parent / '../processed/taxonomy_assignments.parquet').resolve()
    if assignments_out.exists() and state.completed_batches == state.total_batches:
        logger.info('Assignments already completed previously. Nothing to do.')
        return True

    # If partial output exists but not complete, we will rebuild from scratch by recomputing completed batches ->
    # simpler than merging; but to avoid re-token costs we rely on state to skip calling LLM again. So we only
    # append new batches. We'll aggregate in memory then write final parquet at end.
    assigned_products = set()
    existing_rows: List[dict] = []
    if assignments_out.exists():
        try:
            df_existing = pd.read_parquet(assignments_out)
            for _, row in df_existing.iterrows():
                assigned_products.add(row['product_id'])
                existing_rows.append({
                    'product_id': row['product_id'],
                    'category_codes': row['category_codes'],
                    'cuisine_codes': row['cuisine_codes']
                })
            logger.info('Loaded %d existing assignment rows', len(existing_rows))
        except Exception:
            logger.warning('Failed reading existing assignments parquet – will recreate at end.')

    # Determine which product ids still require assignment (skip previously written ones to allow safe resume)
    remaining_product_ids = [pid for pid in state.product_ids if pid not in assigned_products]
    if remaining_product_ids:
        logger.info('%d products pending assignment (batch size %d)', len(remaining_product_ids), state.batch_size)
    else:
        logger.info('No remaining products; ensuring final parquet is present.')
        if not assignments_out.exists():
            pd.DataFrame(existing_rows).to_parquet(assignments_out, index=False)
        return True

    import time
    start_ts = time.time()
    for batch_index, start in enumerate(range(0, len(remaining_product_ids), state.batch_size), start=1):
        group = remaining_product_ids[start:start + state.batch_size]
        batch_df = products_df[products_df['product_id'].isin(group)].copy()
        result = _assignment_call(client, model, state.concepts, batch_df)
        _accumulate_usage(state, 'assignment', result.usage or {})
        # Append rows
        for pid in result.product_ids:
            existing_rows.append({
                'product_id': pid,
                'category_codes': result.category_codes.get(pid, []),
                'cuisine_codes': result.cuisine_codes.get(pid, []),
            })
        # Update state counters
        state.completed_batches += 1
        _save_state(state_path, state)
        elapsed_now = time.time()
        eta = _estimate_eta(state.completed_batches, state.total_batches, start_ts, elapsed_now)
        logger.info('Batch %d/%d done (products %d-%d). ETA %s',
                    state.completed_batches, state.total_batches, start + 1, start + len(group), eta)
    # Write final assignments parquet deterministically sorted
    assign_df = pd.DataFrame(existing_rows)
    assign_df = assign_df.sort_values('product_id').reset_index(drop=True)
    assign_df.to_parquet(assignments_out, index=False)
    logger.info('Wrote %d assignment rows to %s', len(assign_df), assignments_out)
    # Final state save
    _save_state(state_path, state)
    total_prompt = state.token_usage.get('concept_generation', {}).get('prompt', 0) + state.token_usage.get('assignment', {}).get('prompt', 0)
    total_completion = state.token_usage.get('concept_generation', {}).get('completion', 0) + state.token_usage.get('assignment', {}).get('completion', 0)
    logger.info('Token usage cumulative prompt=%s completion=%s total=%s',
                total_prompt, total_completion, total_prompt + total_completion)
    return True


def main() -> bool:
    parser = argparse.ArgumentParser(description='Generate taxonomy concepts & assignments (resumable).')
    parser.add_argument('--rebuild-concepts', action='store_true', help='Ignore prior concepts and regenerate (will re-cost).')
    parser.add_argument('--batch-size', type=int, help='Override batch size (only on first run).')
    args = parser.parse_args()
    try:
        env_force = os.getenv('TAXONOMY_FORCE_REGENERATE_CONCEPTS', '').lower() in ('1', 'true', 'yes')
        rebuild = args.rebuild_concepts or env_force
        return run(rebuild_concepts=rebuild, batch_size_cli=args.batch_size)
    except Exception as e:  # noqa: BLE001 (broad for CLI boundary)
        logger.exception('Taxonomy generation failed: %s', e)
        return False


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(0 if main() else 1)
