# Phase 33: Claude Code Agent (Spike) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 33-claude-code-agent-spike
**Areas discussed:** Способ запуска Claude, Жизненный цикл задачи, Безопасность и границы, Формат результата

---

## Способ запуска Claude

### Фреймворк

| Option | Description | Selected |
|--------|-------------|----------|
| Claude Code CLI | subprocess `claude --print`, уже установлен на VPS | ✓ |
| Claude SDK (Python) | anthropic.Client().messages.create(), нет tool use без реализации | |
| Claude Agent SDK | claude_code_sdk.query(), новый, может быть нестабилен | |

**User's choice:** Claude Code CLI
**Notes:** —

### Среда выполнения

| Option | Description | Selected |
|--------|-------------|----------|
| Bot контейнер | Claude CLI в Dockerfile.bot, монтированный репозиторий | ✓ |
| Отдельный контейнер | Выделенный agent контейнер, коммуникация через Redis | |

**User's choice:** Bot контейнер
**Notes:** —

---

## Жизненный цикл задачи

### Процесс

| Option | Description | Selected |
|--------|-------------|----------|
| Git branch + diff | Ветка agent/task-{id}, работа, diff, approve/reject | ✓ |
| Stash-основанный | Работа в master, stash apply/drop | |

**User's choice:** Git branch + diff
**Notes:** —

### Параллельность

| Option | Description | Selected |
|--------|-------------|----------|
| Одна задача | Очередь из одного, если занят — ждать | ✓ |
| Параллельные ветки | Несколько задач одновременно | |

**User's choice:** Одна задача
**Notes:** —

---

## Безопасность и границы

### Ограничения

| Option | Description | Selected |
|--------|-------------|----------|
| Минимальные | --allowedTools Edit,Write,Bash,Read, timeout 5 мин | ✓ |
| Строгие | Белый список файлов, запрет Bash, только Read+Edit | |

**User's choice:** Минимальные
**Notes:** Для spike достаточно

### Timeout

| Option | Description | Selected |
|--------|-------------|----------|
| 5 минут | Для небольших задач | |
| 15 минут | Для сложных задач | |
| Claude решает | Claude определит оптимальный | ✓ |

**User's choice:** Claude's discretion
**Notes:** —

---

## Формат результата

### Diff

| Option | Description | Selected |
|--------|-------------|----------|
| Summary + WebApp | Краткий stat в чате + полный diff по кнопке WebApp | ✓ |
| Только в чате | Текстовый diff в code block, обрезается | |
| Файлом | .diff файл как документ в Telegram | |

**User's choice:** Summary + WebApp
**Notes:** —

### Документация spike

| Option | Description | Selected |
|--------|-------------|----------|
| SPIKE-REPORT.md | Отчёт с go/no-go рекомендацией | ✓ |
| Claude решает | Формат на усмотрение Claude | |

**User's choice:** SPIKE-REPORT.md
**Notes:** —

---

## Claude's Discretion

- Конкретное значение timeout
- System prompt для Claude Code
- Структура AgentTask модели
- Реализация diff-viewer страницы

## Deferred Ideas

None — discussion stayed within phase scope
