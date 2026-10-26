"""
RAG evaluation for LexMind AI.

Ingests a synthetic corpus (a 5-page NDA and a 4-page services agreement with
deliberately similar clauses) into a throw-away vector store, then asks the
questions in golden.json — each worded differently from the source text — and
checks whether the right document AND page come back.

Retrieval (offline, no API keys), compared across retrievers:
  dense    embeddings only (ONNX MiniLM)
  sparse   BM25 keywords only
  hybrid   both, fused with Reciprocal Rank Fusion (what the app uses)
  rerank   hybrid + Cohere rerank (only with --rerank; calls Cohere)

  hit@1 / hit@3 / hit@5  share of questions whose expected (file, page) is in the top k
  MRR                    mean reciprocal rank of the first matching chunk

Answers (with --llm, calls Groq via the real document agent):
  citation hit           answer cites the expected file and page
  citation precision     share of cited (file, page) pairs that are the expected one
  keyword recall         answer contains the expected facts

Usage (from backend/):
  python -m eval.run_eval                  # retrieval ablation only
  python -m eval.run_eval --rerank --llm   # + Cohere rerank + answer quality
  python -m eval.run_eval --json out.json  # also write raw results
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402,F401 — loads backend/.env (API keys)

# Use a throw-away vector store (the client is created lazily, so this wins)
os.environ["CHROMA_PERSIST_PATH"] = tempfile.mkdtemp(prefix="lexmind_eval_")

from eval.corpus import DOCUMENTS, build_pdf  # noqa: E402
from rag import reranker  # noqa: E402
from rag.ingestion import ingest_document  # noqa: E402
from rag.retrieval import hybrid_retrieve  # noqa: E402

_CITATION = re.compile(r"\[Source:\s*(.+?),\s*Page\s*(\d+)\]", re.IGNORECASE)
_TOP = 5
_RERANK_POOL = 20


def _rank(chunks: list[dict], target: tuple[str, int]) -> int | None:
    for rank, chunk in enumerate(chunks, start=1):
        if (chunk["filename"], chunk["page_number"]) == target:
            return rank
    return None


def _metrics(ranks: list[int | None]) -> dict:
    n = len(ranks)
    return {
        "hit@1": sum(r == 1 for r in ranks) / n,
        "hit@3": sum(r is not None and r <= 3 for r in ranks) / n,
        "hit@5": sum(r is not None for r in ranks) / n,
        "mrr": sum(1 / r for r in ranks if r) / n,
    }


def _ingest_corpus(case_id: str) -> int:
    folder = Path(tempfile.mkdtemp())
    chunks = 0
    for filename, pages in DOCUMENTS.items():
        pdf = build_pdf(folder / filename, pages)
        chunks += ingest_document(str(pdf), case_id, str(uuid.uuid4()), filename=filename)["chunks_stored"]
    return chunks


def evaluate(use_rerank: bool, with_llm: bool) -> dict:
    golden = json.loads((Path(__file__).parent / "golden.json").read_text(encoding="utf-8"))
    case_id = str(uuid.uuid4())
    chunks_indexed = _ingest_corpus(case_id)

    modes = ["dense", "sparse", "hybrid"] + (["rerank"] if use_rerank else [])
    rows = []
    for item in golden:
        target = (item["file"], item["page"])
        row: dict = {"question": item["question"], "expected": f"{item['file']} p{item['page']}", "ranks": {}}
        for mode in modes:
            start = time.perf_counter()
            if mode == "rerank":
                pool = hybrid_retrieve(item["question"], case_id, top_k=_RERANK_POOL)
                top = reranker.rerank(item["question"], pool, top_n=_TOP)
            else:
                top = hybrid_retrieve(item["question"], case_id, top_k=_TOP, mode=mode)  # type: ignore[arg-type]
            row["ranks"][mode] = _rank(top, target)
            row.setdefault("ms", {})[mode] = round((time.perf_counter() - start) * 1000)

        if with_llm:
            from agents import document_agent

            answer = document_agent.run(item["question"], case_id).get("answer", "")
            cited = {(f.strip(), int(p)) for f, p in _CITATION.findall(answer)}
            row.update(
                answer=answer,
                cited=sorted(f"{f} p{p}" for f, p in cited),
                citation_hit=target in cited,
                citation_precision=(1 / len(cited)) if target in cited else 0.0,
                keyword_recall=sum(k.lower() in answer.lower() for k in item["keywords"]) / len(item["keywords"]),
            )
        rows.append(row)

    n = len(rows)
    summary: dict = {
        "questions": n,
        "documents": len(DOCUMENTS),
        "chunks_indexed": chunks_indexed,
        "retrieval": {
            mode: {
                **_metrics([r["ranks"][mode] for r in rows]),
                "avg_ms": round(sum(r["ms"][mode] for r in rows) / n),
            }
            for mode in modes
        },
    }
    if with_llm:
        summary["answers"] = {
            key: sum(r[key] for r in rows) / n
            for key in ("citation_hit", "citation_precision", "keyword_recall")
        }
    return {"summary": summary, "rows": rows}


def _print_report(result: dict) -> None:
    s = result["summary"]
    print(f"\nLexMind RAG eval — {s['questions']} questions over {s['documents']} documents "
          f"({s['chunks_indexed']} chunks), top {_TOP}\n")
    print("| Retriever | hit@1 | hit@3 | hit@5 | MRR | avg ms |")
    print("|---|---|---|---|---|---|")
    for mode, m in s["retrieval"].items():
        print(f"| {mode} | {m['hit@1']:.2f} | {m['hit@3']:.2f} | {m['hit@5']:.2f} | {m['mrr']:.2f} | {m['avg_ms']} |")

    if "answers" in s:
        print("\n| Answer metric | Score |\n|---|---|")
        for key, value in s["answers"].items():
            print(f"| {key} | {value:.2f} |")

    best = "rerank" if "rerank" in s["retrieval"] else "hybrid"
    misses = [r for r in result["rows"] if r["ranks"][best] != 1]
    if misses:
        print(f"\nNot ranked first by {best}:")
        for r in misses:
            print(f"  - {r['question']}  expected {r['expected']}, ranks {r['ranks']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rerank", action="store_true", help="also evaluate Cohere reranking (calls Cohere)")
    parser.add_argument("--llm", action="store_true", help="also evaluate answers (calls Groq)")
    parser.add_argument("--json", type=Path, help="write full results to this file")
    args = parser.parse_args()

    if args.rerank and not os.getenv("COHERE_API_KEY"):
        sys.exit("--rerank needs COHERE_API_KEY (set it in backend/.env)")
    if args.llm and not os.getenv("GROQ_API_KEY"):
        sys.exit("--llm needs GROQ_API_KEY (set it in backend/.env)")
    if not args.rerank:
        # Keep the run offline: the reranker falls back to retrieval order
        reranker._COHERE_API_KEY = ""
        reranker._client = None

    result = evaluate(args.rerank, args.llm)
    _print_report(result)
    if args.json:
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
