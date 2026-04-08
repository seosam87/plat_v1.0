# UI Scenario Runner

Единый YAML-формат UI-сценариев, который одновременно:

1. **Phase 19.1** — исполняется Playwright-раннером в CI как e2e smoke-тесты.
2. **Phase 19.2 (future)** — проигрывается frontend tour player'ом как интерактивный продуктовый тур поверх реального приложения.

Один и тот же файл — два раннера. README'шка документирует публичный контракт, чтобы 19.2 мог полагаться на неизменную схему.

---

## Назначение

Сценарии хранятся как plain YAML — без DSL, без кода, без регистрации в pytest. Любой `scenarios/NN-name.yaml` автоматически превращается в pytest item кастомным коллектором (`tests/fixtures/scenario_runner/collector.py`).

Почему YAML, а не Python-тесты:
- Один источник истины для тестов и туров (19.2 ничего не придётся переписывать).
- Сценарии могут редактировать не-Python пользователи (продакт, QA).
- Диффы в ревью читаются тривиально.

---

## Схема YAML

Минимальный сценарий:

```yaml
name: my-scenario
description: one-liner explaining the goal
steps:
  - op: open
    url: "/ui/dashboard"
```

**Обязательные поля:**
- `name` (str) — уникальное имя сценария, отображается в pytest-выводе.
- `steps` (list[Step], min 1) — последовательность шагов. Пустой список запрещён.

**Опциональные:**
- `description` (str) — человекочитаемое описание цели сценария.

Авторитетное определение: `tests/fixtures/scenario_runner/schema.py` (Pydantic v2 discriminated union по полю `op`). Любые extra-поля запрещены (`extra="forbid"`).

---

## Step типы (P0, исполняются runner'ом 19.1)

| `op`            | Поля                                         | Что делает |
| --------------- | -------------------------------------------- | ---------- |
| `open`          | `url: str`                                   | `page.goto(url)`. Относительные URL (`/ui/...`) автоматически дополняются `BASE_URL`. |
| `click`         | `target: str`                                | Клик по локатору. |
| `fill`          | `target: str`, `value: str`                  | Заполняет input/textarea. |
| `wait_for`      | `target: str`, `state: visible\|hidden\|attached = visible`, `timeout: int = 30000` | Ждёт пока локатор достигнет состояния. |
| `expect_text`   | `target: str`, `contains: str`               | Ассерт: локатор содержит подстроку (`to_contain_text`). |
| `expect_status` | `code: int`                                  | Ассерт: последний main-frame response имеет указанный HTTP-код. |

Минимальные примеры:

```yaml
- op: open
  url: "/ui/keyword-suggest/"
- op: fill
  target: "#seed-input"
  value: "smoke seed"
- op: click
  target: 'role=button[name="Найти подсказки"]'
- op: wait_for
  target: "#suggest-table tbody tr.suggest-row >> nth=0"
  state: visible
  timeout: 30000
- op: expect_text
  target: "#suggest-results-card"
  contains: "smoke seed alpha"
- op: expect_status
  code: 200
```

---

## Зарезервированные step типы (для 19.2 tour player)

Схема валидирует эти типы, но **runner 19.1 их пропускает с WARNING** в лог. Они существуют, чтобы один и тот же YAML-файл валидно парсился и тестовым раннером, и будущим tour player'ом.

| `op`             | Поля              | Назначение в 19.2 |
| ---------------- | ----------------- | ----------------- |
| `say`            | `text: str`       | Показать tooltip/speech-bubble с текстом шага тура. |
| `highlight`      | `target: str`     | Подсветить элемент рамкой/halo. |
| `wait_for_click` | `target: str`     | Дождаться клика пользователя по элементу прежде чем двигаться дальше. |

**Важно:** НЕ меняйте синтаксис этих типов без одновременного обновления обоих раннеров. Контракт фиксирован на уровне Pydantic-схемы (`schema.py`) — изменение поля сломает и тесты, и туры.

---

## Локатор-синтаксис (`target`)

Резолвер в `locators.py` превращает строку `target` в `page.locator(...)` по префиксу:

| Префикс       | Пример                                    | Соответствует Playwright API |
| ------------- | ----------------------------------------- | ---------------------------- |
| `role=`       | `role=button[name="Save"]`                | `page.get_by_role("button", name="Save")` |
| `text=`       | `text=Dashboard`                          | `page.get_by_text("Dashboard")` |
| `label=`      | `label=Email`                             | `page.get_by_label("Email")` |
| `testid=`     | `testid=submit-btn`                       | `page.get_by_test_id("submit-btn")` |
| `#id` / `.cls`| `#seed-input`, `.card`, `tr.suggest-row`  | `page.locator(selector)` (raw CSS fallback) |

Для уточнения используйте Playwright'овский `>>` chaining:

```yaml
target: "#suggest-table tbody tr.suggest-row >> nth=0"   # первая строка
target: "table >> text=Scenario Smoke Site >> nth=0"      # строка внутри таблицы
```

---

## Локальный запуск

**Против уже запущенного dev-стека** (api на `http://localhost:8000`):

```bash
BASE_URL=http://localhost:8000 pytest scenarios/ -v
```

Требуется: Playwright 1.47 + chromium, seeded `smoke_admin` / `smoke@example.com` в dev-БД.

**Полный CI pipeline** (поднимает стек, сидит БД и Redis, прогоняет сценарии в Playwright-контейнере):

```bash
bash scripts/run-scenarios-ci.sh
```

Exit code скрипта == exit code pytest.

---

## Артефакты при падении

На первом упавшем шаге runner пишет:

```
artifacts/scenarios/{scenario_name}/
├── failure.png     # full-page screenshot в момент падения
└── trace.zip       # Playwright trace (snapshots + screenshots + sources)
```

Открыть trace локально:

```bash
playwright show-trace artifacts/scenarios/suggest-to-results/trace.zip
```

Директория `artifacts/` в `.gitignore`. CI wipeает её между прогонами.

---

## Как добавить сценарий

1. Создать `scenarios/NN-name.yaml` (нумерация — для порядка в pytest-выводе).
2. Прописать `name`, `description`, `steps`.
3. Локально проверить: `BASE_URL=http://localhost:8000 pytest scenarios/NN-name.yaml -v`.
4. Commit.

Никакой регистрации в conftest / pytest.ini не требуется — коллектор автоматически подхватывает любой `*.yaml` внутри `scenarios/`.

**Авто-открытие:** `BASE_URL` задаётся переменной окружения (дефолт `http://localhost:8000`). Логин выполняется программно через фикстуру `scenario_page` — seeded `smoke@example.com` / `smoke-password`.

---

## Связь с Phase 19.2 (tour player)

Когда появится 19.2 frontend tour player, он будет загружать **те же самые `scenarios/*.yaml` файлы** и проигрывать их пользователю:

- `open` / `click` / `fill` — автоматические шаги тура (опционально, tour player может эмулировать пользователя или ждать реального клика).
- `say` — speech-bubble с объяснением текущего шага.
- `highlight` — подсветить целевой элемент.
- `wait_for_click` — пауза до реального клика пользователя.

**Правило:** если добавляете сценарий, который нужен И как тест И как тур, просто смешивайте P0 и reserved шаги в одном файле — runner 19.1 пропустит reserved с WARNING, tour player 19.2 отыграет их полноценно.

Пример гибридного сценария (будущее использование):

```yaml
name: new-user-onboarding-tour
description: First-login tour demonstrating suggest + site creation
steps:
  - op: say
    text: "Давайте найдём первые ключевые фразы."
  - op: highlight
    target: "#seed-input"
  - op: wait_for_click
    target: 'role=button[name="Найти подсказки"]'
  - op: wait_for
    target: "#suggest-table tbody tr.suggest-row >> nth=0"
    state: visible
    timeout: 30000
```

Runner 19.1 сегодня запустит этот сценарий и пропустит первые три шага с WARNING'ами — остальные два отработают как полноценный assertion. Tour player 19.2 отыграет всё пятью шагами.
