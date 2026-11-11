#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."

until pg_isready \
    -h postgres \
    -p 5432 \
    -U "$POSTGRES_USER"
do
    sleep 2
done

echo "PostgreSQL is ready"

echo "Running database migrations..."

# migrate db by alembic using upgrade head
alembic -c alembic-corpus.ini upgrade head
alembic -c alembic-users.ini upgrade head

echo "Starting FastAPI..."

exec "$@"