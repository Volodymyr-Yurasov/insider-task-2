#!/bin/sh
set -e

# Only the web container runs migrations; workers and one-off commands skip it.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
fi

exec "$@"
