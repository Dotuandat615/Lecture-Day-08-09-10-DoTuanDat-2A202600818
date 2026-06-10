# Hợp đồng dữ liệu - Lab Day 10

Nguồn sự thật của code/config:

- `contracts/data_contract.yaml`
- `transform/cleaning_rules.py`
- `quality/expectations.py`

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|--------------------|--------------------|----------------|
| `policy_refund_v4` | CSV export từ CS/refund policy system | Stale refund window 14 ngày thay vì 7 ngày; dirty inject bỏ qua refund fix | `refund_no_stale_14d_window`; eval `q_refund_window` `hits_forbidden` |
| `sla_p1_2026` | CSV export từ IT support/SLA system | Chunk cũ thiếu version boundary hoặc thiếu fact P1 current | `no_stale_doc_versions`; grading `gq_d10_04..06` |
| `it_helpdesk_faq` | CSV export từ IT Helpdesk FAQ | Chunk stale/summary thiếu fact lockout/password/VPN | `no_stale_doc_versions`; grading `gq_d10_07..08` |
| `hr_leave_policy` | CSV export từ HR policy system | HR 2025 annual leave 10 ngày lọt vào index | `hr_leave_no_stale_10d_annual`; eval/grading HR forbidden hit |
| `access_control_sop` | CSV export từ IT access workflow | Source hợp lệ bị thiếu allowlist/catalog | Top-1 retrieval cho access questions phải là `access_control_sop` |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| `chunk_id` | string | Có | Stable id sau clean, dùng cho Chroma upsert/prune |
| `doc_id` | string enum | Có | Phải nằm trong allowlist 5 docs hợp lệ |
| `chunk_text` | string | Có | Min length 8, không chứa marker stale/noisy bị cấm |
| `effective_date` | date `YYYY-MM-DD` | Có | Phải >= min effective date theo từng doc |
| `exported_at` | datetime `YYYY-MM-DDTHH:MM:SS` | Có | Dùng cho lineage/freshness; row sai format bị quarantine trong run chuẩn |

Doc được phép:

- `policy_refund_v4`
- `sla_p1_2026`
- `it_helpdesk_faq`
- `hr_leave_policy`
- `access_control_sop`

Ngày hiệu lực tối thiểu theo canonical:

| doc_id | min_effective_date |
|--------|--------------------|
| `policy_refund_v4` | `2026-02-01` |
| `sla_p1_2026` | `2026-01-15` |
| `it_helpdesk_faq` | `2026-01-20` |
| `hr_leave_policy` | `2026-01-01` |
| `access_control_sop` | `2026-01-01` |

---

## 3. Quy tắc quarantine vs drop

Pipeline không drop silent. Mỗi row bị loại khỏi cleaned được ghi vào `artifacts/quarantine/quarantine_<run_id>.csv` với `reason`.

Các reason chính:

- `unknown_doc_id`
- `missing_effective_date`
- `invalid_effective_date_format`
- `missing_chunk_text`
- `duplicate_chunk_text`
- `stale_hr_policy_effective_date`
- `stale_hr_annual_leave_content`
- `invalid_exported_at_format`
- `low_confidence_or_noisy_chunk`
- `stale_doc_version_effective_date`

Nếu cần merge lại row quarantine, owner phải cập nhật canonical source hoặc cleaning rule, chạy lại pipeline, và ghi evidence trong report.

---

## 4. Phiên bản & canonical

Canonical sources nằm trong `data/docs/`:

- Refund: `data/docs/policy_refund_v4.txt`, version v4, effective `2026-02-01`.
- SLA P1: `data/docs/sla_p1_2026.txt`, effective `2026-01-15`.
- IT FAQ: `data/docs/it_helpdesk_faq.txt`, effective `2026-01-20`.
- HR leave: `data/docs/hr_leave_policy.txt`, effective `2026-01-01`.
- Access control: `data/docs/access_control_sop.txt`, effective `2026-01-01`.

Publish chuẩn phải chạy không có `--skip-validate`. Inject mode `--no-refund-fix --skip-validate` chỉ dùng cho evidence Sprint 3 và phải được follow bằng một clean recovery run.
