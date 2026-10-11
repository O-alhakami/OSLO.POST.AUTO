# Oslo Post Auto

A FastAPI/Jinja2 dashboard starter for social-account connections, Cloudinary media uploads, post scheduling with Celery/Redis, and Supabase storage.

## Important behavior

- Signup and login use Supabase Auth. The application uses the Supabase service-role client for its existing `social_accounts` and `posts` tables; never expose that key in browser code.
- OAuth authorization-code flows are implemented for Instagram, Facebook, TikTok, X, and LinkedIn. Register each callback URL as `PUBLIC_BASE_URL/oauth/{platform}/callback`. OAuth provider products/scopes and account eligibility must be configured in each provider's developer console. Facebook Page selection and Instagram Business account discovery may need additional provider-specific API calls.
- Provider APIs for publishing are deliberately **mocked**. The worker records a successful simulated result and does not publish content to any social network. Implement the platform publishing API inside `app/tasks.py` before relying on this application to publish.
- A daily Celery Beat job removes published post rows and their Cloudinary assets once they are older than 15 days.
- Tailwind is loaded from its CDN in the templates.

## Existing Supabase table contract

This project does not create or alter database tables. The existing tables need to expose these columns (add/adjust them in your own Supabase project if they do not):

- `users`: Supabase Auth owns credentials. If this application also relies on a public `users` profile table, keep its `id` equal to the Supabase Auth user UUID. This starter does not write to that table.
- `social_accounts`: `id`, `user_id`, `platform`, `account_id`, `account_name`, `access_token`, `refresh_token`, `expires_at`, `created_at`.
- `posts`: `id`, `user_id`, `content`, `media_urls` (text array), `media_public_ids` (JSON/JSONB array), `platforms` (text array), `status`, `scheduled_at`, `published_at`, `created_at`, `error_message`.

The Supabase service-role key must have the required table permissions. RLS policies do not apply to service-role requests; application routes scope user data by the authenticated user's ID.

Social tokens are encrypted at rest with Fernet. Generate the key (and a separate app secret) using:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the generated values in `.env` as `TOKEN_ENCRYPTION_KEY` and `APP_SECRET_KEY`. Keep both secrets backed up and out of source control; losing the encryption key makes stored social tokens unreadable.

## Local setup (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Fill in .env, then run the services in separate terminals:
uvicorn app.main:app --reload
celery -A app.tasks.celery_app worker --loglevel=info --pool=solo
celery -A app.tasks.celery_app beat --loglevel=info
```

Redis must be reachable at `REDIS_URL`. Configure your Supabase, Cloudinary, and OAuth credentials before using the relevant features. Set `SECURE_COOKIES=true` behind HTTPS in production. `/ping` returns `{"status":"ok"}`.

## Render deployment notes

This project is ready for Render with a `render.yaml` file and a production-safe Gunicorn start command. The app exposes `/ping` for health checks.

Required environment variables in Render:

```env
APP_SECRET_KEY=...
TOKEN_ENCRYPTION_KEY=...
PUBLIC_BASE_URL=https://your-render-app.onrender.com
SECURE_COOKIES=true
REDIS_URL=redis://:password@host:port/0
SUPABASE_URL=https://xyz.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
MAX_UPLOAD_BYTES=104857600
```

If you prefer a single Cloudinary URL instead of individual variables, the app accepts `CLOUDINARY_URL` in `cloudinary://api_key:api_secret@cloud_name` format. Invalid values are ignored safely so the app can still start.

## GitHub

After reviewing the project and adding valid GitHub credentials/permissions, initialize and push with the requested remote:

```powershell
git init
git branch -M main
git add .
git commit -m "Initial commit: Project structure and core backend logic"
git remote add origin https://github.com/O-alhakami/OSLO.POST.AUTO.git
git push -u origin main
```
