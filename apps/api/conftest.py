"""Root conftest: pin test settings before any `app` module is imported.

Tests need a reachable Postgres. Default is a `village_test` database on the local
docker-compose server; CI overrides DATABASE_URL to its service container.
"""

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://village:village@localhost:5432/village_test"
)
os.environ["APP_ENV"] = "development"
os.environ["DEV_LOGIN_ENABLED"] = "true"
os.environ["CRON_SECRET"] = "test-cron-secret"
os.environ["SESSION_SECRET"] = "test-session-secret"
