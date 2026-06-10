#!/usr/bin/env python3
"""
Đánh giá retrieval đơn giản — before/after khi pipeline đổi dữ liệu embed.

Không bắt buộc LLM: chỉ kiểm tra top-k chunk có chứa keyword kỳ vọng hay không
(tiếp nối tinh thần Day 08/09 nhưng tập trung data layer).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def _chat_completions_url(base_url: str) -> str:
    base = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _extract_json_object(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _llm_judge(
    *,
    question: Dict[str, Any],
    docs: List[str],
    metas: List[Dict[str, Any]],
    model: str,
    base_url: str,
    api_key: str,
    timeout: int,
    max_context_chars: int,
) -> Dict[str, str]:
    context_parts = []
    budget = max_context_chars
    for i, doc in enumerate(docs, 1):
        meta = metas[i - 1] if i - 1 < len(metas) and metas[i - 1] else {}
        text = (doc or "").replace("\n", " ").strip()
        if not text:
            continue
        take = text[:budget]
        budget -= len(take)
        context_parts.append(
            f"[{i}] doc_id={meta.get('doc_id', '')}; effective_date={meta.get('effective_date', '')}\n{take}"
        )
        if budget <= 0:
            break

    prompt = {
        "question": question.get("question", ""),
        "expected_any": question.get("must_contain_any", []),
        "forbidden": question.get("must_not_contain", []),
        "expected_top1_doc_id": question.get("expect_top1_doc_id", ""),
        "retrieved_context": "\n\n".join(context_parts),
    }
    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là LLM-judge cho retrieval eval. Chỉ dùng retrieved_context, "
                "không dùng kiến thức ngoài. Chấm xem context có đủ để trả lời đúng "
                "question, có chứa nội dung bị cấm không, và top-1 doc có hợp lý không. "
                "Trả về JSON thuần với keys: pass(boolean), score(0|1|2), "
                "reason(string <= 35 words), answer(string)."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(prompt, ensure_ascii=False),
        },
    ]
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _chat_completions_url(base_url),
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "day10-lab-llm-judge/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM judge HTTP {e.code}: {detail}") from e

    content = body["choices"][0]["message"]["content"]
    judged = _extract_json_object(content)
    return {
        "llm_judge_pass": "yes" if bool(judged.get("pass")) else "no",
        "llm_judge_score": str(judged.get("score", "")),
        "llm_judge_reason": str(judged.get("reason", "")).replace("\n", " "),
        "llm_judge_answer": str(judged.get("answer", "")).replace("\n", " "),
        "llm_judge_model": model,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--questions",
        default=str(ROOT / "data" / "test_questions.json"),
        help="JSON danh sách câu hỏi golden (retrieval)",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "eval" / "before_after_eval.csv"),
        help="CSV kết quả",
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Gọi OpenAI-compatible LLM judge và thêm cột llm_judge_* vào CSV.",
    )
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        help="Model dùng cho LLM judge; mặc định đọc OPENAI_MODEL.",
    )
    parser.add_argument(
        "--judge-base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="OpenAI-compatible base URL; mặc định đọc OPENAI_BASE_URL.",
    )
    parser.add_argument("--judge-timeout", type=int, default=60)
    parser.add_argument("--judge-max-context-chars", type=int, default=4000)
    args = parser.parse_args()

    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        print("Install: pip install chromadb sentence-transformers", file=sys.stderr)
        return 1

    qpath = Path(args.questions)
    if not qpath.is_file():
        print(f"questions not found: {qpath}", file=sys.stderr)
        return 1

    questions = json.loads(qpath.read_text(encoding="utf-8"))
    api_key = os.environ.get("OPENAI_API_KEY", "").strip().strip('"').strip("'")
    if args.llm_judge and not api_key:
        print("OPENAI_API_KEY is required when using --llm-judge", file=sys.stderr)
        return 3

    db_path = os.environ.get("CHROMA_DB_PATH", str(ROOT / "chroma_db"))
    collection_name = os.environ.get("CHROMA_COLLECTION", "day10_kb")
    model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path=db_path)
    emb = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    try:
        col = client.get_collection(name=collection_name, embedding_function=emb)
    except Exception as e:
        print(f"Collection error: {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "question_id",
        "question",
        "top1_doc_id",
        "top1_preview",
        "contains_expected",
        "hits_forbidden",
        "top1_doc_expected",
        "top_k_used",
    ]
    if args.llm_judge:
        fieldnames.extend(
            [
                "llm_judge_pass",
                "llm_judge_score",
                "llm_judge_reason",
                "llm_judge_answer",
                "llm_judge_model",
            ]
        )
    with out_path.open("w", encoding="utf-8", newline="") as fcsv:
        w = csv.DictWriter(fcsv, fieldnames=fieldnames)
        w.writeheader()
        for q in questions:
            text = q["question"]
            res = col.query(query_texts=[text], n_results=args.top_k)
            docs = (res.get("documents") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            top_doc = (metas[0] or {}).get("doc_id", "") if metas else ""
            preview = (docs[0] or "")[:180].replace("\n", " ") if docs else ""
            blob = " ".join(docs).lower()
            must_any = [x.lower() for x in q.get("must_contain_any", [])]
            forbidden = [x.lower() for x in q.get("must_not_contain", [])]
            ok_any = any(m in blob for m in must_any) if must_any else True
            bad_forb = any(m in blob for m in forbidden) if forbidden else False
            want_top1 = (q.get("expect_top1_doc_id") or "").strip()
            top1_expected = ""
            if want_top1:
                top1_expected = "yes" if top_doc == want_top1 else "no"
            row = {
                "question_id": q.get("id", ""),
                "question": text,
                "top1_doc_id": top_doc,
                "top1_preview": preview,
                "contains_expected": "yes" if ok_any else "no",
                "hits_forbidden": "yes" if bad_forb else "no",
                "top1_doc_expected": top1_expected,
                "top_k_used": args.top_k,
            }
            if args.llm_judge:
                try:
                    row.update(
                        _llm_judge(
                            question=q,
                            docs=docs,
                            metas=metas,
                            model=args.judge_model,
                            base_url=args.judge_base_url,
                            api_key=api_key,
                            timeout=args.judge_timeout,
                            max_context_chars=args.judge_max_context_chars,
                        )
                    )
                except Exception as e:
                    row.update(
                        {
                            "llm_judge_pass": "error",
                            "llm_judge_score": "",
                            "llm_judge_reason": str(e).replace("\n", " ")[:500],
                            "llm_judge_answer": "",
                            "llm_judge_model": args.judge_model,
                        }
                    )
            w.writerow(row)

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
