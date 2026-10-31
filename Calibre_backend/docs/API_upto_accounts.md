# Calibre Backend API Documentation

This document describes the REST API for the Calibre backend, intended for frontend (Flutter) developers.

## Base URL

```
http://localhost:8000/api/v1
```

Replace with the actual server URL in production.

## Authentication

Calibre uses JWT (JSON Web Tokens) for authentication.

### Token Flow

1. **Register** or **Login** to get an access token and refresh token
2. Include the access token in the `Authorization` header for authenticated requests:
   ```
   Authorization: Bearer <access_token>
   ```
3. When the access token expires (30 minutes), use the refresh token to get a new pair
4. To logout, send the refresh token to the logout endpoint (blacklists it)

### Token Lifetimes

- **Access token**: 30 minutes
- **Refresh token**: 7 days

### Auth Endpoints

All auth endpoints are public (no token required):
- `POST /auth/register/`
- `POST /auth/login/`
- `POST /auth/token/refresh/`
- `POST /auth/logout/`

All other endpoints require authentication.

## Response Format

### Success Responses

- **201 Created**: `{"field": value, ...}` or `{"user": {...}, "access": "...", "refresh": "..."}`
- **200 OK**: `{"field": value, ...}`
- **204 No Content**: Empty body (used for successful operations with no return data)

### Error Responses

Errors use DRF's default format:

```json
{
  "field": ["error message"],
  "another_field": ["another error message"]
}
```

Or for general errors:

```json
{
  "detail": "error message"
}
```

### Common Status Codes

- `200 OK`: Successful GET, PATCH
- `201 Created`: Successful POST
- `204 No Content`: Successful DELETE, logout, password change
- `400 Bad Request`: Invalid input data
- `401 Unauthorized`: Missing or invalid token, wrong credentials
- `403 Forbidden`: Valid token but insufficient permissions
- `404 Not Found`: Resource doesn't exist (or belongs to another user)

## Data Models

### User

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe",
  "timezone": "Asia/Kolkata",
  "work_start": "09:00",
  "work_end": "18:00",
  "date_joined": "2026-10-28T12:34:56Z"
}
```

**Fields**:
- `id` (integer, read-only): Unique user ID
- `email` (string, read-only): User's email address
- `name` (string, optional): Display name
- `timezone` (string): IANA timezone identifier (e.g., "Asia/Kolkata", "America/New_York")
- `work_start` (string, time): Work day start time in HH:MM format (24-hour)
- `work_end` (string, time): Work day end time in HH:MM format (24-hour)
- `date_joined` (string, datetime, read-only): UTC timestamp when user was created

**Constraints**:
- `timezone` must be a valid IANA timezone (use `zoneinfo.available_timezones()` to validate)
- `work_start` must be earlier than `work_end`

## Endpoints

### Authentication

#### POST /auth/register/

Register a new user account.

**Request** (public):
```json
{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "name": "John Doe"
}
```

**Fields**:
- `email` (required, string): Valid email address, case-insensitive unique
- `password` (required, string): Must pass Django's password validators (minimum length, not common, not similar to email, not all numeric)
- `name` (optional, string): Display name, max 100 characters

**Response** (201):
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "timezone": "Asia/Kolkata",
    "work_start": "09:00",
    "work_end": "18:00",
    "date_joined": "2026-10-28T12:34:56Z"
  },
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Errors** (400):
```json
{
  "email": ["A user with this email already exists."],
  "password": ["This password is too short."]
}
```

---

#### POST /auth/login/

Authenticate with email and password.

**Request** (public):
```json
{
  "email": "user@example.com",
  "password": "StrongPass123!"
}
```

**Response** (200):
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "timezone": "Asia/Kolkata",
    "work_start": "09:00",
    "work_end": "18:00",
    "date_joined": "2026-10-28T12:34:56Z"
  }
}
```

**Errors** (401):
```json
{
  "detail": "No active account found with the given credentials"
}
```

---

#### POST /auth/token/refresh/

Refresh an expired access token using a refresh token.

**Request** (public):
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response** (200):
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Note**: The old refresh token is blacklisted after use. A new refresh token is returned.

**Errors** (401):
```json
{
  "detail": "Token is invalid or expired"
}
```

---

#### POST /auth/logout/

Logout by blacklisting the refresh token.

**Request** (authenticated):
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (204): No content

**Errors** (400):
```json
{
  "refresh": ["Invalid or expired token."]
}
```

---

#### POST /auth/password/change/

Change the current user's password.

**Request** (authenticated):
```json
{
  "old_password": "OldPass123!",
  "new_password": "NewPass456!"
}
```

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (204): No content

**Errors** (400):
```json
{
  "old_password": ["Old password is incorrect."],
  "new_password": ["This password is too short."]
}
```

---

### User Profile

#### GET /users/me/

Get the current user's profile.

**Request** (authenticated):
- No body

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200):
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe",
  "timezone": "Asia/Kolkata",
  "work_start": "09:00",
  "work_end": "18:00",
  "date_joined": "2026-10-28T12:34:56Z"
}
```

**Errors** (401):
```json
{
  "detail": "Authentication credentials were not provided."
}
```

---

#### PATCH /users/me/

Update the current user's profile (partial update).

**Request** (authenticated):
```json
{
  "name": "Jane Doe",
  "timezone": "America/New_York",
  "work_start": "08:00",
  "work_end": "17:00"
}
```

**Headers**:
```
Authorization: Bearer <access_token>
```

**Fields** (all optional):
- `name` (string): New display name
- `timezone` (string): New timezone (must be valid IANA timezone)
- `work_start` (string): New work start time (HH:MM format)
- `work_end` (string): New work end time (HH:MM format)

**Response** (200):
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "timezone": "America/New_York",
  "work_start": "08:00",
  "work_end": "17:00",
  "date_joined": "2026-10-28T12:34:56Z"
}
```

**Errors** (400):
```json
{
  "timezone": ["Invalid timezone."],
  "non_field_errors": ["work_start must be earlier than work_end."]
}
```

**Note**: Cannot change `email` or `password` here. Use password change endpoint for password.

---

#### DELETE /users/me/

Delete the current user's account and all associated data.

**Request** (authenticated):
```json
{
  "password": "CurrentPass123!"
}
```

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (204): No content

**Errors** (400):
```json
{
  "password": ["Password is incorrect."]
}
```

**Note**: This is irreversible. All user data (tasks, events, etc.) will be cascade-deleted.

---

## Conventions

### Pagination

When endpoints return lists, they use page-based pagination:

**Request**:
```
GET /endpoint/?page=2&page_size=50
```

**Response**:
```json
{
  "count": 150,
  "next": "http://localhost:8000/api/v1/endpoint/?page=3",
  "previous": "http://localhost:8000/api/v1/endpoint/?page=1",
  "results": [...]
}
```

- Default page size: 20 items
- Maximum page size: 100 items
- Use `page_size` query parameter to override (up to 100)

### Time Formats

- All datetimes are in UTC
- Format: ISO-8601 (e.g., `2026-10-28T12:34:56Z`)
- Store and send in UTC, convert to user's timezone for display

### User Isolation

All user-owned data is automatically scoped to the authenticated user:
- Users can only see their own data
- Attempting to access another user's data returns 404
- No user ID is needed in URLs for user-owned resources (e.g., `/users/me/` instead of `/users/1/`)

### Error Handling

- Always check the HTTP status code first
- Parse the response body for field-specific errors
- Display appropriate error messages to the user
- On 401, prompt user to re-authenticate
- On 429 (rate limit), implement exponential backoff

### Rate Limiting

The API has rate limits:
- Anonymous requests: 60 per minute
- Authenticated requests: 600 per minute
- Auth endpoints (register, login): 10 per minute

If rate limited, the response will be:
```json
{
  "detail": "Request was throttled."
}
```

## Interactive Documentation

Swagger UI is available at:
```
http://localhost:8000/api/v1/docs/
```

OpenAPI schema is available at:
```
http://localhost:8000/api/v1/schema/
```

## Example Flutter Integration

### Auth Service

```dart
class AuthService {
  final String baseUrl = 'http://localhost:8000/api/v1';
  String? accessToken;
  String? refreshToken;

  Future<Map<String, dynamic>> register(
    String email,
    String password,
    String name,
  ) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/register/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
        'name': name,
      }),
    );

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body);
      accessToken = data['access'];
      refreshToken = data['refresh'];
      return data['user'];
    } else {
      throw Exception('Registration failed: ${response.body}');
    }
  }

  Future<Map<String, dynamic>> login(
    String email,
    String password,
  ) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/login/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      accessToken = data['access'];
      refreshToken = data['refresh'];
      return data['user'];
    } else {
      throw Exception('Login failed: ${response.body}');
    }
  }

  Future<void> logout() async {
    if (refreshToken == null) return;

    await http.post(
      Uri.parse('$baseUrl/auth/logout/'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $accessToken',
      },
      body: jsonEncode({'refresh': refreshToken}),
    );

    accessToken = null;
    refreshToken = null;
  }

  Future<void> refreshAccessToken() async {
    if (refreshToken == null) throw Exception('No refresh token');

    final response = await http.post(
      Uri.parse('$baseUrl/auth/token/refresh/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh': refreshToken}),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      accessToken = data['access'];
      refreshToken = data['refresh'];
    } else {
      throw Exception('Token refresh failed');
    }
  }

  Map<String, String> get authHeaders {
    if (accessToken == null) throw Exception('Not authenticated');
    return {'Authorization': 'Bearer $accessToken'};
  }
}
```

### API Client

```dart
class ApiClient {
  final AuthService authService;
  final String baseUrl = 'http://localhost:8000/api/v1';

  ApiClient(this.authService);

  Future<Map<String, dynamic>> getUser() async {
    final response = await http.get(
      Uri.parse('$baseUrl/users/me/'),
      headers: authService.authHeaders,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else if (response.statusCode == 401) {
      // Try to refresh token
      await authService.refreshAccessToken();
      // Retry request
      final retryResponse = await http.get(
        Uri.parse('$baseUrl/users/me/'),
        headers: authService.authHeaders,
      );
      if (retryResponse.statusCode == 200) {
        return jsonDecode(retryResponse.body);
      }
      throw Exception('Authentication failed');
    } else {
      throw Exception('Failed to fetch user');
    }
  }

  Future<Map<String, dynamic>> updateUser(Map<String, dynamic> data) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/users/me/'),
      headers: {
        ...authService.authHeaders,
        'Content-Type': 'application/json',
      },
      body: jsonEncode(data),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to update user');
    }
  }
}
```

## Testing

Use the Swagger UI at `/api/v1/docs/` to test endpoints interactively.

For automated testing, use the provided test suite in `apps/accounts/tests/`.

## Support

For questions or issues, refer to:
- Architecture documentation: `docs/ARCHITECTURE.md`
- Django REST Framework docs: https://www.django-rest-framework.org/
- SimpleJWT docs: https://django-rest-framework-simplejwt.readthedocs.io/
