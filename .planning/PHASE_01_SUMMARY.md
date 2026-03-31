# Phase 01 — Auth System Summary

## 1. Архитектура auth системы

```
app/
├── models/user.py              # ORM-модель + UserRole enum
├── auth/
│   ├── password.py             # bcrypt хэширование / верификация
│   ├── jwt.py                  # создание и декодирование токенов
│   └── dependencies.py         # FastAPI Depends: get_current_user, require_role
├── routers/
│   ├── auth.py                 # POST /auth/token, GET /auth/me
│   └── admin.py                # CRUD /admin/users (только для admin)
└── services/
    └── user_service.py         # бизнес-логика: create/get/list/update/deactivate
```

Слои чётко разделены: модель → сервис → роутер. Зависимости для авторизации инжектятся через FastAPI `Depends`, а не пробрасываются вручную.

---

## 2. Компоненты

### 2.1 User model (`app/models/user.py`)

| Поле | Тип | Особенности |
|---|---|---|
| `id` | `UUID` (PostgreSQL native) | PK, `default=uuid.uuid4` |
| `username` | `String(100)` | unique |
| `email` | `String(255)` | unique, indexed |
| `password_hash` | `String(255)` | bcrypt hash |
| `role` | `SAEnum(UserRole)` | default = `client` |
| `is_active` | `Boolean` | soft-delete флаг |
| `created_at` / `updated_at` | `DateTime(timezone=True)` | auto-managed |

**Роли** — три уровня иерархии:
```
admin > manager > client
```

Мягкое удаление: пользователь не удаляется из БД, а деактивируется (`is_active = False`). При логине и при каждом запросе активность проверяется.

---

### 2.2 Auth flow

```
POST /auth/token
  │
  ├─ get_user_by_email()        # ищем по email (lower+strip)
  ├─ verify_password()          # bcrypt.verify
  ├─ log_action("user.login")   # audit trail
  └─ create_access_token()      # возвращаем JWT
         │
         └─ { sub: user_id, role: role, exp, iat }

GET /auth/me  (и любой защищённый эндпоинт)
  │
  ├─ oauth2_scheme              # извлекаем Bearer токен из заголовка
  ├─ decode_access_token()      # jose.jwt.decode → payload
  ├─ get_user_by_id()           # проверяем существование
  └─ user.is_active check       # проверяем что не деактивирован
```

**RBAC** через dependency factory `require_role(*roles)`:
```python
require_admin              = require_role(UserRole.admin)
require_manager_or_above   = require_role(UserRole.admin, UserRole.manager)
require_any_authenticated  = require_role(admin, manager, client)
```
Декоратор не нужен — ролевая проверка вешается как `Depends(require_admin)` прямо в сигнатуре роутера.

---

### 2.3 JWT (`app/auth/jwt.py`)

- **Алгоритм**: HS256 (симметричный, ключ из `settings.SECRET_KEY`)
- **Payload**: `sub` (user UUID), `role`, `exp`, `iat`
- **TTL**: `settings.ACCESS_TOKEN_EXPIRE_MINUTES` (по умолчанию 24ч)
- **Библиотека**: `python-jose[cryptography]`
- **Нет refresh token** на этом этапе — только access token

Декодирование кидает `JWTError` при невалидном или истёкшем токене; зависимость `get_current_user` перехватывает это и возвращает `401`.

---

## 3. Зависимости и обоснование

| Пакет | Версия | Зачем |
|---|---|---|
| `python-jose[cryptography]` | 3.3.x | JWT encode/decode. `[cryptography]` backend нужен для HS256; PyJWT в стеке не используется, чтобы не было двух JWT-библиотек |
| `passlib[bcrypt]` | 1.7.x | Абстракция над bcrypt через `CryptContext`; умеет автоматически рехэшировать при смене cost factor (`deprecated="auto"`) |
| `bcrypt` | 3.2.x | Нижний слой для passlib; явно пинится на `<4.0` — bcrypt 4.x меняет поведение хэширования |
| `cryptography` | 42.x | Нужен `python-jose` для криптографических примитивов; также используется для Fernet (WP credentials) в будущих фазах |
| `pydantic[email]` | 2.7+ | `EmailStr` в `CreateUserRequest` и `UpdateUserRequest` — валидация email на уровне схемы |
| `sqlalchemy` | 2.0.30+ | Async ORM (`AsyncSession`); UUID native type через `postgresql.UUID(as_uuid=True)` |
| `asyncpg` | 0.29.x | Единственный production async драйвер для PostgreSQL; psycopg2 синхронный и блокирует event loop |
| `psycopg2-binary` | 2.9.x | **Только для Alembic** `env.py` — синхронный контекст миграций; в рантайме приложения не используется |

### Почему не PyJWT?

В стеке уже есть `python-jose` — он покрывает тот же функционал и поддерживает несколько алгоритмов (HS256, RS256). Держать две JWT-библиотеки создаёт риск подписывать/верифицировать разными инструментами.

### Почему bcrypt cost=12?

На современном железе 2025 года cost 12 даёт ~300ms на хэш — достаточно медленно для защиты от brute-force, но не заметно при интерактивном логине. Cost 10 (default) уже слабоват.

---

## Что реализовано в Phase 01 (auth-слой)

- [x] User model + Alembic migration
- [x] `POST /auth/token` — логин, выдача JWT
- [x] `GET /auth/me` — текущий пользователь
- [x] `get_current_user` dependency + `require_role` factory
- [x] Admin CRUD: `GET/POST /admin/users`, `PUT/DELETE /admin/users/{id}`
- [x] Audit log при логине, создании, обновлении, деактивации
- [x] Soft-delete (`is_active = False`)
