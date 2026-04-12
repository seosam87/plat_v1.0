# Phase 33: Claude Code Agent (Spike) - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Spike-эксперимент: пользователь отправляет текстовую задачу Telegram-боту → бот запускает Claude Code CLI → получает diff → показывает пользователю → пользователь одобряет (merge) или отклоняет (удалить ветку). Это НЕ production feature, а эксперимент для оценки жизнеспособности подхода.

**In scope:**
- Новый handler `/task` в Telegram боте (bot/handlers/agent.py)
- Запуск Claude Code CLI через subprocess в bot контейнере
- Жизненный цикл: приём → ветка → выполнение → diff → approve/reject
- Очередь из одной задачи (если Claude занят — ждать)
- Показ краткого summary в чате + полный diff в WebApp
- Approve → merge ветки, Reject → удалить ветку
- SPIKE-REPORT.md по итогам эксперимента (go/no-go для production)

**Out of scope:**
- Параллельные задачи
- Conversational mode (уточнения внутри задачи)
- Production-grade очередь задач
- UI для истории задач
- Интеграция с GSD workflow

</domain>

<decisions>
## Implementation Decisions

### Способ запуска Claude
- **D-01:** Claude Code CLI через subprocess — `claude --print -p '{task}' --allowedTools Edit,Write,Bash,Read`. Запускается внутри bot контейнера.
- **D-02:** Claude CLI устанавливается в Dockerfile.bot (npm install -g @anthropic-ai/claude-code). Рабочая директория — монтированный репозиторий проекта.
- **D-03:** ANTHROPIC_API_KEY передаётся как env variable в docker-compose.yml для bot сервиса.

### Жизненный цикл задачи
- **D-04:** Git branch flow: создать `agent/task-{uuid}` → Claude работает в ней → `git diff master` → показать пользователю → approve=merge+delete branch, reject=delete branch.
- **D-05:** Одна задача одновременно. Если Claude занят — ответить «Задача выполняется, подождите».
- **D-06:** Статус-сообщения в чат: «⏳ Принято, создаю ветку...» → «🔄 Claude работает...» → «✅ Готово, вот diff:» или «❌ Ошибка: {message}».

### Безопасность и границы
- **D-07:** Минимальные ограничения для spike: `--allowedTools Edit,Write,Bash,Read` — полный набор инструментов Claude Code.
- **D-08:** Timeout — Claude's discretion (рекомендуется 5-10 минут в зависимости от сложности).
- **D-09:** Claude работает в репозитории проекта (volume mount). Изменения изолированы в отдельной git ветке.

### Формат результата
- **D-10:** Краткий summary в чате: список изменённых файлов + stat (lines added/removed) + inline-кнопки «✅ Применить» / «❌ Отклонить» + WebApp-кнопка «Полный diff».
- **D-11:** Полный diff на WebApp-странице `/m/agent/diff/{task_id}` — отдельный мобильный endpoint с подсветкой синтаксиса.
- **D-12:** При ошибке Claude (timeout, crash) — сообщение с ошибкой + авто-удаление ветки.

### Документация spike
- **D-13:** SPIKE-REPORT.md в .planning/phases/33-claude-code-agent-spike/ — что попробовали, что работает, что нет, go/no-go рекомендация для production.

### Claude's Discretion
- Конкретный timeout значение (5-10 мин)
- Формат system prompt для Claude Code (контекст проекта, ограничения)
- Структура модели AgentTask для хранения состояния задачи
- Реализация diff-viewer WebApp страницы (простой pre-formatted text vs syntax highlighting)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bot Infrastructure (Phase 32)
- `bot/main.py` — entry point, handler registration pattern
- `bot/handlers/devops.py` — паттерн confirmation flow с inline-кнопками (переиспользовать для approve/reject)
- `bot/auth.py` — @require_auth decorator
- `bot/config.py` — BotSettings, APP_BASE_URL
- `bot/utils/shell.py` — run_command() — паттерн subprocess execution
- `bot/utils/formatters.py` — code_block, bold для форматирования diff summary

### Docker
- `Dockerfile.bot` — добавить установку Claude CLI (npm)
- `docker-compose.yml` — добавить ANTHROPIC_API_KEY, volume mount репозитория

### Mobile WebApp
- `app/routers/mobile.py` — /m/ роутер для diff-viewer страницы
- `app/templates/mobile/base_mobile.html` — базовый шаблон

### Project Config
- `app/config.py` — ANTHROPIC_API_KEY (уже есть для Phase 16 LLM Briefs)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `bot/handlers/devops.py`: Confirmation flow с inline-кнопками и 60s timeout — переиспользовать для approve/reject diff
- `bot/utils/shell.py`: `run_command()` — базис для запуска Claude CLI subprocess
- `bot/utils/formatters.py`: code_block, bold, status_line — для форматирования diff summary
- `bot/handlers/miniapp.py`: `make_webapp_button()` — для кнопки «Полный diff» → WebApp

### Established Patterns
- Handler + @require_auth decorator для всех команд
- Inline-кнопки для подтверждения опасных операций
- Celery dispatch для длительных операций (но здесь subprocess в bot контейнере, не Celery)
- WebApp кнопки для перехода на /m/ страницы

### Integration Points
- bot/main.py: регистрация нового CommandHandler("task", ...)
- Dockerfile.bot: Node.js + Claude CLI installation
- docker-compose.yml: ANTHROPIC_API_KEY env, volume mount
- app/routers/mobile.py: новый endpoint /m/agent/diff/{task_id}

</code_context>

<specifics>
## Specific Ideas

- Это spike — код может быть менее полированным, главное работоспособность
- SPIKE-REPORT.md должен содержать чёткую рекомендацию go/no-go
- Claude Code CLI `--print` mode возвращает результат в stdout, не интерактивный
- Git ветка `agent/task-{uuid}` изолирует изменения от master

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 33-claude-code-agent-spike*
*Context gathered: 2026-04-12*
