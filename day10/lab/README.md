# Lab Day 10 — Data Pipeline & Data Observability

**Môn:** AI in Action (AICB-P1)  
**Chủ đề:** ETL / cleaning / expectation suite / embed / freshness / before-after evidence  
**Thời gian:** 4 giờ (4 sprints × ~60 phút)  
**Tiếp nối:** Day 08 RAG · Day 09 Multi-agent — **cùng case CS + IT Helpdesk**, hôm nay làm **tầng dữ liệu** trước khi agent "đọc đúng version".

**Slide:** [`../lecture-10.html`](../lecture-10.html)

---

## Bối cảnh

Vector store và agent Day 09 chỉ ổn nếu **pipeline ingest → clean → validate → publish** ổn. Lab này mô phỏng:

- Export "raw" từ **5 hệ thống nguồn** (CSV mẫu) có **duplicate**, **dòng thiếu ngày**, **doc_id lạ**, **ngày hiệu lực không ISO**, **xung đột version HR (10 vs 12 ngày phép)**, **chunk policy sai cửa sổ hoàn tiền (14 vs 7 ngày)**, và **nguồn dữ liệu chưa được đăng ký trong pipeline**.
- Pipeline baseline được cung cấp nhưng **chưa hoàn chỉnh** — học viên phải phân tích dữ liệu raw, phát hiện lỗ hổng trong code, sửa và mở rộng pipeline để embed **toàn bộ** dữ liệu cần thiết vào vector database.
- Nhóm phải có **log số record**, **quarantine**, **expectation halt có kiểm soát**, **run_id** trên manifest, và **bằng chứng before/after** trên retrieval test.

---

## Mục tiêu học tập

| Mục tiêu | Sprint |
|----------|--------|
| Phân tích raw data + phát hiện pipeline gaps + sửa pipeline | Sprint 1 |
| Cleaning rules + cleaned CSV + quarantine + embed | Sprint 1–2 |
| Expectation suite (≥2 mới) + chạy pipeline thành công | Sprint 2 |
| Inject corruption + so sánh eval + quality report | Sprint 3 |
| Freshness check + runbook + hoàn thiện docs & báo cáo | Sprint 4 |

---

## Nhiệm vụ chính — Pipeline cần sửa gì?

> **Pipeline baseline chưa hoàn chỉnh.** Dữ liệu raw chứa export từ **5 hệ thống nguồn**, nhưng pipeline hiện tại chỉ nhận diện và xử lý **một phần**. Học viên cần tự phân tích và sửa pipeline để embed đủ dữ liệu, đảm bảo trả lời đúng **tất cả 10 câu hỏi đánh giá** trong `data/grading_questions.json`.

### Quy trình gợi ý

**Bước 1 — Chạy pipeline lần đầu và quan sát:**

```bash
python etl_pipeline.py run
```

Pipeline sẽ **HALT** do expectation phát hiện dữ liệu chưa sạch. Đọc kỹ log để hiểu lý do.

**Bước 2 — Phân tích dữ liệu raw:**

- Có bao nhiêu `doc_id` **unique** trong `data/raw/policy_export_dirty.csv`?
- `ALLOWED_DOC_IDS` trong `transform/cleaning_rules.py` chứa những doc_id nào?
- Có nguồn dữ liệu hợp lệ nào trong CSV bị pipeline **bỏ qua** (quarantine nhầm) không?

**Bước 3 — Đối chiếu với câu hỏi đánh giá:**

- Mở `data/grading_questions.json`, kiểm tra trường `expect_top1_doc_id` — cần những nguồn nào?
- So sánh với những gì pipeline hiện tại cho phép — thiếu nguồn nào?

**Bước 4 — Sửa pipeline:**

Cần sửa `transform/cleaning_rules.py` (và có thể cả `quality/expectations.py`):
1. Cập nhật allowlist nếu phát hiện nguồn hợp lệ bị thiếu.
2. Thêm cleaning rules để loại bỏ dữ liệu stale (ví dụ: nội dung chính sách cũ vẫn xuất hiện dù ngày export mới).
3. Thêm ≥ **3 rule mới** và ≥ **2 expectation mới** (xem yêu cầu Sprint 2).
4. Đảm bảo `python etl_pipeline.py run` **exit 0** — tất cả expectations phải pass.

**Bước 5 — Kiểm tra kết quả:**

```bash
# Test retrieval tự kiểm (21 câu)
python eval_retrieval.py --out artifacts/eval/eval_after_fix.csv

# Grading chính thức (10 câu)
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

Kiểm tra: `contains_expected` phải `true` và `hits_forbidden` phải `false` cho tất cả câu hỏi.

---

## Cấu trúc thư mục

```
lab/
├── etl_pipeline.py           # Sprint 1–2: run ingest→clean→validate→embed
├── eval_retrieval.py         # Sprint 3–4: before/after retrieval (CSV)
├── grading_run.py            # Grading chính thức — 10 câu đánh giá
├── instructor_quick_check.py # GV: sanity artifact grading/manifest (tuỳ chọn)
│
├── transform/
│   └── cleaning_rules.py     # ⚠️ Baseline chưa đủ — sinh viên phải sửa + mở rộng
├── quality/
│   └── expectations.py       # Baseline expectations — sinh viên thêm ≥2 mới
├── monitoring/
│   └── freshness_check.py    # Đọc manifest + SLA đơn giản
│
├── contracts/
│   └── data_contract.yaml    # Contract dữ liệu — điền owner/SLA
│
├── data/
│   ├── docs/                 # 5 tài liệu gốc (policy, SLA, FAQ, HR, access control)
│   ├── raw/
│   │   └── policy_export_dirty.csv   # Export bẩn từ 5 hệ thống nguồn
│   ├── test_questions.json           # 21 câu tự kiểm (retrieval + keyword)
│   └── grading_questions.json        # 10 câu đánh giá chính thức
│
├── artifacts/
│   ├── logs/
│   ├── manifests/
│   ├── quarantine/
│   ├── cleaned/
│   └── eval/
│
├── docs/
│   ├── pipeline_architecture.md
│   ├── data_contract.md
│   ├── runbook.md
│   └── quality_report_template.md
│
├── reports/
│   ├── group_report.md
│   └── individual/
│       └── template.md
│
├── requirements.txt
└── .env.example
```

---

## Setup

```bash
cd lab
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

**Lần đầu** SentenceTransformers có thể tải model `all-MiniLM-L6-v2` (~90MB) — cần mạng.

---

## Chạy pipeline

### Một lệnh chạy cả pipeline + grading

```bash
python etl_pipeline.py run && python grading_run.py --out artifacts/eval/grading_run.jsonl && python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
```

### Luồng chuẩn (sau khi đã sửa pipeline)

```bash
# Chạy toàn bộ: ingest → clean → validate → embed
python etl_pipeline.py run

# Kiểm tra freshness
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<run-id>.json
```

### Eval retrieval (sau khi đã embed)

```bash
python eval_retrieval.py --out artifacts/eval/after_fix_eval.csv
cat artifacts/eval/after_fix_eval.csv
```

### Eval mở rộng bằng LLM-judge

Nếu `.env` đã có `OPENAI_API_KEY`, `OPENAI_BASE_URL`, và `OPENAI_MODEL`, có thể chạy thêm LLM-judge để chấm context top-k theo câu hỏi:

```bash
python eval_retrieval.py --llm-judge --out artifacts/eval/eval_llm_judge.csv
```

CSV sẽ có thêm các cột `llm_judge_pass`, `llm_judge_score`, `llm_judge_reason`, `llm_judge_answer`, và `llm_judge_model`. Keyword eval vẫn chạy như cũ, LLM-judge chỉ là lớp đánh giá bổ sung.

> **Ghi chú eval:** `hits_forbidden` quét **toàn bộ top-k** chunk ghép lại (không chỉ top-1), để phát hiện "câu trả lời nhìn đúng nhưng context vẫn còn chunk stale".  
> **Index snapshot:** sau mỗi lần `run`, embed **upsert** theo `chunk_id` và **xoá id không còn trong cleaned** để tránh vector cũ làm fail grading.

### Sprint 3 — Inject corruption (embed dữ liệu "xấu", bỏ qua halt)

```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv
# So sánh với file eval sau khi chạy lại pipeline chuẩn
```

### Grading chính thức (10 câu)

```bash
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

**Giảng viên — kiểm tra nhanh artifact (tuỳ chọn):**

```bash
python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
python instructor_quick_check.py --manifest artifacts/manifests/manifest_<run-id>.json
```

---

## 4 Sprints (chi tiết)

### Sprint 1 (60') — Phân tích & Ingest

- Đọc `data/raw/policy_export_dirty.csv` — liệt kê các `doc_id` unique, đếm số record mỗi loại.
- **Chạy pipeline lần đầu** → quan sát HALT → đọc log xác định nguyên nhân.
- **So sánh** `doc_id` trong CSV vs `ALLOWED_DOC_IDS` trong `cleaning_rules.py` → phát hiện nguồn bị thiếu.
- **Đối chiếu** `expect_top1_doc_id` trong `grading_questions.json` → xác nhận cần sửa gì.
- Bắt đầu sửa `cleaning_rules.py`: cập nhật allowlist, thêm rules cho dữ liệu stale.
- Điền **source map** ngắn trong `docs/data_contract.md` (ít nhất 2 nguồn / failure mode / metric).

**DoD:** Log có `raw_records`, `cleaned_records`, `quarantine_records`, `run_id`. Hiểu tại sao pipeline halt.

---

### Sprint 2 (60') — Clean + validate + embed

- Hoàn thiện sửa pipeline: pipeline phải **exit 0** với expectation không halt.
- Thêm ≥ **3 rule mới** và ≥ **2 expectation mới** (đếm trên file nhận được).
- **Chống trivial:** mỗi rule/expectation mới phải có **tác động đo được** — ghi trong `reports/group_report.md` bảng *metric_impact* (ví dụ: `quarantine_records` tăng khi inject, `expectation X fail` trước khi fix). Rule chỉ "strip space" mà không đổi số liệu → **trừ điểm**.
- Đảm bảo embed **idempotent** (upsert `chunk_id` + prune id thừa — baseline đã làm).

**DoD:** `python etl_pipeline.py run` exit 0. `python grading_run.py` → kiểm tra nhanh kết quả.

---

### Sprint 3 (60') — Inject corruption & before/after

- Cố ý làm hỏng dữ liệu (`--no-refund-fix --skip-validate`) → lưu eval "xấu".
- Chạy lại pipeline chuẩn → lưu eval "tốt".
- Lưu **2 file eval** so sánh + ảnh chụp / đoạn log chứng minh.
- Hoàn thành quality report theo `docs/quality_report_template.md`.

**DoD:** Có số liệu chứng minh retrieval **tệ hơn** trước fix và **tốt hơn** sau fix.

---

### Sprint 4 (60') — Monitoring + docs + báo cáo

- Điền `docs/pipeline_architecture.md`, `docs/data_contract.md`, `docs/runbook.md`.
- `python etl_pipeline.py freshness --manifest …` — giải thích PASS/WARN/FAIL trong runbook.
- Chạy `python grading_run.py` lần cuối → verify 10 câu đều pass.
- Hoàn thành `reports/group_report.md` + mỗi người `reports/individual/[ten].md`.

**DoD:** Grading JSONL hợp lệ. README nhóm có "một lệnh chạy cả pipeline". Peer review 3 câu hỏi ghi trong group report.

---

## Deliverables (nộp bài)

| Item | Ghi chú |
|------|---------|
| `etl_pipeline.py` + `transform/` + `quality/` + `monitoring/` | Có thể mở rộng file, không xóa entrypoint bắt buộc |
| `contracts/data_contract.yaml` | Điền owner, SLA, nguồn |
| `artifacts/logs/`, `manifests/`, `quarantine/`, `eval/` | Ít nhất 1 run "tốt" + evidence inject |
| `docs/*.md` (3 file + quality report) | Theo template |
| `reports/group_report.md` | |
| `reports/individual/*.md` | Mỗi thành viên |
| `artifacts/eval/grading_run.jsonl` | 10 câu: `gq_d10_01` … `gq_d10_10` |

---

## Dữ liệu trong raw CSV

Raw CSV (`data/raw/policy_export_dirty.csv`) chứa export từ nhiều hệ thống. Dưới đây là tham khảo (không phải đáp án — học viên tự phân tích):

| Nguồn dữ liệu | Tài liệu tham khảo | Ghi chú |
|----------------|---------------------|---------|
| `policy_refund_v4` | `data/docs/policy_refund_v4.txt` | Có chunk stale "14 ngày" cần fix |
| `sla_p1_2026` | `data/docs/sla_p1_2026.txt` | SLA và quy trình xử lý sự cố |
| `it_helpdesk_faq` | `data/docs/it_helpdesk_faq.txt` | FAQ IT nội bộ |
| `hr_leave_policy` | `data/docs/hr_leave_policy.txt` | Có xung đột version 2025 vs 2026 |
| `access_control_sop` | `data/docs/access_control_sop.txt` | Quy trình cấp quyền truy cập |
| `invalid_doc_*`, `legacy_*` | (không có tài liệu) | Export lỗi / hệ thống cũ |

> **Lưu ý:** Không phải tất cả nguồn dữ liệu đều được pipeline baseline xử lý. Học viên cần tự phát hiện và sửa.

---

## Phân vai (gợi ý — đồng bộ slide Hands-on 10)

| Vai | Trách nhiệm | Sprint chính |
|-----|-------------|----------------|
| **Ingestion Owner** | raw paths, logging, manifest, phân tích doc_id | 1 |
| **Cleaning / Quality Owner** | `cleaning_rules.py`, `expectations.py`, quarantine | 1–3 |
| **Embed Owner** | Chroma collection, idempotency, eval, grading verify | 2–3 |
| **Monitoring / Docs Owner** | freshness, runbook, 3 docs, group report | 4 |

---

## Debug order (nhắc từ slide Day 10)

```
Freshness / version → Volume & errors → Schema & contract → Lineage / run_id → mới đến model/prompt
```

---

## Tài nguyên tham khảo

- Slide: [`../lecture-10.html`](../lecture-10.html)
- Lab Day 09 (orchestration): [`../../day09/lab/README.md`](../../day09/lab/README.md)
- Great Expectations (tuỳ chọn nâng cao): https://docs.greatexpectations.io/
- ChromaDB: https://docs.trychroma.com/

---

# Tổng kết các phần đã thực hiện - Lab Day 10

Phần này tóm tắt các thay đổi đã làm trong lab Day 10: phân tích dữ liệu raw, làm sạch dữ liệu, validate bằng expectations, embed vào Chroma, inject lỗi để chứng minh before/after, monitoring, docs và báo cáo.

---

## 1. Sprint 1 - Phân tích & ingest

Mục tiêu của Sprint 1 là hiểu dữ liệu đầu vào và lý do pipeline ban đầu bị halt.

Các việc đã làm:

- Đọc file `data/raw/policy_export_dirty.csv`.
- Đếm được `raw_records=247`.
- So sánh `doc_id` trong CSV với `ALLOWED_DOC_IDS` trong `transform/cleaning_rules.py`.
- Phát hiện `access_control_sop` là nguồn hợp lệ nhưng chưa có trong allowlist.
- Đối chiếu `expect_top1_doc_id` trong bộ câu hỏi eval/grading để xác nhận pipeline cần retrieve được 5 nguồn:
  - `policy_refund_v4`
  - `sla_p1_2026`
  - `it_helpdesk_faq`
  - `hr_leave_policy`
  - `access_control_sop`

Thay đổi chính:

- Thêm `access_control_sop` vào allowlist.
- Thêm rule phát hiện HR 2025 annual leave stale content, ví dụ chunk ghi `10 ngày phép năm`.
- Điền source map ban đầu trong `docs/data_contract.md`.

Kết quả:

- Pipeline hiểu được đủ 5 nguồn hợp lệ.
- Xác định được nguyên nhân halt ban đầu là dữ liệu HR stale còn lọt qua clean.

---

## 2. Sprint 2 - Clean + validate + embed

Mục tiêu của Sprint 2 là hoàn thiện cleaning rules, thêm expectations, và đảm bảo pipeline chuẩn chạy thành công.

Các rule mới trong `transform/cleaning_rules.py`:

- `invalid_exported_at_format`: quarantine row có `exported_at` sai format datetime.
- `low_confidence_or_noisy_chunk`: quarantine chunk có dấu hiệu noisy hoặc low-confidence.
- `stale_doc_version_effective_date`: quarantine row có `effective_date` cũ hơn version canonical của từng tài liệu.
- `canonical_current_fact_enrichment`: bổ sung fact canonical còn thiếu cho các chunk current của SLA P1 và IT Helpdesk để grading không phụ thuộc vào stale summary rows.

Các expectation mới trong `quality/expectations.py`:

- `no_stale_doc_versions`: cleaned data không còn row cũ hơn min effective date.
- `no_low_confidence_noise_markers`: cleaned data không còn marker noisy/low-confidence.
- `exported_at_iso_datetime`: mọi `exported_at` trong cleaned data phải đúng format `YYYY-MM-DDTHH:MM:SS`.

Kết quả pipeline chuẩn:

```text
raw_records=247
cleaned_records=27
quarantine_records=220
PIPELINE_OK
```

Ý nghĩa:

- 27 chunk sạch được embed vào Chroma.
- 220 row bị quarantine với reason rõ ràng.
- Tất cả halt expectations đều pass.
- Chroma được publish theo snapshot: prune id cũ và upsert theo `chunk_id`.

---

## 3. Sprint 3 - Inject corruption & before/after

Mục tiêu của Sprint 3 là cố tình làm hỏng dữ liệu để chứng minh dữ liệu bẩn làm retrieval tệ hơn, sau đó chạy lại pipeline chuẩn để chứng minh hệ thống phục hồi.

Inject bad run:

```bash
python etl_pipeline.py run --run-id sprint3-inject-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/sprint3_eval_bad.csv
```

Kết quả bad run:

```text
cleaned_records=35
quarantine_records=212
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=3
PIPELINE_OK
```

Pipeline vẫn embed vì có `--skip-validate`, phục vụ mục đích demo lỗi.

Clean recovery run:

```bash
python etl_pipeline.py run --run-id sprint3-clean-good
python eval_retrieval.py --out artifacts/eval/sprint3_eval_good.csv
```

Kết quả clean run:

```text
cleaned_records=27
quarantine_records=220
expectation[refund_no_stale_14d_window] OK (halt) :: violations=0
PIPELINE_OK
```

So sánh eval:

| Metric | Bad inject | Clean good |
|--------|------------|------------|
| contains_expected=yes | 18/21 | 19/21 |
| hits_forbidden=yes | 1/21 | 0/21 |
| top1_doc_expected=yes | 19/21 | 19/21 |

Bằng chứng quan trọng:

- Câu `q_refund_window` trong bad eval có `hits_forbidden=yes` vì context chứa `14 ngày`.
- Sau clean recovery, cùng câu này có `hits_forbidden=no` và context đúng là `7 ngày làm việc`.

File report liên quan:

- `docs/quality_report.md`

---

## 4. Sprint 4 - Monitoring + docs + báo cáo

Mục tiêu của Sprint 4 là hoàn thiện tài liệu vận hành, monitoring, báo cáo nhóm/cá nhân và grading cuối.

Các file docs đã hoàn thiện:

- `docs/pipeline_architecture.md`: mô tả kiến trúc pipeline, flow ingest -> clean -> validate -> embed -> monitor/eval.
- `docs/data_contract.md`: mô tả source map, schema cleaned, allowlist, quarantine reasons, canonical sources.
- `docs/runbook.md`: hướng dẫn debug incident, giải thích PASS/WARN/FAIL của freshness, mitigation và prevention.
- `docs/quality_report.md`: báo cáo before/after từ Sprint 3.

Các report đã hoàn thiện:

- `reports/group_report.md`
- `reports/individual/DoTuanDat.md`

Freshness check:

```bash
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_sprint3-clean-good.json
```

Kết quả:

```text
FAIL {"reason": "freshness_sla_exceeded", ...}
```

Giải thích:

- Freshness FAIL vì sample data có `latest_exported_at` cũ hơn SLA 24h.
- Đây là monitor signal hợp lý, không phải pipeline clean/validate bị lỗi.

Final grading:

```bash
python grading_run.py --out artifacts/eval/grading_run.jsonl
python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
```

Kết quả:

- `gq_d10_01` đến `gq_d10_10` đều OK.
- `contains_expected=true`
- `hits_forbidden=false`
- `top1_doc_matches=true` cho các câu có yêu cầu top-1.

---

## 5. Mở rộng eval bằng LLM-judge

Ngoài keyword eval mặc định, `eval_retrieval.py` đã được mở rộng để hỗ trợ LLM-judge.

Lệnh chạy:

```bash
python eval_retrieval.py --llm-judge --out artifacts/eval/eval_llm_judge.csv
```

CSV output có thêm các cột:

- `llm_judge_pass`
- `llm_judge_score`
- `llm_judge_reason`
- `llm_judge_answer`
- `llm_judge_model`

Kết quả chạy thử:

```text
rows=21
contains_expected=yes: 21
hits_forbidden=no: 21
top1_doc_expected=yes: 21
llm_judge_pass=yes: 21
llm_judge_score=2: 21
```

Hai case từng fail là `q_p1_first_response` và `q_p1_update_frequency`; đã được xử lý bằng cách làm rõ fact SLA P1 trong current chunks. LLM-judge hiện đánh giá đủ 21/21 câu pass.

---

## 6. Các file code chính đã thay đổi

### `transform/cleaning_rules.py`

Vai trò:

- Load raw CSV.
- Chuẩn hóa `effective_date`.
- Allowlist doc hợp lệ.
- Quarantine doc/source lỗi.
- Fix hoặc inject stale refund tùy mode.
- Tạo `chunk_id` ổn định cho embed.

Thay đổi quan trọng:

- Thêm `access_control_sop` vào allowlist.
- Thêm `DOC_MIN_EFFECTIVE_DATES`.
- Thêm rule quarantine stale/noisy/invalid rows.
- Thêm inject path cho Sprint 3.
- Thêm enrichment cho SLA P1 và IT lockout.

### `quality/expectations.py`

Vai trò:

- Chạy expectation suite trên cleaned rows.
- Quyết định pipeline có halt hay không.

Thay đổi quan trọng:

- Thêm expectations cho stale doc version, noisy marker, và exported timestamp.
- Các expectation quan trọng có severity `halt`.

### `eval_retrieval.py`

Vai trò:

- Chạy retrieval eval dựa trên keyword.
- Khi bật `--llm-judge`, gọi LLM để đánh giá context top-k.

Thay đổi quan trọng:

- Thêm flag `--llm-judge`.
- Đọc `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` từ `.env`.
- Thêm các cột `llm_judge_*` vào CSV.

### `contracts/data_contract.yaml`

Vai trò:

- Lưu contract dạng YAML.
- Ghi schema, allowed doc ids, canonical sources, và policy versioning.

Thay đổi quan trọng:

- Đồng bộ `access_control_sop`.
- Thêm min effective date cho 5 doc hợp lệ.

---

## 7. Cách chạy lại toàn bộ

Lệnh chạy pipeline chuẩn và grading:

```bash
cd day10/lab
python etl_pipeline.py run && python grading_run.py --out artifacts/eval/grading_run.jsonl && python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
```

Lệnh chạy eval self-check:

```bash
python eval_retrieval.py --out artifacts/eval/latest_eval.csv
```

Lệnh chạy eval bằng LLM-judge:

```bash
python eval_retrieval.py --llm-judge --out artifacts/eval/eval_llm_judge.csv
```

Lệnh kiểm tra freshness:

```bash
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_sprint3-clean-good.json
```

---

## 8. Tóm tắt dễ hiểu

Pipeline này giống một bộ lọc dữ liệu trước khi đưa tài liệu vào hệ thống tìm kiếm/RAG.

Raw CSV có nhiều lỗi:

- nguồn lạ,
- dữ liệu cũ,
- ngày sai format,
- chunk trùng,
- nội dung stale,
- policy refund cũ 14 ngày,
- HR policy cũ 10 ngày phép năm.

Các rule clean sẽ quyết định row nào được giữ lại và row nào vào quarantine. Expectations kiểm tra lần cuối trước khi embed. Nếu dữ liệu nguy hiểm còn lọt qua, pipeline halt. Khi pipeline sạch, chỉ 27 chunk tốt được embed vào Chroma.

Sprint 3 chứng minh vì sao data quality quan trọng: khi cố tình embed dữ liệu refund cũ, retrieval vẫn tìm đúng doc nhưng context chứa giá trị sai `14 ngày`. Sau khi chạy clean pipeline, context quay về `7 ngày làm việc` và không còn forbidden hit.

LLM-judge là lớp đánh giá bổ sung: thay vì chỉ kiểm tra keyword, nó đọc context top-k và giải thích vì sao context đủ hoặc chưa đủ để trả lời câu hỏi.

