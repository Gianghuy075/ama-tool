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
- `cd RegisterBot_Package && python main.py --diagnose-xiaowei` trên máy Windows Nhật
  - `overall_success=true`
  - pass: `get_devices`, `adb_wm_size`, `adb_pm_list_packages`, `uiautomator_dump`, `ui_text_probe`
  - screenshot vẫn không tạo file local nhưng đã hạ xuống warning non-blocking

## Next action

- Tiếp tục `Phase 5` trên máy Windows Nhật có XiaoWei runtime thật
- Ưu tiên thứ tự:
  - khóa đúng `browser surface`:
    - không bị handoff sang `Amazon Shopping app`
    - foreground phải là `Chrome mobile web`
    - dismiss `Chrome first-run` / `Translate page` infobar nếu có
  - tách rõ `product page visible` với `CTA clickable`
  - locator lại nút CTA theo `anchor -> button below anchor -> verify -> back -> retry`
  - retest `sign-in mobile web` với patch mới:
    - nhận đúng `signin_entry`
    - nhập đúng ô `Enter mobile number or email`
    - bấm đúng nút vàng `Continue`
    - phân biệt rõ `create_account_prompt` / `register_form` / `password_login`
  - retest lại `product CTA search` với patch mới:
    - nhận `Request invite`/`Available by invitation`
    - không scroll preset mù
    - dùng short-sweep có overlap
    - log viewport signature để biết bot đã quét tới đâu
    - loại bỏ node bounds `0,0`
    - xác nhận anchor fallback không còn tap gần đầu màn hình
  - retest false-positive guard:
    - nếu chưa vào `signin_entry` thật thì bot phải dừng
    - tuyệt đối không được gõ email vào ô search của product page
  - runtime verify app open/start
  - runtime verify tap/swipe/type_text
  - end-to-end 1 account
