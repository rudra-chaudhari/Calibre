# Calibre Backend Architecture

## Overview

Calibre is a productivity app ("Own your Time") built for IIT Bombay's Software Lab (CS699). It unifies tasks, events and routines, shows what matters now, finds free time, runs focus sessions, tracks progress, does spaced-repetition revision, journals, and imports deadlines from IITB Moodle. A Flutter app is the client. This repo is the Django + Django REST Framework backend.

### App List and Build Order

The backend is organized into multiple apps, each handling a specific domain. Apps are built in this order to respect dependencies:

| # | App | Purpose | Dependencies |
|---|-----|---------|--------------|
| 1 | `accounts` | User authentication and profile | None (must be first) |
| 2 | `common` | Shared base models, mixins, categories | accounts |
| 3 | `tasks` | Core task entity | accounts, common |
| 4 | `planner` | Events, routines, agenda, free slots | accounts, common, tasks |
| 5 | `integrations` | Moodle sync (writes tasks/events) | accounts, common, tasks, planner |
| 6 | `focus` | Focus sessions linked to tasks | accounts, tasks |
| 7 | `revision` | Spaced-repetition topics and queue | accounts (feeds planner later) |
| 8 | `journal` | Journal entries with context | accounts, tasks, events, focus |
| 9 | `analytics` | Read-only summary stats | accounts, tasks, events, focus |
| 10 | `activity` | Screen-time ingestion | accounts |

The `accounts` and `common` apps are implemented in this phase.

## Layering

The codebase follows a strict layered architecture to make data flow easy to explain and debug:

```
urls.py → views.py → serializers.py → services.py → models.py → DB
```

- **urls.py**: Route definitions only. Maps HTTP paths to views.
- **views.py**: Thin layer. Handles auth, parses request, calls serializer/service, returns response. No business logic beyond a few lines.
- **serializers.py**: Validation and data shaping. Converts between Django models and JSON. Should not touch more than one model.
- **services.py**: Business logic that spans models or has more than a few lines. This is where complex operations live.
- **models.py**: Data definitions and tiny methods. Should only know about its own table.
- **DB**: SQLite (dev) or Postgres (prod). Stores the actual data.

**Rule**: Never put business logic in views or serializers if it touches more than one model. Push it down to services.

## Request Flow

### (a) Register Flow (with Category Seeding)

1. Client sends `POST /api/v1/auth/register/` with `{"email": "...", "password": "...", "name": "..."}`
2. `urls.py` routes to `RegisterView`
3. `RegisterView.create()` calls `RegisterSerializer.validate()` to check email uniqueness and password strength
4. `RegisterSerializer.create()` calls `register_user()` from `accounts/services.py`
5. `register_user()` uses `UserManager.create_user()` to create the user (with password hashing)
6. User is saved to `accounts_user` table
7. `register_user()` calls `seed_default_categories(user)` from `common/services.py`
8. `seed_default_categories()` creates 8 default categories (Academics, Work, Personal, etc.) for the user
9. Categories are saved to `common_category` table
10. `RegisterView.create()` issues JWT tokens via `RefreshToken.for_user(user)`
11. Response: `{"user": {...}, "access": "...", "refresh": "..."}` with 201 status

**Files touched (in order)**:
- `apps/accounts/urls.py` (route)
- `apps/accounts/views.py` (RegisterView)
- `apps/accounts/serializers.py` (RegisterSerializer)
- `apps/accounts/services.py` (register_user)
- `apps/accounts/models.py` (User + UserManager)
- `apps/common/services.py` (seed_default_categories)
- `apps/common/models.py` (Category)
- DB (accounts_user and common_category tables)

### (b) Authenticated Request to `/users/me/`

1. Client sends `GET /api/v1/users/me/` with `Authorization: Bearer <access_token>` header
2. `urls.py` routes to `UserMeView`
3. DRF JWT authentication middleware validates the token and sets `request.user`
4. `UserMeView.get_object()` returns `request.user`
5. `UserMeView.get_serializer_class()` returns `UserSerializer`
6. `UserSerializer` serializes the user object (read-only fields only)
7. Response: `{"id": ..., "email": ..., "name": ..., ...}` with 200 status

**Files touched (in order)**:
- `apps/accounts/urls.py` (route)
- `apps/accounts/views.py` (UserMeView)
- `apps/accounts/serializers.py` (UserSerializer)
- `apps/accounts/models.py` (User - implicit via serializer)

### (c) Logout Flow

1. Client sends `POST /api/v1/auth/logout/` with `{"refresh": "<refresh_token>"}` and access token in header
2. `urls.py` routes to `logout_view`
3. DRF JWT authentication validates the access token and sets `request.user`
4. `LogoutSerializer` validates the refresh token exists
5. `logout_view()` parses the refresh token with `RefreshToken(token)`
6. Calls `.blacklist()` to add it to the blacklist table
7. Response: 204 No Content

**Files touched (in order)**:
- `apps/accounts/urls.py` (route)
- `apps/accounts/views.py` (logout_view)
- `apps/accounts/serializers.py` (LogoutSerializer)
- SimpleJWT's token_blacklist (DB: token_blacklist_blacklistedtoken)

### (d) Create a Category Flow

1. Client sends `POST /api/v1/categories/` with `{"name": "...", "color": "..."}` and access token in header
2. `urls.py` routes to `CategoryViewSet`
3. DRF JWT authentication validates the token and sets `request.user`
4. `CategoryViewSet.perform_create()` calls `serializer.save(user=request.user)` (from OwnedQuerysetMixin)
5. `CategorySerializer.validate()` checks name uniqueness (case-insensitive) and color format
6. `CategorySerializer.save()` creates the Category with the user field set
7. Category is saved to `common_category` table
8. Response: `{"id": ..., "name": ..., "color": ..., ...}` with 201 status

**Files touched (in order)**:
- `apps/common/urls.py` (route)
- `apps/common/views.py` (CategoryViewSet + OwnedQuerysetMixin)
- `apps/common/serializers.py` (CategorySerializer)
- `apps/common/models.py` (Category)
- DB (common_category table)

**Key point**: The `OwnedQuerysetMixin` ensures the category is created under the authenticated user, regardless of what the client sends. This prevents users from creating categories for other users.

### (e) List Categories Flow (Data Isolation)

1. Client sends `GET /api/v1/categories/` with access token in header
2. `urls.py` routes to `CategoryViewSet`
3. DRF JWT authentication validates the token and sets `request.user`
4. `CategoryViewSet.get_queryset()` calls `super().get_queryset().filter(user=request.user)` (from OwnedQuerysetMixin)
5. Query is automatically scoped to only the requesting user's categories
6. Another user's categories are never included in the results
7. Response: JSON array of the user's categories (no pagination wrapper)

**Files touched (in order)**:
- `apps/common/urls.py` (route)
- `apps/common/views.py` (CategoryViewSet + OwnedQuerysetMixin)
- `apps/common/models.py` (Category - implicit via queryset)
- DB (common_category table, filtered by user)

**Key point**: The `OwnedQuerysetMixin` guarantees that users can only see their own data. If a user tries to access another user's category by ID, the queryset won't include it and Django returns 404.

## Auth Design

Calibre uses JWT (JSON Web Tokens) for authentication instead of session-based auth because:

- **Stateless**: No server-side session storage needed. Tokens contain all auth info.
- **Scalable**: Works well with multiple servers if needed later.
- **Mobile-friendly**: Flutter app can store tokens locally and send them with each request.
- **Logout support**: Token rotation + blacklist allow secure logout without server sessions.

### Token Configuration

- **Access token**: Valid for 30 minutes. Short-lived, used for API requests.
- **Refresh token**: Valid for 7 days. Long-lived, used to get new access tokens.
- **Rotation**: Every time a refresh token is used, a new one is issued and the old one is blacklisted.
- **Blacklist**: Blacklisted tokens cannot be used again. This implements secure logout.

### Email-based Login

Login uses email (not username) because:

- Emails are unique and familiar to users.
- Avoids username collision issues.
- More professional for a productivity app.
- Matches IITB student identities (Moodle uses email).

## Conventions

These global conventions apply to all apps:

### Database Conventions

- **Primary keys**: Integer `AutoField` (not UUIDs). Simple and efficient.
- **Deletion**: Hard delete (not soft delete). If you need history, use a separate audit table.
- **User ownership**: Every user-owned model has `user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)`.
- **Query scoping**: Views only query rows where `user=request.user`. Another user's data returns 404.
- **Table naming**: Lowercase with underscores: `accounts_user`, `tasks_task`, etc.
- **Category deletion**: When a category is deleted, dependent rows (tasks, events, etc.) should set their category reference to NULL (use `on_delete=SET_NULL`). This prevents accidental data loss when users delete categories.

### Time Conventions

- **USE_TZ = True**: Django stores and handles times in UTC.
- **Database times**: UTC ISO-8601 format (e.g., `2026-10-28T12:34:56Z`).
- **API times**: UTC ISO-8601 format.
- **User timezone**: Stored in `User.timezone` (e.g., `"Asia/Kolkata"`). Only used to compute "today" and similar display logic.
- **TIME_ZONE setting**: `"UTC"` in Django settings (not the user's timezone).

### API Conventions

- **Base path**: All endpoints under `/api/v1/`.
- **Authentication**: JWT required on all endpoints except register, login, refresh, logout, health.
- **Error format**: DRF default (`{"field": ["msg"]}` or `{"detail": "msg"}`). No custom error envelope.
- **Pagination**: `PageNumberPagination` with default 20 items per page, max 100 via `page_size` query param.
- **JSON keys**: snake_case (not camelCase). Matches Python/DB naming.
- **HTTP methods**: Use proper verbs (GET for read, POST for create, PATCH for partial update, DELETE for delete).

### Password Conventions

- **Validation**: Django's four standard validators (length, common passwords, similarity, numeric).
- **Hashing**: PBKDF2 with SHA256 (Django default). Never store plain text.
- **Change**: Old password must be verified before changing to a new one.

## Shared Base Classes

The `common` app provides reusable base classes that every later app uses:

### TimeStampedModel

Abstract base model that adds timestamp fields:
- `created_at`: Auto-set when the object is first created
- `updated_at`: Auto-updated every time the object is saved

Every model that needs to track when it was created/modified should inherit from this. This provides consistent audit trails across the entire backend.

### OwnedModel

Abstract base model for user-owned entities:
- Inherits from `TimeStampedModel` (gets created_at, updated_at)
- Adds `user` field: ForeignKey to `User` with CASCADE deletion
- Uses a dynamic `related_name` to avoid clashes (e.g., `tasks_task_set`, `events_event_set`)

Every model that belongs to a user (tasks, events, focus sessions, etc.) should inherit from this. This ensures:
1. Consistent user ownership across all user-owned data
2. Automatic cascade deletion when a user is deleted
3. No need to manually add user fields to each model

### OwnedQuerysetMixin

Mixin for DRF viewsets that enforces user data isolation:
- Overrides `get_queryset()` to filter by `user=request.user`
- Overrides `perform_create()` to set `user=request.user` on creation
- The serializer never exposes or accepts a user field

Every viewset for user-owned models should inherit from this mixin. This guarantees:
1. Users can only see their own data
2. Users can only create data under their own account
3. Even if a malicious client sends a different user ID, it's ignored
4. Accessing another user's data by ID returns 404 (data is not in the queryset)

**Why this matters**: Without this mixin, each viewset would need to manually filter by user and set the user on creation. The mixin centralizes this logic and prevents bugs where a developer forgets to add the filter.

## ER Diagram

```mermaid
erDiagram
    User {
        int id PK
        string email UK
        string password
        string name
        string timezone
        time work_start
        time work_end
        bool is_active
        bool is_staff
        datetime date_joined
        datetime last_login
    }

    User ||--o{ Category : owns

    Category {
        int id PK
        string name
        string color
        int sort_order
        bool is_default
        datetime created_at
        datetime updated_at
        int user FK
    }

    %% Additional tables will be added as apps are implemented
    %% Task {
    %%     int id PK
    %%     string title
    %%     string description
    %%     datetime due_date
    %%     bool completed
    %%     int category FK
    %%     int user FK
    %% }
```

**Current state**: The `User` and `Category` tables exist. Other tables will be added as apps are implemented in the build order.
