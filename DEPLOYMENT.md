# Cloud deployment (free plans)

The app is designed for a Render free web service, Supabase PostgreSQL, and a **private** Supabase Storage bucket. The SQLite database and `media/` folder stay local until you explicitly run the migration commands below. Neither is part of the GitHub repository.

## Provider setup

1. Create a Supabase project on its free plan. Save the database password privately. Create a private Storage bucket named `beauty-archive-private` (do not make it public).
2. Copy the Supabase **Session pooler** PostgreSQL URI into Render as `DATABASE_URL`. Add the Supabase S3 endpoint, region, and server-side S3 access key/secret to the Render service environment variables. Never put these in GitHub.
3. Connect the public `crystalzhang20061019-create/beauty-archive` repository to Render using `render.yaml`. Keep the service on the Free plan. Render may ask to enter the `sync: false` values during setup. Do not select a paid database or instance.
4. Render's first deploy runs database migrations. Keep `autoDeploy: false`; deploy the reviewed commit manually from the Render dashboard.

## Move the current archive

Run these commands from this Mac in the project folder, with the virtual environment activated. Add the Supabase S3 settings to the local `.env` file first (copy the names from `.env.example`). The database URL is not needed for these upload commands: they read the existing local SQLite database and write migration files/photos only to the private Supabase bucket.

```bash
source .venv/bin/activate
python manage.py upload_media_to_cloud
python manage.py stage_cloud_data
```

After the first Render deploy succeeds, copy the Supabase **Session pooler** URI. From this Mac, connect Django to the cloud database for the migration only. In Terminal:

```bash
export DATABASE_URL='PASTE_THE_SUPABASE_SESSION_POOLER_URI_HERE'
python manage.py migrate --noinput
python manage.py import_cloud_data
python manage.py changepassword YOUR_EXISTING_USERNAME
unset DATABASE_URL
```

Use the username from your local sign-in. The local password hash is deliberately not copied; `changepassword` lets you choose a fresh cloud password in Terminal. The password is entered interactively and is not saved in the shell command. Sign in at the Render URL and check the product count and photos before treating the migration as finished.

## Private data and backups

`stage_cloud_data` writes a one-time JSON fixture to the **private** Supabase bucket at `private-migrations/archive-data.json`. Keep the bucket private. The Git ignore rules exclude the local SQLite database, media, fixture, and environment files. Preserve the Mac project folder as the original backup until the cloud copy is verified. Supabase Free can pause inactive projects; the app sleeps after 15 minutes without visits on Render Free and needs about a minute to wake up. Free Render services have no Shell, which is why the database migration is run securely from this Mac. Paid plans are not configured here.

## Local run

The cloud settings are optional locally; without `USE_SUPABASE_STORAGE=1`, images continue to use local `media/` and SQLite:

```bash
source .venv/bin/activate
python manage.py runserver
```
