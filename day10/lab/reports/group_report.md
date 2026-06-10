# Báo Cáo Nhóm - Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** DoTuanDat  
**Thành viên:**

| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Đỗ Tuấn Đạt | Ingestion / Cleaning / Embed / Monitoring | N/A |

**Ngày nộp:** 2026-06-10  
**Repo:** Lecture-Day-08-09-10-DoTuanDat-2A202600818

---

## 1. Pipeline tổng quan

Raw CSV `data/raw/policy_export_dirty.csv` được ingest bằng `load_raw_csv`, sau đó clean bằng `transform/cleaning_rules.py`, ghi cleaned/quarantine artifact theo `run_id`, validate bằng `quality/expectations.py`, và publish vào Chroma collection `day10_kb`. Mỗi run ghi `run_id`, `raw_records`, `cleaned_records`, `quarantine_records`, expectation result, embed count, manifest path và freshness status trong `artifacts/logs/run_<run_id>.log`. Run sạch cuối là `sprint3-clean-good`: `raw_records=247`, `cleaned_records=27`, `quarantine_records=220`, tất cả halt expectations OK và `PIPELINE_OK`.

**Một lệnh chạy cả pipeline + grading:**

```bash
python etl_pipeline.py run && python grading_run.py --out artifacts/eval/grading_run.jsonl && python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
```

---

## 2. Cleaning & expectation

### 2a. Bảng metric_impact

| Rule / Expectation mới | Trước | Sau / khi inject | Chứng cứ |
|------------------------|--------|------------------|----------|
| Rule `invalid_exported_at_format` | Sprint 1 cleaned còn 2 row có `exported_at` không ISO datetime | Sprint 2 quarantine thêm 2 row với reason `invalid_exported_at_format` | `artifacts/cleaned/cleaned_2026-06-10T04-56Z.csv`; quarantine CSV Sprint 2 |
| Rule `low_confidence_or_noisy_chunk` | Sprint 1 cleaned còn 9 row có marker low-confidence/noisy | Sprint 2 quarantine 7 unique row với reason `low_confidence_or_noisy_chunk` | `artifacts/cleaned/cleaned_2026-06-10T04-56Z.csv`; quarantine CSV Sprint 2 |
| Rule `stale_doc_version_effective_date` | Sprint 1 cleaned còn 17 row cũ hơn canonical min effective date | Sprint 2 quarantine 8 unique row với reason `stale_doc_version_effective_date` | `transform/cleaning_rules.py`; quarantine CSV Sprint 2 |
| Rule `canonical_current_fact_enrichment` | Grading trước enrichment fail `gq_d10_04`, `gq_d10_05`, `gq_d10_06`, `gq_d10_07` | Sau enrichment, `instructor_quick_check.py` OK cả `gq_d10_01` đến `gq_d10_10` | `artifacts/eval/grading_run.jsonl`; `artifacts/logs/run_2026-06-10T06-40Z.log` |
| Expectation `exported_at_iso_datetime` | FAIL trên Sprint 1 cleaned: `non_iso_exported_at_rows=2` | PASS trên Sprint 2 cleaned: `non_iso_exported_at_rows=0` | Log pipeline Sprint 2 |
| Expectation `no_low_confidence_noise_markers` | FAIL trên Sprint 1 cleaned: `violations=9` | PASS trên Sprint 2 cleaned: `violations=0` | Log pipeline Sprint 2 |
| Expectation `no_stale_doc_versions` | FAIL trên Sprint 1 cleaned: `violations=17` | PASS trên Sprint 2 cleaned: `violations=0` | Log pipeline Sprint 2 |

**Rule chính:**

- Allowlist 5 nguồn hợp lệ gồm `access_control_sop`.
- Quarantine missing/invalid effective date, missing text, duplicate text, HR 2025 annual leave stale content.
- Sprint 2 thêm exported-at ISO datetime, low-confidence/noisy chunk, và doc-level min effective date.
- Sprint 2 enrichment bổ sung fact canonical còn thiếu vào current chunks cho SLA P1 và IT lockout để grading không phụ thuộc vào stale summary rows.

**Ví dụ expectation fail và cách xử lý:**  
Trên cleaned artifact Sprint 1, expectation mới `no_stale_doc_versions` fail với `violations=17`. Sprint 2 thêm rule `stale_doc_version_effective_date`, chạy clean lại, và expectation còn `violations=0`.

---

## 3. Before / after ảnh hưởng retrieval

**Kịch bản inject:**  
Sprint 3 dùng `python etl_pipeline.py run --run-id sprint3-inject-bad --no-refund-fix --skip-validate` để cố tình embed dirty refund chunks. Bad log có `refund_no_stale_14d_window FAIL (halt) :: violations=3`, nhưng `--skip-validate` cho pipeline tiếp tục embed 35 chunks. Sau đó chạy `python eval_retrieval.py --out artifacts/eval/sprint3_eval_bad.csv`. Recovery chạy `python etl_pipeline.py run --run-id sprint3-clean-good`, prune 35 dirty vectors, upsert 27 clean chunks, rồi chạy `python eval_retrieval.py --out artifacts/eval/sprint3_eval_good.csv`.

**Kết quả định lượng:**  
Bad eval: `contains_expected=yes` 18/21, `hits_forbidden=yes` 1/21, `top1_doc_expected=yes` 19/21. Good eval: `contains_expected=yes` 19/21, `hits_forbidden=yes` 0/21, `top1_doc_expected=yes` 19/21. Câu `q_refund_window` là bằng chứng chính: bad run top preview chứa stale `14 ngày làm việc` và `hits_forbidden=yes`; clean run trả về `7 ngày làm việc`, `hits_forbidden=no`.

---

## 4. Freshness & monitoring

SLA mặc định là `FRESHNESS_SLA_HOURS=24`, đo tại publish boundary dựa trên `latest_exported_at` trong manifest. Lệnh Sprint 4:

```bash
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_sprint3-clean-good.json
```

Kết quả trả về `FAIL` vì `latest_exported_at=2026-04-11T00:00:00`, `age_hours=1447.228`, vượt SLA 24h. PASS nghĩa là timestamp hợp lệ và còn trong SLA; WARN nghĩa là manifest thiếu timestamp hoặc format không parse được; FAIL nghĩa là timestamp parse được nhưng stale. Với lab này, FAIL là monitor signal hợp lý cho data mẫu cũ, không phải clean expectation halt.

---

## 5. Liên hệ Day 09

Pipeline Day 10 publish corpus sạch vào Chroma collection `day10_kb`, có thể được retrieval worker của Day 09 dùng thay cho việc đọc raw docs trực tiếp. Nhóm tách collection để debug data layer riêng: nếu answer sai, kiểm tra manifest, quarantine, expectation và eval trước khi sửa supervisor/router/prompt Day 09.

---

## 6. Rủi ro còn lại & việc chưa làm

- `artifacts/` bị `.gitignore`; cần nộp kèm file evidence nếu LMS yêu cầu.
- Freshness đang FAIL vì data mẫu cũ; Sprint 4 runbook đã giải thích PASS/WARN/FAIL.
- Sau chỉnh SLA enrichment, eval self-check và LLM-judge đều pass 21/21; grading chính thức 10 câu cũng pass.
- `grading_questions.json` bị ignore theo rubric; nếu máy khác không có file này thì dùng `data/test_questions.json` để self-check.

---

## 7. Peer review - 3 câu hỏi

| Câu hỏi | Trả lời ngắn |
|---------|--------------|
| Nếu pipeline trả lời refund `14 ngày`, debug theo thứ tự nào? | Kiểm tra eval `hits_forbidden`, log expectation `refund_no_stale_14d_window`, quarantine reason, rồi rerun clean pipeline. |
| Khi nào được dùng `--skip-validate`? | Chỉ dùng cho inject/demo Sprint 3; publish chuẩn không được skip halt expectations. |
| Freshness FAIL có đồng nghĩa pipeline hỏng không? | Không. Trong lab này FAIL do sample `latest_exported_at` cũ hơn SLA 24h; clean/validate vẫn pass nếu expectations OK. |
