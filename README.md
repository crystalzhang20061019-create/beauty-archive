# Beauty Archive

A private, single user collection for makeup, skincare, fragrance, and personal care. The app uses Django and a relational database. Local development defaults to SQLite so it runs on a Mac without a database server; PostgreSQL can be selected with `DATABASE_URL`.

## Run locally on macOS

From Terminal, run these commands from the project directory:

```bash
cd path/to/彩妆网站
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
python manage.py migrate
python manage.py seed_catalog
python manage.py createsuperuser
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and sign in with the superuser credentials you created. Keep `.env`, `db.sqlite3`, and `media/` private. The SQLite database and uploaded product photos persist across server restarts in this project folder.

## Environment and database

`.env.example` documents the supported settings. Copy it to `.env` and replace `DJANGO_SECRET_KEY` with a long random secret before using the archive beyond local development. `DJANGO_DEBUG=1` is for local use. With `DATABASE_URL` unset, Django uses `db.sqlite3`; set it to a PostgreSQL URL to use PostgreSQL. PostgreSQL requires a running local server and an existing database/user.

The currency service uses historical rates from Frankfurter.app and does not require an API key. If a historical rate cannot be fetched, the product form asks for the converted USD amount and stores that amount and its implied rate as a manual conversion. A rate lookup may return the latest prior business-day rate; the actual date returned by the service is saved and displayed on the product record. USD purchases are stored directly.

## Backups and exports

Statistics and Settings include CSV exports for products, purchases, usage records, and monthly spending, plus a JSON archive export containing item, purchase, usage, wishlist, and setting details. The portable JSON export is not currently an automatic restore/import format. For a complete Django database backup, run:

```bash
python manage.py dumpdata --natural-foreign --natural-primary --indent 2 > beauty-archive-fixture.json
```

Restore into a migrated database with:

```bash
python manage.py loaddata beauty-archive-fixture.json
```

Back up uploaded images separately by copying the `media/` directory. Keep database and image backups in a private location. Never commit `.env`, `db.sqlite3`, exports, or private product photos to source control.

## Useful development commands

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

The first catalog command is safe to repeat. To add another login, use `python manage.py createsuperuser`; there is no public registration page.

## Current scope

Implemented: authenticated dashboard, responsive collection, category-first and brand-first browsing, product and purchase records, repeat physical items, image uploads served behind authentication, status and expiration tracking, usage history, historical currency conversion with manual fallback, spending and usage summaries, search and filters, wishlist with purchase conversion, settings, and CSV/JSON exports.

Cloud deployment preparation: `render.yaml`, `build.sh`, and private Supabase Storage migration commands are included. See [DEPLOYMENT.md](DEPLOYMENT.md) for provider setup and the one-time data/photo migration. No hosting project has been created yet; provider account connection and setup are still required. Refund/return adjustments and a visual/mobile review on multiple real devices are not complete.
