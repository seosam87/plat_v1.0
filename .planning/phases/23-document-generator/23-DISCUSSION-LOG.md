# Phase 23: Document Generator - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 23-document-generator
**Areas discussed:** Генерация и хранение PDF, UI документов, Отправка (Telegram/SMTP), Рабочий процесс

---

## PDF Storage Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| DB bytes + 3 версии | PDF в PostgreSQL (bytea), макс 3 версии на документ | ✓ |
| Файловая система + путь в БД | PDF в uploads/documents/, в БД только путь | |
| На усмотрение Claude | Выбрать оптимальный вариант на этапе планирования | |

**User's choice:** DB bytes + 3 версии
**Notes:** Вопрос был заранее зафиксирован в STATE.md pending todos

## Статус генерации PDF

| Option | Description | Selected |
|--------|-------------|----------|
| HTMX polling | Статус обновляется раз в 2-3с через HTMX poll | ✓ |
| Redirect на страницу документа | Редирект на /ui/documents/{id} с автообновлением | |
| Toast-уведомление | Фоновая генерация, уведомление через колокольчик | |

**User's choice:** HTMX polling
**Notes:** Устоявшийся паттерн из позиций и краулера

## Перегенерация документа

| Option | Description | Selected |
|--------|-------------|----------|
| Да, перегенерация | Кнопка "Перегенерировать", новая версия заменяет старую (до 3 в стеке) | ✓ |
| Нет, только новый документ | Каждая генерация — отдельный документ | |

**User's choice:** Да, перегенерация

## Точка входа генерации

| Option | Description | Selected |
|--------|-------------|----------|
| Страница документов клиента | /ui/crm/clients/{id}/documents — кнопка "Создать документ" | ✓ |
| Со страницы шаблона | Кнопка на карточке шаблона в /ui/templates | |
| Оба варианта | И со страницы клиента, и со страницы шаблона | |

**User's choice:** Страница документов клиента

## UI список документов

| Option | Description | Selected |
|--------|-------------|----------|
| Таблица | Колонки: название, тип, сайт, дата, статус, действия. Фильтры: тип + дата | ✓ |
| Карточки | Сетка карточек как в шаблонах | |

**User's choice:** Таблица

## Отправка документа

| Option | Description | Selected |
|--------|-------------|----------|
| Кнопка с выбором канала | "Отправить" → дропдаун: Telegram / Email | ✓ |
| Две отдельные кнопки | Иконка Telegram + иконка Email на строке | |
| Модалка отправки | Модальное окно с выбором канала, адреса, предпросмотром | |

**User's choice:** Кнопка с выбором канала

## Подтверждение отправки

| Option | Description | Selected |
|--------|-------------|----------|
| Да, confirm-диалог | "Отправить КП на info@client.com через Email?" — OK/Отмена | ✓ |
| Нет, отправлять сразу | Один клик — сразу отправка | |

**User's choice:** Да, confirm-диалог

## Связь документов с клиентом

| Option | Description | Selected |
|--------|-------------|----------|
| Таб "Документы" в карточке клиента | Новая вкладка рядом с Сайты, Контакты, История | ✓ |
| Отдельная страница /ui/documents | Общий список всех документов с фильтром по клиенту | |
| Оба варианта | Таб + общий список | |

**User's choice:** Таб "Документы" в карточке клиента

## Доступ

| Option | Description | Selected |
|--------|-------------|----------|
| Admin + Manager | require_manager_or_above — как в CRM | ✓ |
| Только Admin | require_admin | |
| Все аутентифицированные | Любой пользователь | |

**User's choice:** Admin + Manager

---

## Claude's Discretion

- Модель GeneratedDocument: поля, индексы, FK
- Именование PDF файла при скачивании
- Формат статусов Celery task
- Пагинация списка документов
- Порядок отображения документов

## Deferred Ideas

- DOC-06: Variable overrides at generation time
- DOC-07: Auto-generate proposal after intake completion
- DOC-08: Document audit trail via audit_log
- Общий список /ui/documents как отдельная страница
