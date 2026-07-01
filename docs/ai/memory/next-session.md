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

1. Pull the latest repo state on the Japan Windows machine because there is a new Step-1 false-negative fix:
   - broader Amazon product-page fingerprint
   - `preferred_region` scoring bug fix
2. Re-run one real Amazon registration account on XiaoWei.
3. Confirm specifically:
   - bot no longer stops at `Wrong page detected...` when already on a real Amazon product page
   - bot can continue from Step 1 to `Request Invitation`
4. If Step 1 passes:
   - continue evaluating click/input stability on the next steps
   - then move toward full end-to-end verification

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
  - retest fix `wrong_page_detected` false-negative trên Amazon product page thật
  - xác nhận bước `Request Invitation` sau khi Step 1 pass
  - verify `startApk` / app-open runtime thật
  - chạy 1 account end-to-end
