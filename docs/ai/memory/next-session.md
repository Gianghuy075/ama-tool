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

1. Phase 3 is partially complete with real Windows JP runtime evidence:
   - `get_devices`, `adb`, `uiautomator dump` already passed
2. Pull the latest fix for screenshot handling on the Japan Windows machine.
3. Re-run:
   - `cd RegisterBot_Package`
   - `python main.py --diagnose-xiaowei`
4. If screenshot also passes:
   - move to app-open/runtime verification
   - then run one full end-to-end registration account

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
  - xác nhận screenshot pass với patch `screenFile` fallback `screen`
  - verify `startApk` / app-open runtime thật
  - chạy 1 account end-to-end
