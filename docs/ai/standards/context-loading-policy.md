# Context Loading Policy

## Mục tiêu

Không để AI Agent đọc toàn bộ tài liệu mỗi session.

## Thứ tự đọc chuẩn mỗi session

```txt
1. Adapter đang dùng
2. docs/ai/standards/context-loading-policy.md
3. docs/ai/memory/current-task.md
4. docs/ai/memory/known-issues.md
5. docs/ai/memory/risk-register.md
6. docs/ai/knowledge/security-boundary.md
7. Phân loại task
8. Đọc docs/project liên quan
9. Đọc docs/ai workflow/checklist liên quan
10. Đọc source code liên quan
11. Làm task
12. Test/review
13. Update memory
```

## Không đọc toàn bộ khi không cần

Chỉ đọc full `docs/project` và `docs/ai` khi task là bootstrap, full audit, business reconstruction, documentation consolidation hoặc architecture review toàn dự án.

## Routing theo task

### Hiểu nghiệp vụ

- `docs/project/00_project-overview.md`
- `docs/project/01_business-domain.md`
- `docs/project/02_feature-catalog.md`
- `docs/project/03_user-flows.md`
- `docs/project/04_business-rules.md`
- `docs/project/07_open-questions.md`

### Bugfix

- `docs/ai/workflows/bugfix-workflow.md`
- `docs/ai/memory/known-issues.md`
- `docs/project/02_feature-catalog.md`
- `docs/project/03_user-flows.md`
- `docs/project/04_business-rules.md`
- `docs/project/05_screen-api-data-map.md`

### Feature work

- `docs/project/02_feature-catalog.md`
- `docs/project/03_user-flows.md`
- `docs/project/04_business-rules.md`
- `docs/project/05_screen-api-data-map.md`
- `docs/ai/workflows/feature-workflow.md`
- `docs/ai/standards/definition-of-done.md`

### Backend/API

- `docs/project/04_business-rules.md`
- `docs/project/05_screen-api-data-map.md`
- `docs/ai/knowledge/api-map.md`
- `docs/ai/knowledge/data-model.md`

### Security-sensitive work

- `docs/ai/knowledge/security-boundary.md`
- `docs/project/04_business-rules.md`
- `docs/project/05_screen-api-data-map.md`

### Review code

- diff/source liên quan
- `docs/ai/standards/review-checklist.md`
- `docs/ai/standards/testing-checklist.md`
- `docs/ai/knowledge/security-boundary.md`
- `docs/ai/memory/current-task.md`
