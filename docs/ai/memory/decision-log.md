# Decision Log

| Date | Decision | Reason | Impact | Reversible |
|---|---|---|---|---|
| 2026-06-30 | Tạo kiến trúc `docs/project` + `docs/ai` làm source of truth mới | Tuân thủ chuẩn ASEF Pro | Repo có context architecture chuẩn hóa | Yes |
| 2026-06-30 | Chuyển adapter mỏng ra root `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` | Đưa entry files về đúng vai trò adapter chính thức | Tool mới sẽ đọc context từ cấu trúc ASEF thay vì folder staging | Yes |
| 2026-06-30 | Archive legacy context vào `docs/project/source/` và `docs/ai/source/legacy-agent-context/`, sau đó xóa `document-agent-root/`, `adapter/`, `COPY_TO_PROJECT/` | User chọn phương án dọn triệt để | Repo gọn hơn, không còn cụm context dư theo kiến trúc cũ | Partly |
