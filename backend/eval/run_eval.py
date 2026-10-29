"""Run extraction against manually annotated documents and report honest metrics.

No official sample paths or ground truth are shipped yet; the default run therefore
reports a blocked/metrics-unavailable status rather than manufacturing benchmark values.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
MANIFEST_PATH = BACKEND_DIR / "eval" / "dataset" / "manifest.json"
ANNOTATIONS_PATH = BACKEND_DIR / "eval" / "ground_truth" / "annotations.json"
REPORT_PATH = BACKEND_DIR / "eval" / "reports" / "latest.json"


def _norm(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return re.sub(r"[^a-z0-9+#.]+", " ", text).strip()


def _metric(predicted: list[dict[str, Any]], gold: list[dict[str, Any]]) -> dict[str, Any]:
    # Import canonical aliases so Postgres/PostgreSQL etc use the product's documented taxonomy.
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)
    try:
        from radix_jd.skill_match import canonical
        canonicalise = canonical
    except Exception:
        canonicalise = _norm

    pred_keys = {canonicalise(x.get("skill_name")) for x in predicted if x.get("skill_name")}
    gold_keys = {canonicalise(x.get("skill_name")) for x in gold if x.get("skill_name")}
    tp = len(pred_keys & gold_keys)
    fp = len(pred_keys - gold_keys)
    fn = len(gold_keys - pred_keys)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else None

    gold_req = {canonicalise(x.get("skill_name")): x.get("requirement_type") for x in gold
                if x.get("skill_name") and x.get("requirement_type") in {"required", "preferred"}}
    pred_req = {canonicalise(x.get("skill_name")): x.get("requirement_type") for x in predicted
                if x.get("skill_name") and x.get("requirement_type") in {"required", "preferred"}}
    comparable = [key for key in gold_req if key in pred_req]
    requirement_type_accuracy = (sum(gold_req[k] == pred_req[k] for k in comparable) / len(comparable)) if comparable else None
    return {
        "true_positive": tp, "false_positive": fp, "false_negative": fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "requirement_type_accuracy": round(requirement_type_accuracy, 4) if requirement_type_accuracy is not None else None,
        "predicted_skill_count": len(pred_keys), "gold_skill_count": len(gold_keys),
    }



def _dataset_completeness(manifest: dict[str, Any], annotations: dict[str, dict[str, Any]], variants: list[dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
    """A final benchmark requires approved labels and both PDF/DOCX variants for every official item."""
    documents = [d for d in manifest.get("documents", []) if d.get("document_id")]
    expected_ids = {str(d["document_id"]) for d in documents}
    approved_ids = {doc_id for doc_id in expected_ids if (annotations.get(doc_id) or {}).get("approved") is True
                    and isinstance((annotations.get(doc_id) or {}).get("skills"), list)
                    and bool((annotations.get(doc_id) or {}).get("skills"))}
    processed = {(str(row.get("document_id")), str(row.get("format")).lower()) for row in variants
                 if row.get("approved_ground_truth") is True and isinstance(row.get("metrics"), dict)}
    expected_variants = {(doc_id, fmt) for doc_id in expected_ids for fmt in ("pdf", "docx")}
    missing_variants = sorted(f"{doc_id}:{fmt}" for doc_id, fmt in expected_variants if (doc_id, fmt) not in processed)
    detail = {
        "logical_documents_expected": len(expected_ids),
        "documents_with_approved_ground_truth": len(approved_ids),
        "document_variants_expected": len(expected_variants),
        "document_variants_scored": len(processed),
        "missing_or_unapproved_variants": missing_variants,
    }
    return bool(expected_ids) and approved_ids == expected_ids and processed == expected_variants, detail

def _extract(api_base: str, kind: str, path: Path, timeout: int) -> dict[str, Any]:
    endpoint = "/api/analyze-jd" if kind == "jd" else "/api/parse-resume"
    mime = "application/pdf" if path.suffix.lower() == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    with path.open("rb") as handle:
        response = requests.post(api_base.rstrip("/") + endpoint,
                                 files={"file": (path.name, handle, mime)}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def run(api_base: str, timeout: int = 120) -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    annotations_raw = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    annotations = {x.get("document_id"): x for x in annotations_raw.get("documents", []) if isinstance(x, dict)}
    per_variant: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    variant_skills: dict[tuple[str, str], set[str]] = {}
    approved_docs = 0
    calls = 0
    start_all = time.perf_counter()

    for doc in manifest.get("documents", []):
        doc_id = str(doc.get("document_id") or "")
        label = str(doc.get("label") or doc_id)
        kind = doc.get("kind")
        annotation = annotations.get(doc_id)
        if not doc_id or kind not in {"jd", "resume"}:
            skipped.append({"document_id": doc_id or "unknown", "reason": "invalid_manifest_entry"})
            continue
        if not annotation or annotation.get("approved") is not True or not isinstance(annotation.get("skills"), list) or not annotation.get("skills"):
            skipped.append({"document_id": doc_id, "reason": "missing_team_approved_ground_truth"})
            approved = False
        else:
            approved = True
            approved_docs += 1
        for fmt, path_value in (("pdf", doc.get("pdf_path")), ("docx", doc.get("docx_path"))):
            raw_path = str(path_value or "").strip()
            if not raw_path:
                skipped.append({"document_id": doc_id, "format": fmt, "reason": "source_path_not_configured"})
                continue
            path = (ROOT_DIR / raw_path).resolve()
            if not path.is_file() or ROOT_DIR.resolve() not in path.parents:
                skipped.append({"document_id": doc_id, "format": fmt, "reason": "source_file_missing_or_outside_project"})
                continue
            try:
                began = time.perf_counter()
                output = _extract(api_base, kind, path, timeout)
                elapsed = round((time.perf_counter() - began) * 1000, 2)
                calls += 1
            except Exception as exc:
                skipped.append({"document_id": doc_id, "format": fmt, "reason": f"extraction_failed:{type(exc).__name__}"})
                continue
            if kind == "jd":
                predicted = [{"skill_name": x.get("skill_name"), "requirement_type": x.get("requirement_type")}
                             for x in output.get("skills", []) if isinstance(x, dict)]
                analysis_meta = output.get("analysis_meta") or {}
                model_calls = analysis_meta.get("model_calls")
                runtime_ms = analysis_meta.get("runtime_ms", elapsed)
            else:
                predicted = [{"skill_name": x.get("skill_name")} for x in (output.get("profile") or {}).get("skills", []) if isinstance(x, dict)]
                ai_meta = output.get("ai_metadata") or {}
                model_calls = ai_meta.get("model_calls")
                runtime_ms = ai_meta.get("runtime_ms", elapsed)
            canonical_names = {_norm(x.get("skill_name")) for x in predicted if x.get("skill_name")}
            variant_skills[(doc_id, fmt)] = canonical_names
            gold = annotation.get("skills", []) if approved else []
            metrics = _metric(predicted, gold) if approved else None
            per_variant.append({
                "document_id": doc_id, "label": label, "kind": kind, "format": fmt,
                "file": path.name, "approved_ground_truth": approved,
                "metrics": metrics, "predicted_skills": predicted,
                "processing_path": (output.get("analysis_meta") or {}).get("processing_path") if kind == "jd" else output.get("extraction_method"),
                "model_used": (output.get("ai_metadata") or {}).get("model_used") if kind == "resume" else None,
                "model_calls": model_calls, "runtime_ms": runtime_ms,
            })

    metric_rows = [x["metrics"] for x in per_variant if x.get("metrics")]
    # Micro aggregate from TP/FP/FN, never average percentages with unlike denominators.
    if metric_rows:
        total_tp = sum(x["true_positive"] for x in metric_rows)
        total_fp = sum(x["false_positive"] for x in metric_rows)
        total_fn = sum(x["false_negative"] for x in metric_rows)
        p = total_tp / (total_tp + total_fp) if total_tp + total_fp else None
        r = total_tp / (total_tp + total_fn) if total_tp + total_fn else None
        f = 2 * p * r / (p + r) if p is not None and r is not None and p + r else None
        overall = {"true_positive": total_tp, "false_positive": total_fp, "false_negative": total_fn,
                   "precision": round(p, 4) if p is not None else None,
                   "recall": round(r, 4) if r is not None else None,
                   "f1": round(f, 4) if f is not None else None,
                   "requirement_type_accuracy": None}
        req_rows = [(x["metrics"], x["metrics"]["requirement_type_accuracy"]) for x in per_variant
                    if x.get("metrics") and x["kind"] == "jd" and x["metrics"]["requirement_type_accuracy"] is not None]
        if req_rows:
            # accuracy is calculated across matched gold/predicted labels by each doc; each document is one vote.
            overall["requirement_type_accuracy"] = round(sum(a for _, a in req_rows) / len(req_rows), 4)
    else:
        overall = None

    parity = []
    for doc in manifest.get("documents", []):
        doc_id = str(doc.get("document_id") or "")
        pdf = variant_skills.get((doc_id, "pdf")); docx = variant_skills.get((doc_id, "docx"))
        if pdf is None or docx is None:
            continue
        union = pdf | docx
        overlap = len(pdf & docx) / len(union) if union else None
        parity.append({"document_id": doc_id, "jaccard_overlap": round(overlap, 4) if overlap is not None else None,
                       "pdf_skill_count": len(pdf), "docx_skill_count": len(docx)})

    dataset_complete, coverage = _dataset_completeness(manifest, annotations, per_variant)
    if overall is None:
        status = "blocked"
        reason = "No approved human-labelled document variants were successfully evaluated; metrics are unavailable, not zero."
    elif not dataset_complete:
        status = "partial"
        reason = "Subset metrics are shown for transparency, but this is not a final benchmark. Supply and annotate every official document in both PDF and DOCX formats."
    else:
        status = "ready"
        reason = None
    report = {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status, "reason": reason, "api_base": api_base,
        "official_documents_expected": len(manifest.get("documents", [])),
        "approved_ground_truth_documents": approved_docs,
        "dataset_complete": dataset_complete, "coverage": coverage,
        "documents_scored": len(metric_rows), "requests_succeeded": calls,
        "runtime_ms_total": round((time.perf_counter() - start_all) * 1000, 2),
        "metrics": overall, "pdf_docx_parity": parity,
        "documents": per_variant, "skipped": skipped,
        "integrity_note": "Metrics are final only when every official document has team-approved ground truth and both PDF/DOCX variants are scored. Synthetic test files are not substituted for official samples.",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    report = run(args.api_base, args.timeout)
    print(json.dumps({"status": report["status"], "metrics": report["metrics"],
                      "documents_scored": report["documents_scored"],
                      "requests_succeeded": report["requests_succeeded"],
                      "skipped_count": len(report["skipped"]), "report": str(REPORT_PATH)}, indent=2))
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
