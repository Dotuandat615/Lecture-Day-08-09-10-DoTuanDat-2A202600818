# Báo Cáo Cá Nhân - Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Đỗ Tuấn Đạt  
**Vai trò:** Cleaning / Quality / Embed verification / Monitoring docs  
**Ngày nộp:** 2026-06-10

---

## 1. Tôi phụ trách phần nào?

Tôi phụ trách chính phần clean và quality gate cho pipeline Day 10. Các file tôi sửa gồm `transform/cleaning_rules.py`, `quality/expectations.py`, `contracts/data_contract.yaml`, `docs/data_contract.md`, `docs/runbook.md`, `docs/pipeline_architecture.md`, `docs/quality_report.md`, và `reports/group_report.md`. Phần clean bổ sung allowlist `access_control_sop`, quarantine HR 2025 annual leave, quarantine stale doc version, noisy chunk, invalid exported timestamp, và enrich canonical facts cho SLA P1 / IT lockout. Phần quality thêm halt expectations để đảm bảo cleaned output không còn stale/noisy rows trước khi embed.

Bằng chứng chính là run `sprint3-clean-good`: log có `raw_records=247`, `cleaned_records=27`, `quarantine_records=220`, tất cả expectation halt OK, `embed_prune_removed=35`, `embed_upsert count=27`, và `PIPELINE_OK`.

---

## 2. Một quyết định kỹ thuật

Quyết định quan trọng nhất là tách hai chế độ: publish chuẩn và inject demo. Publish chuẩn không được dùng `--skip-validate`; nếu expectation halt fail thì pipeline dừng trước embed. Inject Sprint 3 lại có chủ đích dùng `--no-refund-fix --skip-validate` để chứng minh stale data gây hại cho retrieval. Để làm việc này sau Sprint 2, tôi thêm helper `_inject_dirty_refund`: chỉ khi tắt refund fix, refund dirty rows mới bỏ qua một số quarantine rule và có thể vào cleaned output. Các doc khác vẫn bị clean như cũ. Cách này giữ production path an toàn, nhưng vẫn tạo được before/after evidence thật cho rubric.

---

## 3. Một lỗi hoặc anomaly đã xử lý

Anomaly ban đầu là pipeline sau Sprint 2 quá sạch nên `--no-refund-fix` không còn làm hỏng retrieval: các refund rows 14 ngày đã bị quarantine trước khi refund fix có cơ hội chạy. Nếu giữ nguyên, Sprint 3 sẽ không có bằng chứng "bad eval". Fix của tôi là chỉ mở dirty path cho `policy_refund_v4` khi `apply_refund_window_fix=False`. Bad run `sprint3-inject-bad` sau đó có `refund_no_stale_14d_window FAIL (halt) :: violations=3`, nhưng vẫn embed vì `--skip-validate`. Clean run `sprint3-clean-good` phục hồi về `violations=0`.

---

## 4. Bằng chứng trước / sau

Bad run:

```text
run_id=sprint3-inject-bad
cleaned_records=35
quarantine_records=212
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=3
```

Good run:

```text
run_id=sprint3-clean-good
cleaned_records=27
quarantine_records=220
expectation[refund_no_stale_14d_window] OK (halt) :: violations=0
```

Eval `q_refund_window`: bad file `artifacts/eval/sprint3_eval_bad.csv` có `hits_forbidden=yes` vì top preview chứa `14 ngày làm việc`; good file `artifacts/eval/sprint3_eval_good.csv` có `contains_expected=yes`, `hits_forbidden=no`, top preview là `7 ngày làm việc`.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ thêm một script tổng hợp artifact tự động: đọc log, manifest, eval CSV, grading JSONL và sinh bảng markdown cho quality report. Việc này giảm lỗi copy tay và giúp peer review nhanh hơn khi có nhiều run_id.
