# Next Session

## XiaoWei Phase 1 status

- Phase 1 is no longer blocked on basic official contract discovery.
- Confirmed official common contract:
  - endpoint family uses WebSocket
  - Windows JP runtime assumption still `ws://127.0.0.1:22222/`
  - common codes: `10000=success`, `10001=request failed`
- Confirmed Android handbook action docs:
  - `401` list
  - `403` screen
  - `404` screenFile
  - `413` inputText
  - `422` pointerEvent
  - `351` feature-list article with canonical actions including `adb`, `pushEvent`, `startApk`, `stopApk`

## Important caution

- Vendor detail pages contain copy/paste mistakes.
- Do not trust single detail articles blindly when they conflict with feature-list article `351`.
- `adb` and `startApk` still need runtime verification on Windows JP machine.

## Recommended next step

1. Giữ đúng thứ tự của nhánh `feature/xiaowei-e2e-readiness`:
   - trước hết hoàn thành `XiaoWei direct integration baseline`
   - sau đó mới tiếp tục `Amazon flow hardening`
2. Re-run trên máy Windows Nhật nhưng đánh giá theo baseline trước:
   - mở đúng `Chrome`
   - mở đúng `product_url`
   - không bị app handoff / false-positive state
   - runtime action `tap/swipe/type/open_url/open_app` có evidence thật
3. Chỉ khi baseline trên ổn mới tiếp tục đánh giá:
   - `Request Invitation` CTA
   - sign-in / create-account / register-form
4. Nếu bot vẫn log state sai khác runtime thật:
   - dừng vá thêm heuristic
   - rebaseline hoặc rollback phần hardening gây lệch state

## Reset đã thực hiện

- Plan cải tiến CTA/sign-in cũ đã được đánh dấu là `fail ở observation/runtime verification`.
- `RegisterBot_Package/src/phone_bot.py` đã rollback về snapshot `65a9085`.
- Phần được giữ lại:
  - `Chrome loading/network recovery`
  - `open_url -> verify product page -> open CTA flow` baseline
- Phần đã bỏ:
  - `signin_entry/create_account_prompt/register_form/password_login` state machine
  - `Request invite` / `Available by invitation` heuristic mới
  - `short-sweep` / `first-fold CTA probe`
  - các false-positive guard được dựng trên observation layer không đáng tin

## Bắt đầu từ đâu?

1. Đọc `docs/ai/standards/context-loading-policy.md`
2. Đọc `docs/ai/memory/current-task.md`
3. Đọc `docs/ai/memory/known-issues.md`
4. Nếu làm việc với nghiệp vụ account flow, đọc thêm `docs/project/03_user-flows.md` và `docs/project/04_business-rules.md`

## Context cần đọc

- `docs/ai/standards/context-loading-policy.md`
- `docs/ai/memory/current-task.md`
- `docs/ai/memory/known-issues.md`
- `docs/project/08_roadmap.md`

## Việc còn lại

- Tiếp tục plan XiaoWei tại `docs/ai/plans/xiaowei-direct-integration-plan.md`
- Ưu tiên:
  - khóa lại baseline XiaoWei thật trên Windows JP
  - verify `startApk` / `open_app` / `open_url` / `tap` / `swipe` / `type_text`
  - chạy được 1 account thật với backend XiaoWei
  - sau đó mới quay lại `Request Invitation` + sign-in hardening
