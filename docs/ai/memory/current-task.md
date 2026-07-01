# Current Task

## Task hiện tại

Chuẩn bị migration phone mode từ `android_phone_farm` sang `RegisterBot -> XiaoWei API` và hoàn thiện bộ công cụ test/diagnostics để team test thật trên máy Windows Nhật.

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

## Next action

- Chạy tiếp `Phase 3` trên máy Windows Nhật có XiaoWei runtime thật
- Ưu tiên thứ tự:
  - dashboard test connection
  - `python main.py --diagnose-xiaowei`
  - runtime verify `adb`
  - runtime verify app open/start
  - end-to-end 1 account
