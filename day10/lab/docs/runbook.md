# Runbook vận hành - Lab Day 10

## Symptom

Các triệu chứng người dùng/agent có thể thấy:

- Agent trả lời refund window là `14 ngày` thay vì `7 ngày`.
- Câu HR annual leave trả về `10 ngày phép năm` thay vì `12 ngày`.
- Câu access control không retrieve `access_control_sop`.
- Eval CSV có `hits_forbidden=yes`, `contains_expected=no`, hoặc `top1_doc_expected=no`.
- Pipeline log có `PIPELINE_HALT` hoặc expectation `FAIL (halt)`.

---

## Detection

Các lệnh kiểm tra chính:

```bash
python etl_pipeline.py run
python eval_retrieval.py --out artifacts/eval/latest_eval.csv
python grading_run.py --out artifacts/eval/grading_run.jsonl
python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
```

Freshness check:

```bash
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_sprint3-clean-good.json
```

Kết quả quan sát ở Sprint 4:

```text
FAIL {"latest_exported_at": "2026-04-11T00:00:00", "age_hours": 1447.228, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

Ý nghĩa freshness status:

| Status | Ý nghĩa | Hành động |
|--------|---------|-----------|
| PASS | Manifest có `latest_exported_at` parse được và age nằm trong `FRESHNESS_SLA_HOURS` | Tiếp tục serving bình thường |
| WARN | Timestamp bị thiếu/không parse được hoặc manifest chưa đủ dữ liệu để quyết định freshness | Kiểm tra manifest generation và format timestamp nguồn |
| FAIL | Timestamp parse được nhưng đã quá SLA | Xem data là stale; rerun ingest/export hoặc báo owner |

Trong lab này, freshness FAIL là expected với sample data cũ và không có nghĩa clean/validate bị lỗi.

---

## Diagnosis

| Step | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Mở latest `artifacts/logs/run_<run_id>.log` | Thấy `run_id`, record counts, expectation OK/FAIL |
| 2 | Mở `artifacts/manifests/manifest_<run_id>.json` | Xác nhận `raw_records`, `cleaned_records`, `quarantine_records`, `latest_exported_at` |
| 3 | Mở `artifacts/quarantine/quarantine_<run_id>.csv` | Đếm reason như `stale_doc_version_effective_date`, `unknown_doc_id`, `low_confidence_or_noisy_chunk` |
| 4 | Chạy eval retrieval | Xác định câu nào có `hits_forbidden` hoặc sai top-1 |
| 5 | Nếu grading sai | Chạy `instructor_quick_check.py` để biết `gq_d10_*` nào fail |

Ví dụ incident Sprint 3:

- Bad run: `sprint3-inject-bad`
- Log: `refund_no_stale_14d_window FAIL (halt) :: violations=3`
- Eval: `q_refund_window` có `hits_forbidden=yes`
- Root cause: dirty inject `--no-refund-fix --skip-validate` đã embed stale refund chunks.

---

## Mitigation

1. Dừng dùng dirty inject index cho serving.
2. Chạy clean recovery:

```bash
python etl_pipeline.py run --run-id sprint3-clean-good
```

3. Verify log có:

```text
expectation[refund_no_stale_14d_window] OK (halt) :: violations=0
PIPELINE_OK
```

4. Chạy lại eval/grading:

```bash
python eval_retrieval.py --out artifacts/eval/sprint3_eval_good.csv
python grading_run.py --out artifacts/eval/grading_run.jsonl
python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
```

5. Nếu freshness vẫn FAIL, giải thích sample source đang intentionally old hoặc yêu cầu export mới hơn.

---

## Prevention

- Chỉ dùng `--skip-validate` cho demo; không dùng cho normal publish.
- Giữ halt expectations cho stale refund, HR stale annual leave, stale doc versions, noisy markers, và exported timestamp format.
- Mỗi allowed doc mới phải được thêm ở cả `cleaning_rules.py` và `contracts/data_contract.yaml`.
- Giữ eval artifacts cho before/after evidence sau mỗi thay đổi quality.
- Dùng Chroma prune + upsert snapshot publishing để stale vector ids không sống sót sau clean run.
