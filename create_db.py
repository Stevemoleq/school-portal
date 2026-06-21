"""Create the project database. Reads credentials from the environment.

This script is intentionally NOT in version control (see .gitignore). It
should only be run locally during initial setup. Production database
creation is handled by the platform (e.g. Render) — never run this in
production.

Required env vars:
    DB_SUPERUSER_PASSWORD   Postgres superuser password
    DB_HOST                 (default: localhost)
    DB_PORT                 (default: 5432)
    DB_NAME                 (default: school_portal)
"""
import os
import sys

import psycopg2
from psycopg2 import sql
from psycopg2.errors import DuplicateDatabase


def main():
    password = os.environ.get("DB_SUPERUSER_PASSWORD")
    if not password:
        print(
            "ERROR: DB_SUPERUSER_PASSWORD environment variable is required.",
            file=sys.stderr,
        )
        sys.exit(1)

    dbname = os.environ.get("DB_NAME", "school_portal")
    user = os.environ.get("DB_SUPERUSER_USER", "postgres")
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")

    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=user,
            password=password,
            host=host,
            port=port,
        )
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
        print(f"Database '{dbname}' created successfully!")
        cursor.close()
        conn.close()
    except DuplicateDatabase:
        print(f"Database '{dbname}' already exists!")
    except psycopg2.OperationalError as e:
        print(f"Could not connect to PostgreSQL at {host}:{port}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
