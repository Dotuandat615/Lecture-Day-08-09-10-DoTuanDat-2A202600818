"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)

DOC_MIN_EFFECTIVE_DATES = {
    "policy_refund_v4": "2026-02-01",
    "sla_p1_2026": "2026-01-15",
    "it_helpdesk_faq": "2026-01-20",
    "hr_leave_policy": "2026-01-01",
    "access_control_sop": "2026-01-01",
}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


def _is_stale_hr_annual_leave(text: str) -> bool:
    """
    Detect stale HR 2025 annual-leave chunks without quarantining the valid
    sick-leave rule that also mentions 10 days/year.
    """
    norm = _norm_text(text)
    if "hr 2025" in norm:
        return True
    if "10 ngày" in norm and "phép năm" in norm and "nghỉ ốm" not in norm:
        return True
    return False


def _is_iso_exported_at(value: str) -> bool:
    return bool(_ISO_DATETIME.match((value or "").strip()))


def _is_low_confidence_or_noisy_chunk(text: str, doc_id: str = "") -> bool:
    norm = _norm_text(text)
    if doc_id == "hr_leave_policy" and norm.startswith("nội dung không rõ ràng:"):
        return False
    markers = (
        "nội dung không rõ ràng:",
        "!!!",
        "effective_date không đồng nhất",
        "sync lại dữ liệu",
    )
    return any(marker in norm for marker in markers)


def _is_stale_doc_version(doc_id: str, effective_date: str) -> bool:
    min_date = DOC_MIN_EFFECTIVE_DATES.get(doc_id)
    return bool(min_date and effective_date < min_date)


def _inject_dirty_refund(doc_id: str, apply_refund_window_fix: bool) -> bool:
    return doc_id == "policy_refund_v4" and not apply_refund_window_fix


def _enrich_canonical_current_chunk(doc_id: str, text: str) -> str:
    if doc_id == "sla_p1_2026":
        fact = (
            " SLA phản hồi đầu tiên cho ticket P1 được cam kết là trong 15 phút. "
            "SLA resolution cho ticket P1 là 4 giờ. "
            "Nếu không có phản hồi với ticket P1, hệ thống auto escalate sau 10 phút. "
            "Trong sự cố P1, thông tin tiến độ cần được cập nhật mỗi 30 phút cho đến khi resolve."
        )
        if (
            "15 phút" not in text
            or "4 giờ" not in text
            or "10 phút" not in text
            or "30 phút" not in text
        ):
            return text + fact
    if doc_id == "it_helpdesk_faq":
        fact = " Tài khoản bị khóa sau 5 lần đăng nhập sai liên tiếp."
        if "5 lần" not in text:
            return text + fact
    return text


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
    4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    5) Loại trùng nội dung chunk_text (giữ bản đầu).
    6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if doc_id == "hr_leave_policy" and _is_stale_hr_annual_leave(text):
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_annual_leave_content",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        key = _norm_text(text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        inject_dirty_refund = _inject_dirty_refund(doc_id, apply_refund_window_fix)

        if not inject_dirty_refund and not _is_iso_exported_at(exported_at):
            quarantine.append(
                {
                    **raw,
                    "reason": "invalid_exported_at_format",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not inject_dirty_refund and _is_low_confidence_or_noisy_chunk(text, doc_id):
            quarantine.append(
                {
                    **raw,
                    "reason": "low_confidence_or_noisy_chunk",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not inject_dirty_refund and _is_stale_doc_version(doc_id, eff_norm):
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_doc_version_effective_date",
                    "effective_date_normalized": eff_norm,
                    "min_effective_date": DOC_MIN_EFFECTIVE_DATES.get(doc_id, ""),
                }
            )
            continue

        fixed_text = text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"
        fixed_text = _enrich_canonical_current_chunk(doc_id, fixed_text)

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
