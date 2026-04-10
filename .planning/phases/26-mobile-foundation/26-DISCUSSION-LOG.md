# Phase 26: Mobile Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 26-mobile-foundation
**Areas discussed:** Mobile Layout, Telegram WebApp Auth, PWA Configuration, /m/ Routing

---

## Mobile Layout

### Template approach

| Option | Description | Selected |
|--------|-------------|----------|
| Отдельный `base_mobile.html` | Свой шаблон с bottom nav, без sidebar. Чистое разделение | ✓ |
| Расширение `base.html` | Добавить bottom nav через media query, один шаблон на всё | |
| На усмотрение Claude | | |

**User's choice:** Отдельный `base_mobile.html`
**Notes:** —

### Bottom navigation tabs

| Option | Description | Selected |
|--------|-------------|----------|
| Минимум (4 таба) | Дайджест, Сайты, Позиции, Ещё (меню) | ✓ |
| Расширенный (5 табов) | Дайджест, Сайты, Позиции, Задачи, Ещё | |
| Свой набор | Пользовательский набор вкладок | |

**User's choice:** Минимум (4 таба)
**Notes:** —

### Version switching

| Option | Description | Selected |
|--------|-------------|----------|
| Явная ссылка | На desktop — "Мобильная версия", на mobile — "Полная версия" | ✓ |
| Авторедирект по User-Agent | Телефон → /m/, desktop → обычный, с ручным переключением | |
| Без редиректа | /m/ доступен всем как отдельная точка входа | |
| На усмотрение Claude | | |

**User's choice:** Явная ссылка
**Notes:** —

---

## Telegram WebApp Auth

### Привязка Telegram ID

| Option | Description | Selected |
|--------|-------------|----------|
| Привязка через профиль | Desktop → профиль → "Привязать Telegram" (Login Widget) | ✓ |
| Invite-ссылка | Админ генерирует ссылку, пользователь открывает в Telegram | |
| На усмотрение Claude | | |

**User's choice:** Привязка через профиль (Telegram Login Widget)
**Notes:** —

### Непривязанный telegram_id

| Option | Description | Selected |
|--------|-------------|----------|
| Экран "Привяжите аккаунт" | Инструкция + ссылка на desktop профиль | ✓ |
| Форма логина | Email + пароль внутри WebApp | |
| На усмотрение Claude | | |

**User's choice:** Экран "Привяжите аккаунт"
**Notes:** —

---

## PWA Configuration

### Service Worker кэш

| Option | Description | Selected |
|--------|-------------|----------|
| Только shell | HTML-каркас, CSS, JS, иконки. Оффлайн — заглушка | |
| Shell + последние данные | Кэш последних API-ответов, оффлайн — устаревшие данные | |
| На усмотрение Claude | | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** —

### PWA брендинг

| Option | Description | Selected |
|--------|-------------|----------|
| Текущие цвета платформы | Indigo #1e1b4b + белый фон | ✓ (временно) |
| Свои цвета | | |
| На усмотрение Claude | | |

**User's choice:** Текущие цвета, но пользователь недоволен ими. Добавить в бэклог задачу по редизайну.
**Notes:** Пользователь явно сказал "мне не нравятся текущие цвета". Редизайн отложен в бэклог.

---

## Маршрутизация /m/

### Организация роутов

| Option | Description | Selected |
|--------|-------------|----------|
| Отдельный роутер `mobile.py` | APIRouter(prefix="/m"), мобильные эндпоинты отдельно | |
| По фичам | В каждом существующем роутере добавляются /m/ роуты | |
| На усмотрение Claude | | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** Ключевое ограничение — мобильные эндпоинты вызывают те же сервисы.

### Auth на /m/ роутах

| Option | Description | Selected |
|--------|-------------|----------|
| Тот же JWT | Cookie или header, общий get_current_user | |
| Отдельный механизм | Session-based для WebApp | |
| На усмотрение Claude | | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** Ключевое ограничение — после Telegram WebApp auth пользователь неотличим от desktop-пользователя на уровне сервисов.

---

## Claude's Discretion

- Организация мобильных роутов (D-09)
- Auth механизм на mobile (D-10)
- Стратегия service worker кэша (D-07 — shell-only выбран пользователем для оффлайн, детали кэширования на Claude)

## Deferred Ideas

- UI/branding redesign — пользователь недоволен текущей цветовой схемой, нужно исследовать варианты
