# Location Popularity Map — REST API

A Django REST Framework API where users add places worth visiting, review and rate them,
like or dislike reviews, and browse the most popular places. Rating and popularity are
computed with the Django ORM on every query and never stored.

**Stack:** Python 3.13 · Django 6.1 · DRF · django-filter · PostgreSQL 17 · Redis 7 ·
Celery · pandas · drf-spectacular · Docker Compose · uv · pytest

---

## Quick start

```bash
cp .env.example .env          # then set DJANGO_SECRET_KEY
docker compose up -d --build
```

### Demo data

On every start, the `web` container runs `python manage.py seed` after migrations. The
command adds:
- an admin account
- 5 users
- 4 categories
- 8 Kyiv locations
- 21 reviews and 12 votes

| Account | Password |
|---|---|
| `admin` (superuser) | `Admin-pass-123` (`SEED_ADMIN_PASSWORD`) |
| `olena`, `taras`, `iryna`, `dmytro`, `sofia` | `Demo-pass-123` (`SEED_USER_PASSWORD`) |

Running it again is safe:
- **Nothing is duplicated or overwritten.** Each record is looked up by its natural key and
  created only if it's missing. A changed password or a soft-deleted demo location stays
  as it is.
- **Containers starting at the same time** can't both seed: a PostgreSQL advisory lock lets
  only one run at a time.
- **No emails are sent.** Reviews and votes are bulk-inserted, which skips the
  notification signal.

Set `SEED_DATA=0` in `.env` to turn seeding off.

| URL | What |
|---|---|
| http://localhost:8000/api/docs/ | Swagger UI (OpenAPI schema at `/api/schema/`) |
| http://localhost:8000/admin/ | Django admin |
| http://localhost:8025/ | Mailpit: every email the app sends (password reset, review notifications) |

Services:
- `web`: gunicorn; runs migrations and the demo seed when it starts
- `worker`: Celery
- `db`, `redis`, `mailpit`

### Email in development (Mailpit)

[Mailpit](https://mailpit.axllent.org/) is a fake mail server for development. It accepts every
email the app sends, whatever the recipient address, and keeps it instead of delivering it.
Nothing leaves your machine, so the seeded `@example.com` users can "receive" mail.

It isn't a Python dependency. It runs as its own container, from the `axllent/mailpit`
Docker image declared in `docker-compose.yml`. Django talks to it with its standard SMTP
backend, like any other mail server.

Mailpit listens on two ports:

| Port | Protocol | Use it to |
|---|---|---|
| **8025** | HTTP | **Read mail.** Open http://localhost:8025 for the inbox, or use the REST API (below). |
| **1025** | SMTP | **Send mail.** The app delivers here: `EMAIL_HOST=mailpit`, `EMAIL_PORT=1025` inside Docker. A Django process running on the host uses `EMAIL_HOST=localhost`. |

Reading mail from a script or test, for example to grab a password-reset link:

```bash
curl http://localhost:8025/api/v1/messages              # list (newest first)
curl http://localhost:8025/api/v1/message/<ID>          # one message: headers, text, HTML
curl -X DELETE http://localhost:8025/api/v1/messages    # empty the inbox
```

What sends email:
- **Password-reset requests**
- **New reviews:** to the location's author and its subscribers

Seeding, votes and review edits send nothing. Email always goes through the Celery `worker`,
so if mail doesn't show up, check `docker compose logs worker`.

Mailpit keeps mail **in memory**, so restarting its container empties the inbox. All ports are
bound to `127.0.0.1`: reachable from your machine, not from the network.

**Sending real email:** remove the `mailpit` service and point the same settings at a real
SMTP provider. No code changes are needed:

```env
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=Location Map <no-reply@your-domain.com>
SITE_URL=https://api.your-domain.com
```

The sending domain also needs SPF, DKIM and DMARC DNS records, or mail will land in spam.

### Tests

```bash
docker compose run --rm -e RUN_MIGRATIONS=0 -e SEED_DATA=0 web pytest
```

Tests run against real PostgreSQL. Celery tasks run inline (eager mode), and emails go to
Django's in-memory outbox.

### Local development without Docker for Python

```bash
uv sync                                  # creates .venv from uv.lock
docker compose up -d db redis mailpit    # infrastructure only; ports published on 127.0.0.1
# in .env, replace the Docker hostnames with localhost:
#   DATABASE_URL=postgres://locmap:locmap@localhost:5432/locmap
#   REDIS_CACHE_URL=redis://localhost:6379/0   CELERY_BROKER_URL=redis://localhost:6379/1
#   EMAIL_HOST=localhost                        (port 1025 stays the same)
uv run python manage.py migrate
uv run python manage.py runserver
uv run ruff check . && uv run ruff format --check .
```

---

## Authentication (session + cookies, no JWT)

The API uses Django's own `login()` and `logout()` with DRF `SessionAuthentication`. A client
does the following:

1. `GET /api/auth/csrf/` sets the `csrftoken` cookie.
2. Every unsafe request sends the token back in the `X-CSRFToken` header. The browser sends
   the cookies automatically.
3. `POST /api/auth/login/` sets the `sessionid` cookie (`HttpOnly`, `SameSite=Lax`, and
   `Secure` in prod).

By default DRF checks CSRF only for authenticated users. Register, login and password reset
are anonymous, so they are wrapped in `csrf_protect` explicitly to block login CSRF. These
endpoints are also rate limited through the `auth` throttle scope.

**Password reset:** `POST /api/auth/password-reset/ {email}` always returns `202`, so it
can't be used to find out which emails have accounts. Where the emailed link points depends
on `FRONTEND_PASSWORD_RESET_URL`:

- **Empty (default):** `SITE_URL/accounts/reset/<uid>/<token>/`, a page served by this
  backend using Django's `PasswordResetConfirmView`. It works without any frontend: open the
  link, choose a password, done.
- **Set to an SPA page:** `FRONTEND_PASSWORD_RESET_URL?uid=…&token=…`. The SPA then calls
  `POST /api/auth/password-reset/confirm/ {uid, token, new_password}`.

Both use Django's `default_token_generator`, so tokens expire (`PASSWORD_RESET_TIMEOUT`) and
work only once. Passwords are checked by `AUTH_PASSWORD_VALIDATORS` in both cases.

---

## API overview

| Endpoint | Methods | Access |
|---|---|---|
| `/api/auth/csrf/` | GET | anyone |
| `/api/auth/register/` · `login/` · `logout/` · `me/` | POST · POST · POST · GET | anyone / logged in |
| `/api/auth/password-reset/` · `password-reset/confirm/` | POST | anyone |
| `/api/categories/` · `/api/categories/{id}/` | CRUD | read: anyone (active only); write: admin |
| `/api/locations/` · `/api/locations/{id}/` | CRUD | read: anyone; create: logged in; edit/delete: author or admin |
| `/api/locations/export/?file_format=csv\|json` | GET | anyone |
| `/api/locations/{id}/reviews/` | GET, POST | read: anyone; post: logged in |
| `/api/reviews/{id}/` | GET, PUT/PATCH, DELETE | read: anyone; edit/delete: author or admin |
| `/api/reviews/{id}/vote/` | PUT `{"value": 1 \| -1}`, DELETE | logged in |
| `/api/locations/{id}/subscribe/` | POST, DELETE | logged in |
| `/api/subscriptions/` | GET (current user's subscriptions) | logged in |

### Location list: search, filters, ordering, pagination

| Query param | Effect |
|---|---|
| `search` | matches `name` and `description` (case-insensitive) |
| `category`, `category_slug` | filter by category id or slug |
| `author` | filter by author id |
| `min_rating`, `max_rating` | filter on the computed rating (unrated locations never match) |
| `min_lat`, `max_lat`, `min_lng`, `max_lng` | map viewport (bounding box) |
| `ordering` | `created_at`, `rating`, `popularity`; prefix `-` for descending. Default `-created_at`. Locations with no rating always sort last. |
| `page`, `page_size` | page-number pagination; 20 per page by default, at most 100 |

Export uses the same filters, search and ordering, and returns the whole result set
without pagination.

### Example response

```json
{
  "id": 1,
  "name": "Hydropark",
  "description": "Island park",
  "category": 1,
  "category_detail": {"id": 1, "name": "Parks", "slug": "parks"},
  "address": "Kyiv",
  "latitude": "50.445000",
  "longitude": "30.577000",
  "author": {"id": 2, "username": "owner"},
  "rating": 4.0,
  "reviews_count": 1,
  "views_7d": 1,
  "popularity": 3.119,
  "created_at": "2026-11-24T09:34:42Z",
  "updated_at": "2026-11-24T09:34:42Z"
}
```

---

## Design decisions

### Rating and popularity (computed, never stored)

`LocationQuerySet.with_stats()` is the only place these numbers are defined. The list,
detail, filters, ordering and export all use it.

```
rating        = AVG(review.rating)                            -- NULL when there are no reviews
reviews_count = COUNT(reviews)
views_7d      = COUNT(views WHERE viewed_at >= now() - 7 days)

popularity    = COALESCE(rating, 0) * LN(1 + reviews_count)
              + 0.5 * LN(1 + views_7d)
```

- **Rating times log of review count.** A place rated 5★ by 50 people ranks above one rated
  5★ by a single person. The logarithm keeps sheer volume from dominating.
- **Views count less.** Views carry a smaller weight and are also logarithmic, so recent
  traffic can lift a place without letting someone refreshing the page push it to the top.
- **Each aggregate is a separate correlated subquery,** not a `JOIN`. Joining reviews and
  views together would multiply rows: 3 reviews × 5 views = 15 rows. A test guards against
  that.

### Counting views

`register_view()` runs when someone opens a location's detail page:

- It calls `cache.add("location-view:{location}:{viewer}", ttl=1h)`, which is Redis
  `SET NX`, so the check is atomic and concurrent requests can't count twice.
- Only if that succeeds does it store a `LocationView` row.
- The viewer is the user id for logged-in users. For anonymous users it is a hash of the IP,
  so raw IPs never sit in Redis.

Views are stored as individual events rather than as a counter, which makes the rolling
7-day window exact. The `(location, viewed_at)` index keeps counting them fast.

### Caching the location list (Redis)

The cached list response is keyed by
`locations:list:v{version}:{hash of query params}` and expires after 5 minutes
(`LOCATION_LIST_CACHE_TTL`).

- **Invalidation increments the version number.** All cached entries become unreachable in
  one step, without scanning keys.
- **What triggers it:**
  - Saving or deleting a location, including soft delete. Bulk soft delete and restore in the
    admin are covered too, because they go through `queryset.update()` and that is hooked as
    well.
  - Saving or deleting a review.
  - Saving or deleting a category.
- **Timing:** the version is bumped in `transaction.on_commit`, so a concurrent request can
  never cache data from before the commit.
- **Why not `cache_page`:** it varies on `Cookie`, so with session auth every visitor would
  get a private copy. The list response contains nothing user-specific, so one shared entry
  per query is safe.
- **Staleness:** `views_7d` in the list can lag by up to the TTL. That is deliberate: views
  don't clear the cache, otherwise every page view would wipe it.

### Soft delete

`SoftDeleteModel` (in `apps/core`) sets `deleted_at` instead of removing the row:

- `objects` returns only live locations; `all_objects` returns everything.
- Related objects (for example `review.location`) are loaded through the unfiltered base
  manager, so existing reviews still point at their location after it's deleted.
- The admin shows deleted locations and has *Soft delete* and *Restore* actions.
- `queryset.update()` skips `auto_now`, so soft delete sets `updated_at` explicitly.

### Reviews and votes

- **One review per user per location.** This is enforced by a `UniqueConstraint`. The
  serializer checks first and returns `400`, and if two requests arrive at once the
  database constraint plus an `IntegrityError` handler still return `400`.
- **Rating 1–5** is checked by the serializer and by a database `CheckConstraint`.
- **No self-reviews and no voting on your own review.**
- **One vote per user per review, changed in place.** `PUT /vote/` creates the vote (`201`)
  or updates its value (`200`); sending the same value again changes nothing. The vote's
  `created_at` is when the user first voted and `updated_at` is when they last changed it.
  `DELETE` retracts the vote.

### Categories

Categories are a list that only admins change. They are a table, not a code enum, so changes
don't need a deploy. A category that locations use is protected (`on_delete=PROTECT`):
deleting it returns `409`, and the admin should set `is_active=false` instead. Inactive
categories are hidden from non-admins and can't be chosen for new locations.

### Email notifications (bonus)

When a review is created, a signal runs `transaction.on_commit` and then
`notify_new_review.delay()`, which is a Celery task with retry and backoff.

- **Recipients:** the location's author, plus everyone subscribed to the location.
  Duplicates are removed and the reviewer is excluded.
- **One message per recipient,** so recipients don't see each other's addresses. All
  messages go out over a single mail connection.
- **Edits don't notify:** editing a review sends nothing.

The password reset email goes through Celery as well.

### Timestamps

`TimeStampedModel` adds `created_at` and `updated_at` to Category, Location, Review,
ReviewVote and LocationSubscription. `User` has Django's `date_joined` plus an extra
`updated_at`. `LocationView` is a log entry that never changes, so it has only `viewed_at`.

---

## Project layout

```
config/                 settings (base / dev / test / prod), urls, celery, wsgi/asgi
apps/
  core/                 base models (timestamps, soft delete), permissions, pagination,
                        versioned list cache, ordering filter, email helpers
  users/                custom User, session auth, password reset
  locations/            Category, Location, LocationView, stats querysets, filters, export
  reviews/              Review, ReviewVote
  notifications/        LocationSubscription, new-review emails
templates/emails/       plain-text + HTML email templates
docker/entrypoint.sh    migrations, collectstatic and demo seed for the web container
apps/core/management/commands/seed.py   idempotent demo data
```

Each app splits its code the same way: `models` → `querysets` (reads) → `services` (writes
and business rules) → `serializers` → `views` → `urls`, with `signals`, `tasks`, `admin`
and `tests/` alongside.

## Configuration

All settings come from environment variables; see [`.env.example`](.env.example). Use
`config.settings.prod` in production: secure cookies, HSTS, SSL redirect, and JSON-only
renderers.
