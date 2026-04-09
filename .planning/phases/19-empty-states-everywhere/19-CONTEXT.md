# Phase 19: Empty States Everywhere - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Создать reusable Jinja2-макрос для empty state и применить его на всех основных страницах платформы. Каждый empty state объясняет пользователю почему нет данных, как начать работу (collapsible "Как использовать") и даёт прямую кнопку-действие. Существующие ad-hoc empty states мигрируются на новый макрос.

</domain>

<decisions>
## Implementation Decisions

### Визуальный дизайн
- **D-01:** Карточка с рамкой — белый фон, border, rounded corners (Tailwind: bg-white rounded-lg shadow-sm border border-gray-200)
- **D-02:** Без иконок — только текстовый контент (заголовок, описание, how-to, кнопки)
- **D-03:** Стилизация через Tailwind-классы (не inline styles)

### How-to контент
- **D-04:** Глубина "Как использовать" — на усмотрение Claude. Для сложных фич (краул, позиции) детальнее: предусловия + шаги + ожидаемый результат. Для простых (keywords, competitors) — краткий hint.

### CTA-стратегия
- **D-05:** Основной CTA (кнопка bg-blue-600 text-white) + опциональный второстепенный CTA (текстовая ссылка)
- **D-06:** Макрос принимает: `reason` (str), `cta_label` (str), `cta_url` (str), опционально `secondary_label` (str), `secondary_url` (str), `docs_url` (str, зарезервирован)
- **D-07:** How-to контент передаётся через Jinja2 `{% call %}` блок

### Объём страниц
- **D-08:** Включить ВСЕ страницы из инвентаря, включая Tools (Phase 24–25), даже если сами инструменты ещё не реализованы
- **D-09:** Мигрировать существующие ad-hoc empty states (Metrika, Traffic Analysis, Positions, Gap Analysis и др.) на новый макрос
- **D-10:** Smoke-тесты Phase 15.1 не должны ломаться — все страницы с empty state корректно рендерятся

### Claude's Discretion
- Конкретный текст "Как использовать" для каждой страницы
- Выбор предусловий для каждой фичи
- Порядок и группировка страниц по планам

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Макросы и шаблоны
- `app/templates/macros/health.html` — Существующий Jinja2-макрос (health widget), пример структуры макроса в проекте
- `app/templates/metrika/index.html` — Лучший существующий пример empty state с двумя вариантами (no counter / no data)

### Требования
- `.planning/REQUIREMENTS.md` §EMP-01..EMP-07 — Требования к empty states

### Smoke-тесты
- `tests/fixtures/scenario_runner/` — Каталог сценариев Phase 15.1; новые empty state роуты нужно зарегистрировать

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/templates/macros/health.html` — единственный существующий Jinja2-макрос; можно использовать как пример структуры
- Tailwind CSS — уже подключён, используется в большинстве шаблонов

### Established Patterns
- Empty states сейчас — ad-hoc `<p class="text-gray-500">Нет данных...</p>` без CTA и how-to
- Metrika имеет лучший паттерн: два разных empty state в зависимости от причины (no counter vs no data)
- `<details>/<summary>` — нативный HTML, работает без JS, совместим с HTMX

### Integration Points
- Каждый шаблон страницы — точка интеграции через `{% from "macros/empty_state.html" import empty_state %}`
- Phase 15.1 smoke crawler — новые роуты нужно добавить в параметризацию тестов

</code_context>

<specifics>
## Specific Ideas

Нет специальных требований — стандартные подходы.

</specifics>

<deferred>
## Deferred Ideas

None — обсуждение осталось в рамках фазы.

</deferred>

---

*Phase: 19-empty-states-everywhere*
*Context gathered: 2026-04-09*
