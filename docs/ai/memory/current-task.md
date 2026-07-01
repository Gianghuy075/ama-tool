# Current Task

## Task hiện tại

Chuẩn bị migration phone mode từ `android_phone_farm` sang `RegisterBot -> XiaoWei API` và hoàn thiện bộ công cụ test/diagnostics để team test thật trên máy Windows Nhật.

Ưu tiên hiện tại trên nhánh này:

1. Hoàn thành `XiaoWei direct integration baseline`
2. Chỉ sau đó mới tiếp tục `Amazon CTA/sign-in/register hardening`

## Trạng thái

in_progress

## Files touched

- `RegisterBot_Package/src/xiaowei_client.py`
- `RegisterBot_Package/src/web_server.py`
- `RegisterBot_Package/src/web/templates/index.html`
- `RegisterBot_Package/src/web/static/js/app.js`
- `RegisterBot_Package/src/web/static/css/style.css`
- `RegisterBot_Package/main.py`
- `RegisterBot_Package/data/config.json`
- `RegisterBot_Package/data/config.xiaowei.example.json`
- `docs/ai/plans/xiaowei-direct-integration-plan.md`
- `docs/ai/plans/xiaowei-windows-jp-runbook.md`
- `docs/ai/memory/current-task.md`
- `docs/ai/memory/task-history.md`
- `docs/ai/memory/test-evidence.md`

## Tests run

- `python3 -m py_compile` cho:
  - `RegisterBot_Package/src/xiaowei_client.py`
  - `RegisterBot_Package/src/web_server.py`
  - `RegisterBot_Package/src/phone_bot.py`
  - `RegisterBot_Package/src/config.py`
- `cd RegisterBot_Package && python3 main.py --diagnose-xiaowei`
  - pass tới lớp CLI/reporting
  - fail đúng chỗ connect `ws://127.0.0.1:22222/` trên máy Mac dev vì không có XiaoWei runtime local
- `cd RegisterBot_Package && python main.py --diagnose-xiaowei` trên máy Windows Nhật
  - `overall_success=true`
  - pass: `get_devices`, `adb_wm_size`, `adb_pm_list_packages`, `uiautomator_dump`, `ui_text_probe`
  - screenshot vẫn không tạo file local nhưng đã hạ xuống warning non-blocking

## Next action

- Tiếp tục `Phase 5` nhưng theo đúng thứ tự baseline:
  - ổn định lại `open Chrome -> open product URL -> giữ đúng surface`
  - runtime verify `open_app`, `open_url`, `tap`, `swipe`, `type_text`
  - xác nhận bot chạy được trên 1 device chỉ định bằng XiaoWei
  - chỉ khi baseline đó ổn mới tiếp tục hardening `CTA/sign-in/register`
- Không tiếp tục cộng dồn heuristic mới nếu runtime truth và internal state còn lệch nhau.
- Nếu patch hardening tạo false-positive state:
  - ưu tiên rebaseline/rollback phần đó
  - không cố vá tiếp trên assumption sai
- Trạng thái reset hiện tại:
  - `docs/ai/plans/xiaowei-direct-integration-plan.md` đã đánh dấu plan cải tiến CTA/sign-in hiện tại là fail
  - `RegisterBot_Package/src/phone_bot.py` đã được rollback về mốc `65a9085`
  - giữ lại các fix `Chrome loading/network surface recovery`
  - bỏ lớp `signin_entry/create_account_prompt/register_form/password_login` false-positive từ `90a951e` trở đi
