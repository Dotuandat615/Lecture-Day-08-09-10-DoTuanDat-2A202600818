# Báo cáo chất lượng - Lab Day 10 (nhóm)

**run_id:** `sprint3-inject-bad` -> `sprint3-clean-good`  
**Ngày:** 2026-06-10

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước / inject bad | Sau / clean good | Ghi chú |
|--------|---------------------|------------------|---------|
| raw_records | 247 | 247 | Cùng file `data/raw/policy_export_dirty.csv` |
| cleaned_records | 35 | 27 | Inject cho stale refund/noisy refund lọt vào cleaned |
| quarantine_records | 212 | 220 | Clean good quarantine lại stale/noisy/export format rows |
| Expectation halt? | Có, nhưng `--skip-validate` cho embed tiếp | Không | Bad run có 4 halt expectation fail; good run tất cả OK |

Log chứng minh:

```text
run_id=sprint3-inject-bad
cleaned_records=35
quarantine_records=212
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=3
WARN: expectation failed but --skip-validate -> tiếp tục embed
PIPELINE_OK
```

```text
run_id=sprint3-clean-good
cleaned_records=27
quarantine_records=220
expectation[refund_no_stale_14d_window] OK (halt) :: violations=0
expectation[no_stale_doc_versions] OK (halt) :: violations=0
PIPELINE_OK
```

---

## 2. Before / after retrieval

Files:

- Eval xấu: `artifacts/eval/sprint3_eval_bad.csv`
- Eval tốt: `artifacts/eval/sprint3_eval_good.csv`

Tổng hợp 21 câu eval:

| Metric | Bad inject | Clean good |
|--------|------------|------------|
| contains_expected=yes | 18/21 | 19/21 |
| hits_forbidden=yes | 1/21 | 0/21 |
| top1_doc_expected=yes | 19/21 | 19/21 |

**Câu hỏi then chốt:** refund window (`q_refund_window`)

| Run | top1_doc_id | contains_expected | hits_forbidden | top1_doc_expected | top1_preview |
|-----|-------------|-------------------|----------------|-------------------|--------------|
| Bad inject | `policy_refund_v4` | yes | yes | yes | `Nội dung không rõ ràng: Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc...` |
| Clean good | `policy_refund_v4` | yes | no | yes | `Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.` |

Kết luận: dirty index vẫn retrieve đúng doc refund, nhưng context top-k chứa forbidden stale value `14 ngày`. Clean pipeline loại/fix stale refund, nên forbidden hit biến mất và answer context quay về `7 ngày làm việc`.

**Merit - HR versioning (`q_hr_annual_leave_under3`)**

| Run | contains_expected | hits_forbidden | top1_doc_expected |
|-----|-------------------|----------------|-------------------|
| Bad inject | yes | no | yes |
| Clean good | yes | no | yes |

HR vẫn ổn định vì Sprint 1-2 đã quarantine HR 2025 annual leave stale content.

---

## 3. Freshness & monitor

Bad inject freshness:

```text
freshness_check=WARN {"reason": "no_timestamp_in_manifest", ... "latest_exported_at": "2026/04/07T00:00:00"}
```

Clean good freshness:

```text
freshness_check=FAIL {"latest_exported_at": "2026-04-11T00:00:00", "age_hours": 1447.057, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

Giải thích: sample export date cũ hơn SLA 24h nên freshness FAIL/WARN là đúng với dữ liệu mẫu. Đây là monitor signal, không phải expectation halt của clean/validate.

---

## 4. Corruption inject (Sprint 3)

Lệnh inject:

```bash
python etl_pipeline.py run --run-id sprint3-inject-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/sprint3_eval_bad.csv
```

Inject có chủ đích tắt refund fix và bỏ qua validation halt, làm stale refund chunks `14 ngày làm việc` được embed vào Chroma. Expectation suite đã phát hiện đúng lỗi:

- `refund_no_stale_14d_window`: 3 violations
- `no_stale_doc_versions`: 8 violations
- `no_low_confidence_noise_markers`: 4 violations
- `exported_at_iso_datetime`: 1 violation

Lệnh clean recovery:

```bash
python etl_pipeline.py run --run-id sprint3-clean-good
python eval_retrieval.py --out artifacts/eval/sprint3_eval_good.csv
```

Clean run prune 35 dirty vectors, upsert 27 clean chunks, và grading quick check sau recovery OK tất cả `gq_d10_01` đến `gq_d10_10`.

---

## 5. Hạn chế & việc chưa làm

- Sau chỉnh SLA enrichment, eval keyword và LLM-judge đều pass 21/21; trước đó 2 câu P1 (`q_p1_first_response`, `q_p1_update_frequency`) chưa vào top-k tốt.
- Freshness đang FAIL do timestamp mẫu cũ; Sprint 4 runbook đã giải thích PASS/WARN/FAIL và SLA boundary.
- Artifacts nằm trong `artifacts/` và bị `.gitignore`, cần đảm bảo nộp kèm nếu LMS yêu cầu file evidence.
