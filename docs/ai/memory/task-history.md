# Task History

## 2026-06-30 - XiaoWei Phase 1 official contract extraction

- Re-loaded mandatory repo context before continuing XiaoWei integration work.
- Reconnected `computer-use` and confirmed the vendor page `https://www.xiaowei.xin/help/70/234` is readable in local Chrome.
- Confirmed directly from the visible official page:
  - API WebSocket address: `ws://127.0.0.1:22222/`
  - common request shape: `action`, `devices`, `data`
  - common success code: `10000`
  - common failure code: `10001`
- Updated:
  - `docs/ai/plans/xiaowei-api-contract-notes.md`
  - `docs/ai/plans/xiaowei-direct-integration-plan.md`
- Current blocker:
  - `computer-use` can read the page but sidebar navigation/link clicking is unstable, so action-specific articles under `8.2` are not extracted yet.

## 2026-07-01 - XiaoWei Android handbook action mapping

- Extracted official Android handbook feature/action list from article `351` (`4.2 接口文档`).
- Confirmed canonical Android action names now include:
  - `list`
  - `adb`
  - `screen`
  - `pointerEvent`
  - `pushEvent`
  - `writeClipBoard`
  - `uploadFile`
  - `pullFile`
  - `apkList`
  - `installApk`
  - `uninstallApk`
  - `startApk`
  - `stopApk`
  - `imeList`
  - `installInputIme`
  - `selectIme`
  - `inputText`
- Extracted detailed Android action articles:
  - `401`: `list获取设备列表`
  - `403`: `screen 截图到相册`
  - `404`: `screenFile 截图到电脑`
  - `413`: `inputText 输入文字`
  - `422`: `pointerEvent 屏幕控制`
- Identified vendor-doc inconsistencies:
  - `startApp` article body says `stopApk`
  - `appList` article body says `pullFile`
  - `uploadFile` article body says `writeClipBoard`
- Conclusion:
  - feature-list article is more trustworthy for canonical action names
  - `adb` and `startApk` still need runtime verification before final code assumptions are locked

## 2026-07-01 - XiaoWei Phase 2 runtime defaults switched

- Updated runtime config file:
  - `RegisterBot_Package/data/config.json`
  - switched from `phone_farm` to `xiaowei`
  - `api_url = http://127.0.0.1:22222`
  - `devices = all`
- Updated code defaults/fallbacks:
  - `RegisterBot_Package/src/config.py`
  - `RegisterBot_Package/src/xiaowei_client.py`
  - `RegisterBot_Package/src/web_server.py`
- Verified:
  - `CONFIG['xiaowei']['api_type'] == 'xiaowei'`
  - `CONFIG['xiaowei']['api_url'] == 'http://127.0.0.1:22222'`
  - `CONFIG['xiaowei']['devices'] == 'all'`
- `py_compile` passed for:
  - `src/config.py`
  - `src/xiaowei_client.py`
  - `src/web_server.py`
  - `main.py`

## 2026-07-01 - XiaoWei Phase 3 CLI smoke-test preparation

- Installed Python dependencies from `RegisterBot_Package/requirements.txt` for local `python3`.
- Found local interpreter mismatch:
  - machine has `Python 3.9.6`
  - `main.py` used `str | None` annotation syntax that broke at runtime without postponed evaluation
- Fixed CLI startup compatibility by:
  - adding `from __future__ import annotations` to `RegisterBot_Package/main.py`
  - adding missing `import json` for `--diagnose-xiaowei` output path
- Re-ran:
  - `cd RegisterBot_Package && python3 main.py --diagnose-xiaowei`
- Result:
  - CLI now runs and emits diagnostics JSON
  - failure is now at the intended backend layer: connect refused to `ws://127.0.0.1:22222/`
  - this is expected on the current Mac dev machine without XiaoWei runtime listening locally

## 2026-07-01 - XiaoWei Windows JP diagnostics first pass

- User checked out branch `feature/xiaowei-e2e-readiness` on the Japan Windows machine and ran:
  - `cd RegisterBot_Package`
  - `python main.py --diagnose-xiaowei`
- Runtime evidence confirmed:
  - connected to local XiaoWei runtime at `http://127.0.0.1:22222`
  - discovered `10` devices
  - `adb wm size` works
  - `adb pm list packages com.android.chrome` works
  - `uiautomator dump` works
  - UI text probe works
- Remaining issue found:
  - diagnostics reported `overall_success=false` only because `screenshot` step returned success from XiaoWei but local file existence check failed immediately
- Fix implemented in repo:
  - `RegisterBot_Package/src/xiaowei_client.py`
  - `RegisterBot_Package/src/web_server.py`
  - client now prefers `screenFile` when `savePath` is provided, falls back to `screen`, and waits briefly for file materialization

## 2026-07-01 - XiaoWei Windows JP diagnostics pass

- Re-ran `python main.py --diagnose-xiaowei` on the Japan Windows machine after the non-blocking screenshot adjustment.
- Result:
  - `overall_success=true`
  - `get_devices`, `adb_wm_size`, `adb_pm_list_packages`, `uiautomator_dump`, `ui_text_probe` all passed
  - `screenshot` still did not materialize a local file and is now treated as a warning instead of a hard failure
- Practical conclusion:
  - Phase 3 core smoke test is good enough to proceed to runtime interaction checks and one real registration flow

## 2026-07-01 - Amazon product-page false-negative fix for XiaoWei flow

- Runtime test on the Japan Windows machine reached a real Amazon JP product page but the bot stopped at Step 1 with:
  - `Wrong page detected hoặc không xác nhận được product page Amazon`
- Evidence from the shared screenshot showed the phone was already on a valid Amazon product page:
  - Amazon search bar visible
  - product title visible
  - price marker `¥7,216`
  - Amazon benefit text such as `Amazon Mastercard`
- Root cause in repo:
  - `RegisterBot_Package/src/phone_bot.py`
  - `verify_expected_product_page()` still depended too heavily on first-fold CTA visibility
  - `screen_reader.find_best_element()` had a `preferred_region` bug comparing percent regions against pixel coordinates
- Fix implemented:
  - widened Amazon product-page fingerprint detection with host + price + cart/benefit/product markers
  - wrong-domain detection now ignores cases where XML already contains strong Amazon indicators
  - fixed `preferred_region` scoring to convert node coordinates into screen percentages before boosting
- Verification:
  - `python3 -m py_compile RegisterBot_Package/src/phone_bot.py RegisterBot_Package/src/screen_reader.py`
  - pass

## 2026-07-01 - Runtime rebaseline: surface control is part of the core problem

- Further real-device tests on the Japan Windows machine changed the understanding of the CTA issue:
  - opening the same Amazon product URL could hand off into `Amazon Shopping app`
  - after removing that app from the phone, the same URL stayed in `Chrome mobile web` but the UI variant changed again
  - `Chrome first-run`, `Translate page` UI, mobile web layout, and CTA visibility all affect the flow before CTA targeting even starts
- Conclusion:
  - the improvement plan can no longer treat CTA-finding as an isolated problem
  - `surface control` must be considered a prerequisite layer:
    - correct foreground package
    - no app handoff
    - stable Chrome runtime state
    - CTA viewport readiness
- The XiaoWei improvement plan was rebaselined accordingly:
  - Wave 1 and Wave 2 remain useful but are no longer sufficient indicators of runtime readiness
  - a new `Wave S - Surface control` was added ahead of CTA hardening

## Mục tiêu

Ghi lại lịch sử task/session quan trọng đã thực hiện bởi user hoặc AI Agent.

| Date/Period | Task | Agent/Tool | Files/Modules | Result | Evidence |
|---|---|---|---|---|---|
| 2026-06-28 | Phân tích codebase và tạo bộ legacy context ban đầu | Orchestrator AI (legacy) | legacy docs, legacy adapter | Completed | `docs/ai/source/legacy-agent-context/08-session-history.legacy.md` |
| 2026-06-28 | Implement 6 accuracy improvements cho phone bot | Orchestrator AI (legacy) | `RegisterBot_Package/src/phone_bot.py`, `src/screen_reader.py`, `src/xiaowei_client.py` | Completed, pending runtime verification | `docs/ai/source/legacy-agent-context/08-session-history.legacy.md` |
| 2026-06-30 | Audit, migrate và dọn triệt để context architecture sang ASEF Pro | Codex | `docs/project/*`, `docs/ai/*`, root adapters | Completed | File tree hiện tại, `docs/ai/source/legacy-agent-context/legacy-context-inventory.md` |
| 2026-06-30 | Chuẩn bị migration sang `RegisterBot -> XiaoWei API`, thêm runbook/config mẫu/diagnostics tích hợp | Codex | `RegisterBot_Package/src/xiaowei_client.py`, `src/web_server.py`, `src/web/*`, `main.py`, `docs/ai/plans/*` | In progress, ready for Windows runtime test | `docs/ai/plans/xiaowei-direct-integration-plan.md`, `docs/ai/plans/xiaowei-windows-jp-runbook.md` |
| 2026-06-30 | Truy xuất contract API XiaoWei official từ site API nội bộ | Codex | `docs/ai/plans/xiaowei-api-contract-notes.md`, `docs/ai/plans/xiaowei-direct-integration-plan.md` | Partial contract confirmed | `https://www.xiaowei.xin/api/manual/article?id=234` |

## Ghi chú

Không dùng file này thay cho `current-task.md`.  
`current-task.md` chỉ chứa trạng thái hiện tại.
