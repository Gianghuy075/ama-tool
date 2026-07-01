# Legacy Context Inventory

| File/Folder | Tool/Source đoán được | Loại nội dung | Giá trị hiện tại | Độ tin cậy | Nên chuyển sang đâu | Hành động đề xuất | Rủi ro |
|---|---|---|---|---|---|---|---|
| `CLAUDE.md` cũ | Claude/AI agent cũ | AI operation rules + adapter + routing | Cao | High | Root `CLAUDE.md` mới + `docs/ai/source/legacy-agent-context/CLAUDE.legacy.md` | Đã archive và thay bằng adapter mỏng mới | Legacy links bên trong chỉ còn giá trị lịch sử |
| `document-agent-root/01..06` | AI/team | product/business docs + technical docs | Cao | High | `docs/project/*`, `docs/ai/knowledge/*`, `docs/project/source/legacy-docs/*.legacy.md` | Đã migrate và archive | Có thể còn lệch nhỏ so với code mới |
| `document-agent-root/07-current-status.md` | AI/team | roadmap + session snapshot | Trung bình | Medium | `docs/project/08_roadmap.md`, `docs/ai/memory/*`, `docs/project/source/raw-notes/07-current-status.legacy.md` | Đã migrate và archive | Nội dung trạng thái đã cũ |
| `document-agent-root/08-session-history.md` | AI agent cũ | task log/session memory | Cao | High | `docs/ai/memory/task-history.md`, `docs/ai/source/legacy-agent-context/08-session-history.legacy.md` | Đã migrate và archive | Có thể chứa quyết định cũ |
| `document-agent-root/improvement-plan-accuracy.md` | AI/team | roadmap + technical plan + test evidence | Cao | High | `docs/project/08_roadmap.md`, `docs/ai/memory/test-evidence.md`, `docs/project/source/raw-notes/improvement-plan-accuracy.legacy.md` | Đã migrate và archive | Nếu đọc riêng lẻ vẫn là note lịch sử |
| `android_phone_farm/HUONG_DAN_CHAY_LOCAL.md` | Team/AI | raw ops note | Trung bình | Medium | `docs/project/source/raw-notes/HUONG_DAN_CHAY_LOCAL.legacy.md` | Đã archive | Chứa setup và thông tin nhạy cảm kiểu cũ |
| `RegisterBot_Package/README-boxphone.md` | AI/team | API docs trùng | Trung bình | Medium | `docs/project/source/legacy-docs/README-boxphone.legacy.md` | Đã archive khỏi component root | Gần duplicate `android_phone_farm/README.md` |
| `COPY_TO_PROJECT/` | ASEF bootstrap pack | template/standard | Cao | High | Không còn cần trong repo đang vận hành | Đã xóa sau khi migrate xong | Không còn template cũ để tham khảo tại chỗ |

## Conflict notes

- `docs/project/source/legacy-docs/04-registration-flow.legacy.md` vẫn mô tả hardcoded tap như hạn chế chính, nhưng source hiện đã có `screen_reader.py`, `_tap_element()` và `_type_and_verify()`.
- `docs/project/source/raw-notes/07-current-status.legacy.md` chưa phản ánh đầy đủ các improvement đã được ghi completed trong `docs/ai/source/legacy-agent-context/08-session-history.legacy.md`.
- Một số tài liệu legacy chứa credential và đường dẫn tuyệt đối máy cũ, không nên dùng nguyên văn làm source of truth.
