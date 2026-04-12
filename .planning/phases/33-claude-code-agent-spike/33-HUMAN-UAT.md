---
status: partial
phase: 33-claude-code-agent-spike
source: [33-VERIFICATION.md]
started: 2026-04-12T16:35:00Z
updated: 2026-04-12T16:35:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Full /task lifecycle
expected: Bot responds with 'Принято, создаю ветку...', then 'Claude работает...', then a message with diff stats and three inline buttons (Применить, Отклонить, Полный diff)
result: [pending]

### 2. WebApp diff viewer
expected: /m/agent/diff/{task_id} page loads with colored diff (green additions, red deletions, cyan hunks) inside mobile base template
result: [pending]

### 3. Approve flow
expected: Bot edits message to 'Изменения применены и смёрджены в master.'; git log shows merge commit
result: [pending]

### 4. Reject flow
expected: Bot edits message to 'Задача отклонена. Ветка удалена.'; no agent/task-* branches remain
result: [pending]

### 5. Mutex enforcement
expected: Second /task while first is running gets 'Задача уже выполняется, подождите.'
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
