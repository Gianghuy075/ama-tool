# Test Evidence

| Date | Task | Command/Step | Result | Evidence |
|---|---|---|---|---|
| 2026-06-30 | Legacy context migration audit | `rg`, `find`, `sed` đối chiếu docs và source | Completed | Session audit của Codex |
| 2026-06-30 | XiaoWei integration repo preparation | `python3 -m py_compile`, cập nhật adapter/UI/diagnostics/runbook | Completed ở mức repo, chưa có runtime Windows | `docs/ai/plans/xiaowei-direct-integration-plan.md`, `docs/ai/plans/xiaowei-windows-jp-runbook.md` |
| 2026-06-30 | XiaoWei official API common contract retrieval | `GET https://www.xiaowei.xin/api/manual/article?id=234` | Confirmed official WS endpoint `ws://127.0.0.1:22222/` và request/response fields chung | `docs/ai/plans/xiaowei-api-contract-notes.md` |
| 2026-07-01 | XiaoWei Phase 2 config switch | cập nhật `data/config.json` + fallback defaults trong code | Completed | `RegisterBot_Package/data/config.json`, `RegisterBot_Package/src/config.py`, `RegisterBot_Package/src/web_server.py`, `RegisterBot_Package/src/xiaowei_client.py` |
| 2026-07-01 | XiaoWei CLI diagnostics on Mac dev machine | `cd RegisterBot_Package && python3 main.py --diagnose-xiaowei` | CLI path OK, fail đúng chỗ connect `ws://127.0.0.1:22222/` vì không có XiaoWei runtime local | JSON report in terminal: `overall_success=false`, step `get_devices=false` |
| 2026-06-28 | Accuracy improvements implementation | Legacy AI session log | Claimed syntax check OK, runtime test chưa xác nhận | `docs/ai/source/legacy-agent-context/08-session-history.legacy.md` |
| 2026-06-27 đến 2026-06-28 | End-to-end runtime evidence cũ | Screenshots/log/build artifacts được nhắc trong docs cũ | Partial evidence | `docs/project/source/raw-notes/07-current-status.legacy.md`, `docs/ai/source/legacy-agent-context/08-session-history.legacy.md`, `logs/` |
