# Calibre API Documentation

**Version**: 0.1.0  
**Base URL**: `/api/v1/`  
**Authentication**: JWT Bearer Token (obtained from `/api/v1/auth/login/`)  
**Content-Type**: `application/json`  
**Timezone**: All timestamps are UTC (ISO 8601 format)  

---

## Table of Contents

1. [Authentication](#authentication)
2. [User Management](#user-management)
3. [Categories](#categories)
4. [Health](#health)
5. [Tasks](#tasks)
6. [Events](#events)
7. [External Events](#external-events)
8. [Routines](#routines)
9. [Routine Check-ins](#routine-check-ins)
10. [Calendar Agenda](#calendar-agenda)
11. [Free Slots](#free-slots)
12. [Moodle Integration](#moodle-integration)

---

## Authentication

### POST /auth/register/

Register a new user account. Default categories (Personal and Academics) are automatically created.

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "John Doe"
}
```

**Validation Rules**:
- `email`: Required, unique (case-insensitive), valid email format
- `password`: Required, min 8 characters, at least one uppercase, one lowercase, one digit
- `name`: Required, max 200 characters

**Response** (201 Created):
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "timezone": "Asia/Kolkata",
    "work_start": "09:00:00",
    "work_end": "18:00:00",
    "created_at": "2026-11-22T10:30:00Z",
    "updated_at": "2026-11-22T10:30:00Z"
  },
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Error Responses**:
- `400`: Invalid email format, weak password, duplicate email
- `500`: Server error

---

### POST /auth/login/

Authenticate with email and password to obtain JWT tokens.

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response** (200 OK):
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Error Responses**:
- `400`: Missing credentials
- `401`: Invalid email or password

---

### POST /auth/refresh/

Refresh an access token using a refresh token.

**Request Body**:
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Note**: Refresh tokens rotate on each refresh. Store the new refresh token to maintain your session.

**Error Responses**:
- `401`: Invalid or expired refresh token

---

### POST /auth/logout/

Logout by blacklisting the refresh token.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (204 No Content)

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid refresh token

---

### POST /auth/change-password/

Change the authenticated user's password.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "old_password": "SecurePass123!",
  "new_password": "NewSecurePass456!"
}
```

**Validation Rules**:
- `old_password`: Required, must match current password
- `new_password`: Required, min 8 characters, at least one uppercase, one lowercase, one digit

**Response** (204 No Content)

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Wrong old password or weak new password

---

### POST /auth/delete-account/

Delete the authenticated user's account and all associated data.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "password": "SecurePass123!"
}
```

**Response** (204 No Content)

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Wrong password

---

## User Management

### GET /users/me/

Get the authenticated user's profile.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe",
  "timezone": "Asia/Kolkata",
  "work_start": "09:00:00",
  "work_end": "18:00:00",
  "created_at": "2026-11-22T10:30:00Z",
  "updated_at": "2026-11-22T10:30:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token

---

### PATCH /users/me/

Update the authenticated user's profile.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body** (all fields optional):
```json
{
  "name": "John Updated",
  "timezone": "America/New_York",
  "work_start": "08:00:00",
  "work_end": "17:00:00"
}
```

**Validation Rules**:
- `name`: Max 200 characters
- `timezone`: Valid IANA timezone identifier
- `work_start`: Valid time, must be before `work_end`
- `work_end`: Valid time, must be after `work_start`

**Response** (200 OK):
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Updated",
  "timezone": "America/New_York",
  "work_start": "08:00:00",
  "work_end": "17:00:00",
  "created_at": "2026-11-22T10:30:00Z",
  "updated_at": "2026-11-22T15:45:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid timezone, work_start after work_end

---

## Categories

### GET /categories/

List all categories for the authenticated user.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
[
  {
    "id": 1,
    "name": "Academics",
    "color": "#FF5733",
    "created_at": "2026-11-22T10:30:00Z",
    "updated_at": "2026-11-22T10:30:00Z"
  },
  {
    "id": 2,
    "name": "Work",
    "color": "#33FF57",
    "created_at": "2026-11-22T10:30:00Z",
    "updated_at": "2026-11-22T10:30:00Z"
  }
]
```

**Error Responses**:
- `401`: Missing or invalid access token

---

### POST /categories/

Create a new category for the authenticated user.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "name": "Personal",
  "color": "#3357FF"
}
```

**Validation Rules**:
- `name`: Required, max 100 characters, unique per user (case-insensitive)
- `color`: Required, valid hex color code (e.g., "#FF5733")

**Response** (201 Created):
```json
{
  "id": 3,
  "name": "Personal",
  "color": "#3357FF",
  "created_at": "2026-11-22T12:00:00Z",
  "updated_at": "2026-11-22T12:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid color, duplicate name

---

### GET /categories/{id}/

Get a specific category by ID.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": 1,
  "name": "Academics",
  "color": "#FF5733",
  "created_at": "2026-11-22T10:30:00Z",
  "updated_at": "2026-11-22T10:30:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Category not found or belongs to another user

---

### PATCH /categories/{id}/

Update a category.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body** (all fields optional):
```json
{
  "name": "Study",
  "color": "#FF3333"
}
```

**Response** (200 OK):
```json
{
  "id": 1,
  "name": "Study",
  "color": "#FF3333",
  "created_at": "2026-11-22T10:30:00Z",
  "updated_at": "2026-11-22T13:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Category not found or belongs to another user
- `400`: Invalid color, duplicate name

---

### DELETE /categories/{id}/

Delete a category. Tasks/events with this category will have their category set to null.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (204 No Content)

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Category not found or belongs to another user

---

## Health

### GET /health/

Health check endpoint (public, no authentication required).

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2026-11-22T15:00:00Z"
}
```

---

## Tasks

### GET /tasks/

List tasks for the authenticated user with filtering and pagination.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters** (all optional):
- `status`: Filter by status (`todo`, `done`)
- `category`: Filter by category ID
- `important`: Filter by importance (`true`, `false`)
- `source`: Filter by source (`manual`, `moodle`)
- `due_before`: Filter tasks due before this datetime (ISO 8601)
- `due_after`: Filter tasks due after this datetime (ISO 8601)
- `ordering`: Sort order (`due_at`, `-due_at`, `id`, `-id`)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20)

**Response** (200 OK):
```json
{
  "count": 42,
  "next": "http://localhost:8000/api/v1/tasks/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Complete assignment",
      "notes": "Chapter 5 exercises",
      "category": 1,
      "status": "todo",
      "is_important": true,
      "estimate_min": 60,
      "due_at": "2026-11-25T18:30:00Z",
      "completed_at": null,
      "source": "manual",
      "external_id": "",
      "created_at": "2026-11-22T10:30:00Z",
      "updated_at": "2026-11-22T10:30:00Z"
    }
  ]
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid filter value

---

### POST /tasks/

Create a new task.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "title": "Complete assignment",
  "notes": "Chapter 5 exercises",
  "category": 1,
  "is_important": true,
  "estimate_min": 60,
  "due_at": "2026-11-25T18:30:00Z"
}
```

**Validation Rules**:
- `title`: Required, max 200 characters
- `notes`: Optional, blank allowed
- `category`: Optional, must belong to user
- `is_important`: Optional, default `false`
- `estimate_min`: Optional, 0-1440 minutes
- `due_at`: Optional, ISO 8601 datetime
- `status`, `completed_at`, `source`, `external_id`: Ignored (server-set)

**Response** (201 Created):
```json
{
  "id": 1,
  "title": "Complete assignment",
  "notes": "Chapter 5 exercises",
  "category": 1,
  "status": "todo",
  "is_important": true,
  "estimate_min": 60,
  "due_at": "2026-11-25T18:30:00Z",
  "completed_at": null,
  "source": "manual",
  "external_id": "",
  "created_at": "2026-11-22T12:00:00Z",
  "updated_at": "2026-11-22T12:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid title length, invalid estimate, category belongs to another user

---

### GET /tasks/{id}/

Get a specific task by ID.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": 1,
  "title": "Complete assignment",
  "notes": "Chapter 5 exercises",
  "category": 1,
  "status": "todo",
  "is_important": true,
  "estimate_min": 60,
  "due_at": "2026-11-25T18:30:00Z",
  "completed_at": null,
  "source": "manual",
  "external_id": "",
  "created_at": "2026-11-22T12:00:00Z",
  "updated_at": "2026-11-22T12:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Task not found or belongs to another user

---

### PATCH /tasks/{id}/

Update a task (partial update).

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body** (all fields optional):
```json
{
  "title": "Updated assignment",
  "notes": "Chapter 5-7 exercises",
  "category": 2,
  "is_important": false,
  "estimate_min": 90,
  "due_at": "2026-11-26T18:30:00Z"
}
```

**Note**: `status` and `completed_at` cannot be updated via PATCH. Use the complete/reopen endpoints.

**Response** (200 OK):
```json
{
  "id": 1,
  "title": "Updated assignment",
  "notes": "Chapter 5-7 exercises",
  "category": 2,
  "status": "todo",
  "is_important": false,
  "estimate_min": 90,
  "due_at": "2026-11-26T18:30:00Z",
  "completed_at": null,
  "source": "manual",
  "external_id": "",
  "created_at": "2026-11-22T12:00:00Z",
  "updated_at": "2026-11-22T14:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Task not found or belongs to another user
- `400`: Invalid field values

---

### DELETE /tasks/{id}/

Delete a task.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (204 No Content)

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Task not found or belongs to another user

---

### POST /tasks/{id}/complete/

Mark a task as done.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": 1,
  "title": "Complete assignment",
  "notes": "Chapter 5 exercises",
  "category": 1,
  "status": "done",
  "is_important": true,
  "estimate_min": 60,
  "due_at": "2026-11-25T18:30:00Z",
  "completed_at": "2026-11-22T15:00:00Z",
  "source": "manual",
  "external_id": "",
  "created_at": "2026-11-22T12:00:00Z",
  "updated_at": "2026-11-22T15:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Task not found or belongs to another user

---

### POST /tasks/{id}/reopen/

Reopen a done task (set status back to todo).

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": 1,
  "title": "Complete assignment",
  "notes": "Chapter 5 exercises",
  "category": 1,
  "status": "todo",
  "is_important": true,
  "estimate_min": 60,
  "due_at": "2026-11-25T18:30:00Z",
  "completed_at": null,
  "source": "manual",
  "external_id": "",
  "created_at": "2026-11-22T12:00:00Z",
  "updated_at": "2026-11-22T16:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Task not found or belongs to another user

---

### GET /tasks/today/

Get tasks due today in the user's local timezone.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
[
  {
    "id": 1,
    "title": "Complete assignment",
    "notes": "Chapter 5 exercises",
    "category": 1,
    "status": "todo",
    "is_important": true,
    "estimate_min": 60,
    "due_at": "2026-11-22T18:30:00Z",
    "completed_at": null,
    "source": "manual",
    "external_id": "",
    "created_at": "2026-11-22T10:00:00Z",
    "updated_at": "2026-11-22T10:00:00Z"
  }
]
```

**Error Responses**:
- `401`: Missing or invalid access token

---

### GET /tasks/overdue/

Get overdue tasks (status=todo and due_at < now).

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20)

**Response** (200 OK):
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 2,
      "title": "Submit project",
      "notes": "",
      "category": null,
      "status": "todo",
      "is_important": false,
      "estimate_min": null,
      "due_at": "2026-11-20T18:30:00Z",
      "completed_at": null,
      "source": "manual",
      "external_id": "",
      "created_at": "2026-11-18T10:00:00Z",
      "updated_at": "2026-11-18T10:00:00Z"
    }
  ]
}
```

**Error Responses**:
- `401`: Missing or invalid access token

---

### GET /tasks/now/

Get current tasks prioritized by urgency and importance (matrix method).

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
- `limit`: Maximum number of tasks to return (default: 20, max: 50)

**Response** (200 OK):
```json
[
  {
    "id": 1,
    "title": "Complete assignment",
    "notes": "Chapter 5 exercises",
    "category": 1,
    "status": "todo",
    "is_important": true,
    "estimate_min": 60,
    "due_at": "2026-11-25T18:30:00Z",
    "completed_at": null,
    "source": "manual",
    "external_id": "",
    "created_at": "2026-11-22T10:00:00Z",
    "updated_at": "2026-11-22T10:00:00Z"
  }
]
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid limit value

---

### GET /tasks/matrix/

Get tasks organized by the Eisenhower Matrix (quadrants).

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "urgent_important": [
    {
      "id": 1,
      "title": "Complete assignment",
      "due_at": "2026-11-25T18:30:00Z",
      "is_important": true,
      "estimate_min": 60
    }
  ],
  "not_urgent_important": [],
  "urgent_not_important": [],
  "not_urgent_not_important": []
}
```

**Error Responses**:
- `401`: Missing or invalid access token

---

## Events

### GET /events/

List events for the authenticated user with filtering and pagination.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters** (all optional):
- `kind`: Filter by kind (`event`, `block`)
- `category`: Filter by category ID
- `source`: Filter by source (`manual`, `moodle`, `cse`, `insti`, `course`)
- `external_id`: Filter by external_id
- `series_id`: Filter by series_id (for repeating events)
- `start_date`: Filter events overlapping after this local date (YYYY-MM-DD)
- `end_date`: Filter events overlapping before this local date (YYYY-MM-DD)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 200)

**Note**: Date filters use overlap semantics - events that start before the window and end inside it are included.

**Response** (200 OK):
```json
{
  "count": 15,
  "next": "http://localhost:8000/api/v1/events/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "CS699 Lab",
      "notes": "KReSIT 203",
      "location": "KReSIT",
      "category": 1,
      "kind": "event",
      "task": null,
      "start_at": "2026-11-22T09:00:00Z",
      "end_at": "2026-11-22T11:00:00Z",
      "remind_at": "2026-11-22T08:30:00Z",
      "source": "manual",
      "external_id": "",
      "series_id": null,
      "created_at": "2026-11-22T08:00:00Z",
      "updated_at": "2026-11-22T08:00:00Z"
    }
  ]
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid date format, invalid filter value

---

### POST /events/

Create a new event. Supports repeat rules for recurring events.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body** (single event):
```json
{
  "title": "CS699 Lab",
  "notes": "KReSIT 203",
  "location": "KReSIT",
  "category": 1,
  "kind": "event",
  "task": null,
  "start_at": "2026-11-22T09:00:00Z",
  "end_at": "2026-11-22T11:00:00Z",
  "remind_at": "2026-11-22T08:30:00Z"
}
```

**Request Body** (repeating event):
```json
{
  "title": "CS699 Lab",
  "notes": "KReSIT 203",
  "location": "KReSIT",
  "category": 1,
  "kind": "event",
  "start_at": "2026-11-23T04:30:00Z",
  "end_at": "2026-11-23T06:30:00Z",
  "remind_at": "2026-11-23T04:00:00Z",
  "repeat": {
    "freq": "weekly",
    "weekdays": [0, 2],
    "until": "2027-03-31"
  }
}
```

**Validation Rules**:
- `title`: Required, max 200 characters, whitespace stripped
- `notes`: Optional, blank allowed
- `location`: Optional, max 200 characters, blank allowed
- `category`: Optional, must belong to user
- `kind`: Optional, `event` or `block`, default `event`
- `task`: Optional, must belong to user
- `start_at`: Required, ISO 8601 datetime
- `end_at`: Required, ISO 8601 datetime, must be >= start_at (zero-length allowed)
- `remind_at`: Optional, ISO 8601 datetime
- `source`, `external_id`: Ignored (server-set)
- `repeat`: Optional, object with:
  - `freq`: Required, `daily` or `weekly`
  - `weekdays`: Required for `weekly`, list of integers 0-6 (Monday=0)
  - `until`: Required, local date (YYYY-MM-DD), inclusive
  - The weekday of `start_at` must be in the `weekdays` list for `weekly`
  - Maximum 366 occurrences

**Response** (201 Created, single event):
```json
{
  "id": 1,
  "title": "CS699 Lab",
  "notes": "KReSIT 203",
  "location": "KReSIT",
  "category": 1,
  "kind": "event",
  "task": null,
  "start_at": "2026-11-22T09:00:00Z",
  "end_at": "2026-11-22T11:00:00Z",
  "remind_at": "2026-11-22T08:30:00Z",
  "source": "manual",
  "external_id": "",
  "series_id": null,
  "created_at": "2026-11-22T08:00:00Z",
  "updated_at": "2026-11-22T08:00:00Z"
}
```

**Response** (201 Created, repeating event):
```json
{
  "series_id": "550e8400-e29b-41d4-a716-446655440000",
  "count": 18,
  "first": {
    "id": 1,
    "title": "CS699 Lab",
    "notes": "KReSIT 203",
    "location": "KReSIT",
    "category": 1,
    "kind": "event",
    "task": null,
    "start_at": "2026-11-23T04:30:00Z",
    "end_at": "2026-11-23T06:30:00Z",
    "remind_at": "2026-11-23T04:00:00Z",
    "source": "manual",
    "external_id": "",
    "series_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-11-22T08:00:00Z",
    "updated_at": "2026-11-22T08:00:00Z"
  }
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid title, end_at < start_at, category/task belongs to another user, invalid repeat rule

---

### GET /events/{id}/

Get a specific event by ID.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": 1,
  "title": "CS699 Lab",
  "notes": "KReSIT 203",
  "location": "KReSIT",
  "category": 1,
  "kind": "event",
  "task": null,
  "start_at": "2026-11-22T09:00:00Z",
  "end_at": "2026-11-22T11:00:00Z",
  "remind_at": "2026-11-22T08:30:00Z",
  "source": "manual",
  "external_id": "",
  "created_at": "2026-11-22T08:00:00Z",
  "updated_at": "2026-11-22T08:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Event not found or belongs to another user

---

### PATCH /events/{id}/

Update an event (partial update). Supports scope parameter for repeating events.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
- `scope`: Optional, `this` (default), `following`, or `all`
  - `this`: Update only this event
  - `following`: Update this and all later events in the series
  - `all`: Update all events in the series

**Request Body** (all fields optional):
```json
{
  "title": "Updated Lab",
  "notes": "KReSIT 205",
  "location": "KReSIT",
  "category": 2,
  "start_at": "2026-11-22T10:00:00Z",
  "end_at": "2026-11-22T12:00:00Z"
}
```

**Scope Behavior**:
- With `scope=following` or `scope=all`, date changes (`start_at`, `end_at`) are not allowed
- Only title, notes, location, category, kind, and task can be changed with scope
- Time changes move the time of day by the same offset for each occurrence
- Scope is ignored for events without a series_id

**Response** (200 OK):
```json
{
  "id": 1,
  "title": "Updated Lab",
  "notes": "KReSIT 205",
  "location": "KReSIT",
  "category": 2,
  "kind": "event",
  "task": null,
  "start_at": "2026-11-22T10:00:00Z",
  "end_at": "2026-11-22T12:00:00Z",
  "remind_at": "2026-11-22T08:30:00Z",
  "source": "manual",
  "external_id": "",
  "series_id": null,
  "created_at": "2026-11-22T08:00:00Z",
  "updated_at": "2026-11-22T14:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Event not found or belongs to another user
- `400`: Invalid field values, invalid scope, date changes with scope

---

### DELETE /events/{id}/

Delete an event. Supports scope parameter for repeating events.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
- `scope`: Optional, `this` (default), `following`, or `all`
  - `this`: Delete only this event
  - `following`: Delete this and all later events in the series
  - `all`: Delete all events in the series

**Scope Behavior**:
- Scope is ignored for events without a series_id
- Deleting one event from a series keeps the rest of the series

**Response** (204 No Content)

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Event not found or belongs to another user
- `400`: Invalid scope

---

## External Events

### GET /external-events/

List shared external events from CSE or Institute feeds.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters** (all required):
- `source`: Filter by source (`cse` or `insti`)
- `start_date`: Local date (YYYY-MM-DD)
- `end_date`: Local date (YYYY-MM-DD), must be >= start_date
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 200)

**Note**: Date filters use overlap semantics - events that start before the window and end inside it are included.

**Response** (200 OK):
```json
{
  "count": 42,
  "next": "http://localhost:8000/api/v1/external-events/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "source": "cse",
      "external_id": "abc123...",
      "title": "Machine Learning Seminar",
      "description": "Abstract of the talk...",
      "location": "LH 1",
      "start_at": "2026-11-25T14:00:00Z",
      "end_at": "2026-11-25T15:00:00Z",
      "url": "https://example.com/event"
    }
  ]
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid date format, invalid source value

---

### POST /external-events/{id}/add/

Add an external event to the user's own events.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (201 Created for new event, 200 OK if already added):
```json
{
  "id": 100,
  "title": "Machine Learning Seminar",
  "notes": "Abstract of the talk...",
  "location": "LH 1",
  "category": 2,
  "kind": "event",
  "task": null,
  "start_at": "2026-11-25T14:00:00Z",
  "end_at": "2026-11-25T15:00:00Z",
  "remind_at": null,
  "source": "cse",
  "external_id": "abc123...",
  "series_id": null,
  "created_at": "2026-11-22T12:00:00Z",
  "updated_at": "2026-11-22T12:00:00Z"
}
```

**Behavior**:
- Creates a copy of the external event as the user's own event
- Uses the user's Personal category
- If the user already added this event, returns the existing event (not an error)
- The copy is independent: editing or deleting it never changes the shared external event
- Returns 404 if the external event does not exist or was removed

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: External event not found or removed

---

## Routines

### GET /routines/

List routines for the authenticated user with pagination.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20)

**Response** (200 OK):
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Morning Exercise",
      "category": 2,
      "weekdays": [0, 2, 4],
      "start_time": "06:00:00",
      "end_time": "07:00:00",
      "start_date": "2026-11-01",
      "end_date": null,
      "is_active": true,
      "created_at": "2026-11-01T08:00:00Z",
      "updated_at": "2026-11-01T08:00:00Z"
    }
  ]
}
```

**Error Responses**:
- `401`: Missing or invalid access token

---

### POST /routines/

Create a new routine.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "title": "Morning Exercise",
  "category": 2,
  "weekdays": [0, 2, 4],
  "start_time": "06:00:00",
  "end_time": "07:00:00",
  "start_date": "2026-11-01",
  "end_date": null,
  "is_active": true
}
```

**Validation Rules**:
- `title`: Required, max 200 characters, whitespace stripped
- `category`: Optional, must belong to user
- `weekdays`: Required, non-empty list of integers 0-6 (Monday=0, Sunday=6), unique values
- `start_time`: Required, wall-clock time
- `end_time`: Required, must be after start_time
- `start_date`: Optional, local date (defaults to user's local today)
- `end_date`: Optional, local date, must be >= start_date
- `is_active`: Optional, default `true`

**Response** (201 Created):
```json
{
  "id": 1,
  "title": "Morning Exercise",
  "category": 2,
  "weekdays": [0, 2, 4],
  "start_time": "06:00:00",
  "end_time": "07:00:00",
  "start_date": "2026-11-01",
  "end_date": null,
  "is_active": true,
  "created_at": "2026-11-01T08:00:00Z",
  "updated_at": "2026-11-01T08:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid weekdays, end_time <= start_time, end_date < start_date, category belongs to another user

---

### GET /routines/{id}/

Get a specific routine by ID.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": 1,
  "title": "Morning Exercise",
  "category": 2,
  "weekdays": [0, 2, 4],
  "start_time": "06:00:00",
  "end_time": "07:00:00",
  "start_date": "2026-11-01",
  "end_date": null,
  "is_active": true,
  "created_at": "2026-11-01T08:00:00Z",
  "updated_at": "2026-11-01T08:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Routine not found or belongs to another user

---

### PATCH /routines/{id}/

Update a routine (partial update).

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body** (all fields optional):
```json
{
  "title": "Updated Exercise",
  "weekdays": [1, 3, 5],
  "start_time": "07:00:00",
  "end_time": "08:00:00"
}
```

**Response** (200 OK):
```json
{
  "id": 1,
  "title": "Updated Exercise",
  "category": 2,
  "weekdays": [1, 3, 5],
  "start_time": "07:00:00",
  "end_time": "08:00:00",
  "start_date": "2026-11-01",
  "end_date": null,
  "is_active": true,
  "created_at": "2026-11-01T08:00:00Z",
  "updated_at": "2026-11-22T14:00:00Z"
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Routine not found or belongs to another user
- `400`: Invalid field values

---

### DELETE /routines/{id}/

Delete a routine (cascades to all check-ins).

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (204 No Content)

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Routine not found or belongs to another user

---

## Routine Check-ins

### POST /routines/{id}/checkin/

Create or update a check-in for a routine occurrence.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "date": "2026-11-22",
  "done": true
}
```

**Validation Rules**:
- `date`: Required, local date (YYYY-MM-DD), must be a scheduled day for the routine
- `done`: Optional, default `true`

**Response** (201 Created for new check-in, 200 OK for update):
```json
{
  "routine": 1,
  "date": "2026-11-22",
  "done": true
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Routine not found or belongs to another user
- `400`: Invalid date format, routine does not occur on this date

---

### DELETE /routines/{id}/checkin/?date=YYYY-MM-DD

Remove/reset a check-in for a routine occurrence.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
- `date`: Required, local date (YYYY-MM-DD)

**Response** (204 No Content, idempotent)

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Routine not found or belongs to another user
- `400`: Missing date parameter

---

## Calendar Agenda

### GET /calendar/agenda/

Get a merged agenda of events, routine occurrences, and tasks for a date range.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
- `start_date`: Required, local date (YYYY-MM-DD)
- `end_date`: Required, local date (YYYY-MM-DD), must be >= start_date
- Maximum span: 62 days

**Response** (200 OK):
```json
{
  "start_date": "2026-11-22",
  "end_date": "2026-11-28",
  "timezone": "Asia/Kolkata",
  "items": [
    {
      "type": "event",
      "id": 1,
      "title": "CS699 Lab",
      "start_at": "2026-11-22T09:00:00Z",
      "end_at": "2026-11-22T11:00:00Z",
      "category": 1,
      "status": null,
      "details": {
        "kind": "event",
        "task": null,
        "location": "KReSIT"
      },
      "source": "manual",
      "external_id": null,
      "series_id": null
    },
    {
      "type": "routine",
      "id": 1,
      "title": "Morning Exercise",
      "start_at": "2026-11-22T00:30:00Z",
      "end_at": "2026-11-22T01:30:00Z",
      "category": 2,
      "status": "pending",
      "details": {
        "date": "2026-11-22"
      }
    },
    {
      "type": "task",
      "id": 1,
      "title": "Complete assignment",
      "start_at": "2026-11-25T18:30:00Z",
      "end_at": null,
      "category": 1,
      "status": "todo",
      "details": {
        "estimate_min": 60,
        "is_important": true
      }
    }
  ]
}
```

**Item Types**:
- `event`: From Event model overlapping the window
- `routine`: Generated routine occurrences (status: `pending`, `done`, `skipped`)
- `task`: Tasks with due_at in the window (status: `todo`, `done`)

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Missing parameters, invalid dates, span > 62 days

---

## Free Slots

### GET /free-slots/

Get free time slots with task suggestions for a specific day.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
- `date`: Optional, local date (YYYY-MM-DD), defaults to user's local today
- `min_minutes`: Optional, minimum slot duration in minutes (5-480, default: 15)

**Response** (200 OK):
```json
{
  "date": "2026-11-22",
  "timezone": "Asia/Kolkata",
  "work_window": {
    "start_at": "2026-11-22T03:30:00Z",
    "end_at": "2026-11-22T12:30:00Z"
  },
  "slots": [
    {
      "start_at": "2026-11-22T09:00:00Z",
      "end_at": "2026-11-22T10:15:00Z",
      "minutes": 75,
      "suggestions": [
        {
          "id": 1,
          "title": "Complete assignment",
          "estimate_min": 60,
          "due_at": "2026-11-25T18:30:00Z",
          "is_important": true
        }
      ]
    }
  ]
}
```

**Behavior**:
- Work window = user's work_start to work_end on the local day
- Events and pending routines block time
- Skipped routines free time
- On today, first slot starts at now if inside work hours
- Suggestions use greedy first-fit algorithm ordered by priority_rank

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid date, min_minutes out of range (4 or 481)

---

## Moodle Integration

### POST /moodle/connect/

Connect the user's Moodle account with their token.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Request Body**:
```json
{
  "token": "moodlemobile://token=<base64_string>"
}
```

**Note**: The token can be:
- A full launch URL: `moodlemobile://token=<base64>`
- A bare base64 string
- A plain 32-character token

**Response** (201 Created for new connection, 200 OK for update):
```json
{
  "connected": true,
  "status": "active",
  "moodle_userid": 12345
}
```

**Error Responses**:
- `401`: Missing or invalid access token
- `400`: Invalid token format, Moodle rejected the token
- `502`: Moodle unreachable or returned an error

---

### GET /moodle/status/

Get the user's Moodle connection status.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "connected": true,
  "status": "active",
  "moodle_userid": 12345,
  "last_synced_at": "2026-11-22T12:00:00Z",
  "last_error": "",
  "imported": {
    "tasks": 15,
    "events": 8
  }
}
```

**When not connected**:
```json
{
  "connected": false,
  "status": null,
  "moodle_userid": null,
  "last_synced_at": null,
  "last_error": "",
  "imported": {
    "tasks": 0,
    "events": 0
  }
}
```

**Error Responses**:
- `401`: Missing or invalid access token

---

### POST /moodle/sync/

Sync Moodle events and tasks for the user.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Rate Limit**: 10 requests per hour per user

**Response** (200 OK):
```json
{
  "tasks": {
    "created": 3,
    "updated": 2,
    "deleted": 1
  },
  "events": {
    "created": 5,
    "updated": 1,
    "deleted": 0
  },
  "course_events": {
    "created": 15,
    "updated": 2,
    "deleted": 1
  },
  "synced_at": "2026-11-22T15:00:00Z",
  "window": {
    "start": "2026-10-22T18:30:00Z",
    "end": "2027-05-22T18:30:00Z"
  }
}
```

**Sync Behavior**:
- Fetches events from Moodle for the configured sync window (default: 1 month back, 6 months forward)
- Moodle deadlines become Tasks with `source="moodle"`
- Other events become Events with `source="moodle"`
- Updates only Moodle-owned fields (title, due_at, start_at, end_at)
- Never overwrites user-owned fields (status, category, notes, is_important, estimate_min)
- Deletes removed items within the sync window (todo tasks only, keeps done tasks)
- Also syncs course schedule events from CourseSchedule table based on enrolled courses
- Course events have `source="course"` and are generated from course schedules

**Error Responses**:
- `401`: Missing or invalid access token
- `404`: Moodle not connected
- `409`: Token expired (code: `moodle_reauth_required`)
- `429`: Rate limit exceeded
- `502`: Moodle unreachable or returned an error

---

### DELETE /moodle/

Disconnect the user's Moodle account.

**Request Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
- `delete_imported`: Optional, `true` to also delete imported Moodle tasks and events

**Response** (204 No Content, idempotent)

**Behavior**:
- Without `delete_imported`: Keeps all imported tasks and events
- With `delete_imported=true`: Deletes all Moodle-sourced events and todo tasks (keeps done tasks)

**Error Responses**:
- `401`: Missing or invalid access token

---

## Feed Sync Management Commands

The following Django management commands are available for syncing external event feeds:

### sync_cse_feed

Syncs CSE department talks from the IITB CSE feed.

**Usage**:
```bash
python manage.py sync_cse_feed
```

**Behavior**:
- Fetches from https://www.cse.iitb.ac.in/~internal-live/webcal/export/
- Keeps events starting 30 days ago or later
- Parses ICS format (SUMMARY → title, ABSTRACT → description, DTSTART → start_at)
- Sets end_at to start_at + 1 hour (configurable duration)
- Builds external_id as hash of title + start_at
- Marks events that vanished from the feed as removed
- Logs counts of created, updated, and removed events

### sync_insti_feed

Syncs Institute events from the IITB Gymkhana API.

**Usage** (light sync, hourly):
```bash
python manage.py sync_insti_feed
```

**Usage** (full sync, initial or daily):
```bash
python manage.py sync_insti_feed --full
```

**Options**:
- `--full`: Fetch the full events-all list (~10MB, slower) instead of the light events list (~11KB)
- `--cutoff-days`: Import events from this many days ago (default: 30)

**Behavior**:
- **Light sync (hourly)**: Fetches from https://gymkhana.iitb.ac.in/instiapp/api/events (4 newest events, ~11KB)
  - 30-second timeout
  - Upserts only the newest events
  - Does not mark events as removed
- **Full sync (initial/daily)**: Fetches from https://gymkhana.iitb.ac.in/instiapp/api/events-all (all events, ~10MB)
  - 120-second timeout with up to 3 retries
  - Imports only events with `verification_status=approved`
  - Imports events from 30 days ago or later (configurable)
  - Skips bad dates (e.g., 1970-01-01)
  - Converts ISO 8601 timestamps with +05:30 offset to UTC
  - Handles all_day events by using the whole local day
  - Maps: id → external_id, name → title, description/longdescription → description, start_time/end_time → start_at/end_at, website_url → url
  - Builds location from venues list and venue_room
  - Marks events that vanished from the feed as removed
  - Logs counts of created, updated, and removed events

**Recommended Schedule**:
1. First run: `sync_insti_feed --full` to import all approved events from 30 days ago
2. Hourly: `sync_insti_feed` to keep newest events current
3. Daily (night): `sync_insti_feed --full` to catch changed/approved events

Both commands keep the last good data if fetch fails.

Both commands:
- Run with a 30-second timeout
- Keep the last good data if fetch fails
- Log errors without crashing

These commands should be scheduled to run periodically (e.g., via cron) to keep the external events up to date.

---

## Course Events

Course events are automatically generated from the CourseSchedule table based on a user's enrolled courses from Moodle. These events appear under the Academics category and represent scheduled class meetings.

**Source**: `course`

**External ID Format**: `{course_code}_{slot}_{date}` (e.g., `CS101_L1_2026-11-23`)

**Behavior**:
- Generated automatically after Moodle connection and on each sync
- One event per class meeting from semester start to end
- Uses the course's schedule weekdays, times, and venue
- Deleted class occurrences are tracked and not recreated on future syncs
- Future events for dropped courses are automatically deleted
- Updates only title, times, and location on sync (preserves user edits to notes and category)

**Note**: Course events follow the same ownership rules as Moodle events - the system owns the core fields (title, times, location) while the user owns notes and category.

---

## Error Response Format

All error responses follow the standard DRF format:

```json
{
  "detail": "Error message"
}
```

For validation errors (400):
```json
{
  "field_name": ["Error message 1", "Error message 2"]
}
```

For Moodle reauth required (409):
```json
{
  "code": "moodle_reauth_required",
  "detail": "Your Moodle connection expired. Please reconnect."
}
```

---

## Pagination

List endpoints use page-based pagination. Response includes:

```json
{
  "count": 100,
  "next": "http://localhost:8000/api/v1/tasks/?page=2",
  "previous": null,
  "results": [...]
}
```

Query parameters:
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20)

---

## Authentication

All endpoints except `/health/` require authentication. Include the access token in the Authorization header:

```
Authorization: Bearer <access_token>
```

Access tokens expire after 30 minutes. Use the refresh token to obtain a new access token via `/auth/refresh/`.

---

## Timezone Handling

- All stored timestamps are UTC
- All API timestamps are ISO 8601 with `Z` suffix
- Date-based endpoints use the user's local timezone
- Routine times are wall-clock times in the user's timezone
- Work hours are wall-clock times in the user's timezone

---

## Field Ownership (Moodle Sync)

When syncing from Moodle, only Moodle-owned fields are updated:

| Field | Owner | Sync Behavior |
|-------|-------|--------------|
| `title` | Moodle | Updated on sync |
| `due_at` / `start_at` / `end_at` | Moodle | Updated on sync |
| `status` | User | Never changed |
| `category` | User | Never changed |
| `notes` | User | Never changed |
| `is_important`, `estimate_min` | User | Never changed |
| `completed_at` | User | Never changed |

Users can mark Moodle tasks as done, change categories, add estimates, or edit notes without losing changes on future syncs.

---

## Rate Limiting

- General user rate limit: 600 requests per minute
- Auth rate limit: 10 requests per minute
- Moodle sync rate limit: 10 requests per hour

Rate limit exceeded returns 429 status code.

---

## OpenAPI/Swagger

Interactive API documentation available at:
- Swagger UI: `/api/v1/docs/`
- OpenAPI Schema: `/api/v1/schema/`
