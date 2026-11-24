# Calibre

A calendar-first productivity app for IIT Bombay students.

- **Backend:** Django + Django REST Framework, in `Calibre_backend/`
- **App:** Flutter desktop app for macOS and Windows, in `frontend/`
- **Utils:** timetable Excel to JSON converter, in `Utils/`

The app talks to the backend at `http://127.0.0.1:8000/api/v1`. Start the backend first, then the app.

## What to install

| Tool | Needed for | Mac | Windows |
|---|---|---|---|
| Python 3.12 or newer | backend | python.org or `brew install python` | python.org (tick "Add Python to PATH") |
| Flutter SDK | app | flutter.dev | flutter.dev |
| Xcode and CocoaPods | Mac app only | `xcode-select --install`, `brew install cocoapods`, and Xcode from the App Store | not needed |
| Visual Studio with "Desktop development with C++" | Windows app only | not needed | yes |

Run `flutter doctor` and fix anything it marks with an X for the platform you want.

## 1. Backend

Open a terminal in the `Calibre_backend/` folder.

**Mac**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell refuses to run the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

### Settings file

Make sure `.env` exists in `Calibre_backend/` with at least:

```
SECRET_KEY=any-long-random-string
MOODLE_TOKEN_KEY=<a Fernet key>
```

Make a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Start the backend

```bash
python manage.py migrate
python manage.py runserver
```

You should see "Starting development server at http://127.0.0.1:8000/". To check it, open `http://127.0.0.1:8000/api/v1/docs/` in a browser.

Use `python3` in place of `python` on Mac if `python` is not found.

### Load the department timetable (needed for "Add courses")

In a second terminal, in `Calibre_backend/` with the venv active:

```bash
python manage.py import_timetable combined_timetable.json
```

### Department and Institute events

In a third terminal, in `Calibre_backend/` with the venv active:

```bash
python manage.py runscheduler
```

- On first start, if there are no external events yet, it imports the CSE calendar and the full Institute list.
- Then it syncs the CSE feed and the light Institute feed every hour, and the full Institute list every day at 03:30.

## 2. App

Open a terminal in the `frontend/` folder.

**Mac**

```bash
flutter pub get
flutter run -d macos
```

**Windows**

```powershell
flutter pub get
flutter run -d windows
```

## Using the app

1. Create an account on the first screen, then sign in.
2. Use **New event** to add events, with an optional repeat.
3. Use **Add courses** to pick a department and add lectures as weekly events.
4. Use **Connect Moodle** and then **Sync Moodle** to bring in deadlines.
5. The Department and Institute tabs show shared campus events once the scheduler has run.

## Code organization

Calibre has three parts that talk to each other in one direction: the Flutter app calls the Django REST API, and the API reads and writes the database.

```
Calibre_Submission_Minimum_Needed_Files/
  Calibre_backend/     Django REST API, the database and the feed scheduler
  frontend/            Flutter app for macOS and Windows
  Utils/               one-off script that turns the ASC timetable Excel files into JSON
```

### How the backend is organised

The backend is a Django project called `config` with five apps in `apps/`. Each app has the same layers, so a file name tells you its job:

| Layer | What it does |
|---|---|
| `models.py` | Database tables. |
| `serializers.py` | Checks incoming JSON and shapes outgoing JSON. |
| `views.py` | The API endpoints. They stay thin and call the services. |
| `services.py` | The business logic, kept apart from the web layer. |
| `urls.py` | Maps URLs to views. |
| `filters.py` | Query filters for list endpoints. |
| `admin.py` | Django admin screens. |
| `migrations/` | Generated database changes. Do not edit by hand. |

Every request needs a login token (JWT) except sign-up, sign-in and the health check. Personal data (events, tasks, categories, routines) belongs to one user and is always filtered by the logged-in user. Campus events and the timetable are shared by everyone.

### Backend: top level

| File | Role |
|---|---|
| `manage.py` | Entry point for every Django command (`runserver`, `migrate`, `runscheduler`). |
| `requirements.txt` | The Python packages to install. |
| `.env` | Secrets and settings: `SECRET_KEY` and `MOODLE_TOKEN_KEY`. Never share it. |
| `db.sqlite3` | The SQLite database file, with the data from development. |
| `combined_timetable.json` | All department timetables in one JSON file, loaded by `import_timetable`. |

### Backend: `config/` (project settings)

| File | Role |
|---|---|
| `settings.py` | All settings: installed apps, JWT lifetimes, rate limits, CORS, database, Moodle options. |
| `urls.py` | The root URL list. Mounts each app under `/api/v1/` and the API docs. |
| `wsgi.py` | Entry point for a production web server. |
| `asgi.py` | Entry point for an async web server. |
| `__init__.py` | Marks the folder as a Python package. |

### Backend: `apps/accounts/` (users and sign-in)

| File | Role |
|---|---|
| `models.py` | The custom `User` (email login, name, timezone) and its manager. |
| `serializers.py` | Validation for register, login, profile update, password change, account delete and logout. |
| `services.py` | `register_user` creates the user and seeds the default categories. |
| `views.py` | Endpoints for register, login, token refresh, logout, change password and `users/me`. |
| `urls.py` | Routes under `auth/` and `users/me/`. |
| `admin.py` | Admin screen for users. |
| `apps.py` | App registration. |
| `migrations/0001`, `0002` | Create and adjust the user table. |

### Backend: `apps/common/` (shared building blocks)

| File | Role |
|---|---|
| `models.py` | Base classes `TimeStampedModel` (created and updated times) and `OwnedModel` (belongs to one user), and the `Category` table. |
| `mixins.py` | `OwnedQuerysetMixin` limits every query to the logged-in user and sets the owner on create. |
| `timeutils.py` | Helpers for "today", a day's start and end, and local time to UTC in the user's timezone. |
| `services.py` | `seed_default_categories` gives each new user the Personal and Academics categories. |
| `serializers.py` | JSON shape for categories. |
| `views.py` | The `health/` check and the category endpoints. |
| `urls.py` | Routes for the above. |
| `admin.py` | Admin screen for categories. |
| `management/commands/seed_default_categories.py` | Command that adds the default categories to existing users. |
| `migrations/0001_initial.py` | Creates the category table. |

### Backend: `apps/tasks/` (deadlines)

| File | Role |
|---|---|
| `models.py` | The `Task` table: title, due time, status, priority and source. |
| `serializers.py` | Validation and JSON shape for tasks. |
| `services.py` | Task rules: overdue, urgent, complete and reopen, due today, the priority matrix, and "what to do now". |
| `views.py` | The task endpoints, including the complete and reopen actions. |
| `filters.py` | Filters for the task list. |
| `urls.py` | Registers the `tasks/` routes. |
| `admin.py` | Admin screen for tasks. |
| `tests.py` | Placeholder for tests. |
| `migrations/0001_initial.py` | Creates the task table. |

### Backend: `apps/planner/` (events, timetable and campus feeds)

| File | Role |
|---|---|
| `models.py` | `Event` (a calendar entry, with a series id for repeats), `ExternalEvent` (shared campus events), `TimetableEntry` (department timetable), `DeletedEvent`, `CourseSchedule`, `Routine` and `RoutineCheckin`. |
| `serializers.py` | Validation and JSON for events, routines, the agenda, free-slot queries, campus events and timetable imports. |
| `services.py` | Calendar logic: agenda for a date range, free-time slots, busy-interval merging, routine dates and task suggestions. |
| `views.py` | Endpoints for events (including repeats), routines, `calendar/agenda/`, `free-slots/`, `external-events/` (with the Add action) and `timetable/`. |
| `filters.py` | Filters for the event list. |
| `pagination.py` | A larger page size for calendar lists. |
| `urls.py` | Registers events, routines, external-events and timetable routes. |
| `admin.py` | Admin screens for events, routines and timetable entries. |
| `management/commands/runscheduler.py` | Long-running process: first import if the table is empty, then hourly and daily syncs. |
| `management/commands/sync_cse_feed.py` | Downloads the CSE department calendar and saves the last 3 months. |
| `management/commands/sync_insti_feed.py` | Downloads Institute events from the Gymkhana API and saves them. |
| `management/commands/import_timetable.py` | Loads `combined_timetable.json` into the timetable table. |
| `migrations/0001` to `0004` | Create the event, campus event, course schedule and timetable tables. |

### Backend: `apps/integrations/` (Moodle)

| File | Role |
|---|---|
| `models.py` | `MoodleConnection`: the encrypted token and the sync status for each user. |
| `crypto.py` | Encrypts and decrypts the Moodle token with Fernet. |
| `moodle_client.py` | Talks to Moodle: reads the sign-in token, gets site info, fetches calendar events and courses. |
| `mapping.py` | Cleans Moodle events into Calibre's event format. |
| `services.py` | Connect, sync, disconnect and status. Turns deadlines into tasks and the rest into events, and keeps the student's edits. |
| `exceptions.py` | Moodle error types: bad token, API error, unavailable, re-sign-in needed. |
| `serializers.py` | JSON shapes for connect, status and sync results. |
| `views.py` | Endpoints `moodle/connect/`, `status/`, `sync/` and disconnect. Maps Moodle errors to HTTP codes. |
| `urls.py` | Routes for the above. |
| `admin.py` | Admin screen for connections. |
| `tests.py` | Placeholder for tests. |
| `migrations/0001_initial.py` | Creates the Moodle connection table. |

### Utils

| File | Role |
|---|---|
| `Utils/timetable_to_json.py` | Reads the ASC portal Excel timetables (several courses can share a cell) and writes them out as JSON. |

### How the Flutter app is organised

All app code is in `frontend/lib/`. It is split into layers, and each layer only uses the ones below it:

```
screens/   whole pages
widgets/   reusable pieces used by the pages
state/     the data the screens show, with change notifications
services/  calls to the backend API
models/    plain data classes
utils/     small helpers
```

| File | Role |
|---|---|
| `main.dart` | Starts the app and creates the sign-in state. |
| `config.dart` | The backend address (`baseUrl`). |

**`models/`**

| File | Role |
|---|---|
| `user.dart` | The signed-in user. |
| `calendar_event.dart` | One calendar item, an event or a deadline, and the repeat rule. |

**`services/`**

| File | Role |
|---|---|
| `auth_service.dart` | All API calls: sign-up, sign-in, refreshing tokens and retrying, plus generic GET, POST, PATCH and DELETE. |
| `moodle_service.dart` | Moodle sign-in flow, connect, status and sync. |
| `token_storage.dart` | Saves the login tokens in secure storage. |
| `api_exception.dart` | The error type for failed API calls. |

**`state/`**

| File | Role |
|---|---|
| `auth_state.dart` | Whether the user is checking, signed out or signed in, and `AuthScope` to read it anywhere. |
| `event_state.dart` | Holds events and tasks for the visible dates and for today and tomorrow, and loads, adds, edits and deletes them. |

**`screens/`**

| File | Role |
|---|---|
| `auth_gate.dart` | Shows the loading, sign-in or main screen depending on the sign-in state. |
| `auth_screen.dart` | The sign-in and create-account form. |
| `app_shell.dart` | The main layout: side menu, top bar and the chosen Month, Week or Day view. Handles date navigation. |
| `week_screen.dart` | The Week view page. |
| `day_screen.dart` | The Day view page. |
| `month_screen.dart` | The Month view page. |

**`widgets/`**

| File | Role |
|---|---|
| `side_menu.dart` | The left sidebar: New event, tabs, Today card, Add courses and Moodle buttons, and the profile menu. |
| `today_card.dart` | The sidebar card with what is on now, next up, due today and tomorrow. |
| `top_bar.dart` | Date title, previous and next, Today button and the Month, Week and Day switch. |
| `week_grid.dart` | The seven-day grid, with events placed by time. |
| `hour_grid.dart` | The hour rows and the current-time line, shared by the Week and Day views. |
| `week_day_cards.dart` | The row of day labels above the week grid. |
| `event_tile.dart` | One event block, with its colour and title. |
| `day_header.dart` | An older day heading. It is not used. |
| `add_event_dialog.dart` | The New event form, with the repeat options. |
| `add_courses_dialog.dart` | The department and course picker for the timetable. |

**`utils/`**

| File | Role |
|---|---|
| `date_utils.dart` | Date helpers: start of week, same day, labels and formatting. |
| `event_layout.dart` | Works out side-by-side columns for overlapping events. |
| `event_palette.dart` | The event colours and the Personal and Academic calendars. |

**Other frontend files**

| File | Role |
|---|---|
| `pubspec.yaml` | Package list and the Pacifico font. |
| `pubspec.lock` | The exact package versions in use. |
| `analysis_options.yaml` | Code style checks. |
| `assets/fonts/` | The font files. |
| `macos/`, `windows/`, `linux/`, `web/` | Generated by `flutter create`. They hold the platform wrappers and are rarely edited by hand. |
| `README.md` | The default Flutter text. |
| `.flutter-plugins-dependencies` | Generated by Flutter. Not edited. |

### How a request flows through the code

1. A screen or widget asks `EventState` or `MoodleService` for data.
2. `AuthService` sends the HTTP request with the login token. If the token has expired, it refreshes the token and retries once.
3. Django receives it at `/api/v1/...`. The app's `urls.py` sends it to a view.
4. The view validates the input with a serializer and calls a function in `services.py`.
5. The service reads or writes the models, which are saved in the database.
6. The response goes back, `EventState` updates, and the screens redraw.

Separately, `runscheduler` fills the shared campus events table on a timer, and `import_timetable` fills the timetable table once.
