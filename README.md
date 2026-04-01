# 🧠 Document Intelligence API

> **Upload a document. Get AI-powered insights. Ask anything about it.**

A production-grade, multi-tenant REST API that transforms raw PDF and image documents into structured intelligence — summaries, named entities, and conversational Q&A — powered by Groq's Llama model, processed asynchronously via Celery, and deployed on Railway.

Built as a portfolio project targeting **FAANG Backend SWE roles**. Every architectural decision was made the way it would be made at scale.

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.0-green?style=flat-square&logo=django)](https://djangoproject.com)
[![Celery](https://img.shields.io/badge/Celery-5.3-brightgreen?style=flat-square)](https://docs.celeryq.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?style=flat-square&logo=postgresql)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7.0-red?style=flat-square&logo=redis)](https://redis.io)
[![Tests](https://img.shields.io/badge/Tests-60%2B%20passing-success?style=flat-square)](./tests)
[![Coverage](https://img.shields.io/badge/Coverage-80%25%2B-success?style=flat-square)](./htmlcov)
[![Deploy](https://img.shields.io/badge/Deployed-Railway-purple?style=flat-square)](https://railway.app)

---

## 🤔 Problem Statement — Why Did I Build This?

Tools like ChatGPT let you upload a file and ask questions. That works great for **one person, one file, one time**.

But what if you need to:
- Process **thousands of documents** automatically in the background?
- Give **hundreds of users** their own private document workspace?
- Let **any application** (mobile app, web app, internal tool) integrate document intelligence via a clean API?
- Get **notified via webhook** when processing completes — no polling required?
- **Retry failed processing** without re-uploading the file?

That's a completely different engineering problem. You're not *using* AI — you're **building infrastructure around AI**.

This project is the answer to that problem. It's the difference between using a calculator and building a calculator API that thousands of apps can call.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Any App)                         │
│              Mobile App / Web App / Postman / curl              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS + JWT Bearer Token
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DJANGO + GUNICORN                            │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  Auth API   │  │ Document API │  │      Health Check      │ │
│  │  /auth/*    │  │ /documents/* │  │      /api/health/      │ │
│  └─────────────┘  └──────┬───────┘  └────────────────────────┘ │
│                          │                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Django Middleware Stack                        │ │
│  │  CORS → Security → Auth → RateLimit → CustomException      │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐
│  PostgreSQL  │  │    Redis     │  │       Cloudinary         │
│              │  │              │  │                          │
│  Users       │  │  Task Queue  │  │  PDF / Image Storage     │
│  Documents   │  │  Rate Limit  │  │  (CDN Delivered)         │
│  QA History  │  │  Cache       │  │                          │
│  Task Results│  │              │  └──────────────────────────┘
└──────────────┘  └──────┬───────┘
                         │ Task picked up
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CELERY WORKER                                │
│                  (Separate Process)                             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              process_document Task                       │   │
│  │                                                         │   │
│  │  1. Download file from Cloudinary → temp file           │   │
│  │  2. Extract text (pypdf, layout mode)                   │   │
│  │  3. Clean text (remove line numbers, garbage chars)     │   │
│  │  4. Truncate to 12k chars (context window safe)         │   │
│  │  5. POST to Groq API → Summary (3-5 bullets)            │   │
│  │  6. POST to Groq API → Entities (people/orgs/dates)     │   │
│  │  7. Update DB: status=COMPLETED                         │   │
│  │  8. Fire webhook (if configured)                        │   │
│  │                                                         │   │
│  │  On failure: Exponential backoff retry (3x)             │   │
│  │  On timeout: SoftTimeLimitExceeded → clean exit         │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Webhook (if configured)
                           ▼
                ┌─────────────────────┐
                │   Your Server URL   │
                │  POST with payload  │
                │  X-Webhook-Signature│
                │  (HMAC-SHA256)      │
                └─────────────────────┘
```

### Document Lifecycle

```
Upload → PENDING → PROCESSING → COMPLETED ✅
                             ↘ FAILED ❌
                                  ↓
                    POST /<id>/retry/ (no re-upload needed)
                                  ↓
                             PENDING → PROCESSING → COMPLETED ✅
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔐 **JWT Authentication** | Register, login, logout with refresh token rotation and blacklisting |
| 📄 **Document Upload** | PDF, JPEG, PNG, WebP — validated by magic bytes (not just extension) |
| ⚡ **Async Processing** | Celery + Redis task queue — API returns immediately, processing happens in background |
| 🤖 **AI Summarization** | 3-5 bullet point summaries grounded strictly in document content |
| 🏷️ **Entity Extraction** | People, organizations, dates, locations, key topics — structured JSON |
| 💬 **Document Q&A** | Ask anything, get answers from document content only — zero hallucination |
| 📚 **Q&A History** | Every question and answer saved per document — append-only log pattern |
| 🔄 **Smart Retry** | Retry failed documents without re-uploading — same file, fresh processing |
| 🚦 **Rate Limiting** | 10 uploads/minute + 20 uploads/day per user — Redis-backed token bucket |
| 🪝 **Webhooks** | HMAC-SHA256 signed notifications when processing completes |
| 📊 **API Docs** | Auto-generated Swagger UI + ReDoc from code annotations |
| ❤️ **Health Check** | DB + Redis liveness check endpoint for deployment monitoring |

---

## 🛠️ Tech Stack — And Why Each Choice Was Made

Every technology here was chosen deliberately. Here's the reasoning:

### Core Framework
| Technology | Why This, Not Something Else |
|------------|------------------------------|
| **Django 5** | Batteries-included ORM, admin, auth, migrations. FastAPI would require building these from scratch. For a data-heavy API, Django's ORM is a massive productivity advantage. |
| **Django REST Framework** | Industry standard. Serializers, ViewSets, throttling, permissions — all production-tested patterns. |
| **PostgreSQL** | JSONField for entities, UUID support, proper indexing, ACID transactions. SQLite doesn't scale, MySQL lacks Django-native JSONField quality. |

### Async Processing
| Technology | Why This, Not Something Else |
|------------|------------------------------|
| **Celery** | Python's most battle-tested task queue. Built-in retry logic, exponential backoff, task routing, monitoring. Bull (Node) and Sidekiq (Ruby) are alternatives but we're in Python. |
| **Redis** | Sub-millisecond task queuing. Also used for rate limiting counters. Could use RabbitMQ as broker but Redis does both broker + cache in one service. |
| **django-celery-results** | Stores task outcomes in PostgreSQL — queryable, persistent, visible in admin. |

### Authentication
| Technology | Why This, Not Something Else |
|------------|------------------------------|
| **SimpleJWT** | Refresh token rotation + blacklisting out of the box. Session auth doesn't work for stateless APIs. API key auth lacks expiry. JWT with blacklisting gives best of both worlds. |

### AI / Processing
| Technology | Why This, Not Something Else |
|------------|------------------------------|
| **Groq API (Llama 3.1)** | Free tier, no credit card, extremely fast inference (~200 tokens/sec). OpenAI costs money. Ollama works locally but not on Railway. Groq's SDK is OpenAI-compatible — swap in 5 lines. |
| **pypdf** | Active maintenance (PyPDF2 deprecated). `extraction_mode="layout"` gives significantly better text ordering than default. |

### Storage & Infrastructure
| Technology | Why This, Not Something Else |
|------------|------------------------------|
| **Cloudinary** | Free 25GB. Railway's filesystem is ephemeral — files disappear on redeploy. S3 requires a credit card. Cloudinary's free tier is genuinely production-viable. |
| **Whitenoise** | Serves Django static files without nginx. On Railway, no separate web server — Whitenoise handles it in-process. |
| **dj-database-url** | `conn_max_age=600` enables connection pooling — drastically reduces PostgreSQL connection overhead on free tier. |

### Testing
| Technology | Why This, Not Something Else |
|------------|------------------------------|
| **pytest + pytest-django** | Superior to Django's built-in test runner. Fixtures, parametrize, better output, parallel execution. |
| **factory-boy** | `DocumentFactory()` in one line vs 10 lines of manual `objects.create()`. Fake data with sensible defaults, overridable per-test. |
| **pytest-mock** | `mocker.patch()` for mocking Groq, Cloudinary, Celery in tests — never hit real APIs in CI. |
| **responses** | Intercepts `requests.post()` for webhook tests — no real HTTP calls. |

---

## 🚀 How to Run Locally

### Prerequisites

- Python 3.12+
- PostgreSQL running locally
- Redis running locally

```bash
# macOS
brew install postgresql redis
brew services start postgresql redis

# Ubuntu
sudo apt install postgresql redis-server
sudo systemctl start postgresql redis
```

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/docintelligence.git
cd docintelligence

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements/development.txt

# 4. Create database
createdb docintelligence

# 5. Set up environment variables
cp .env.example .env
# Edit .env with your values (see below)

# 6. Run migrations
python manage.py migrate

# 7. Create a superuser (for admin access)
python manage.py createsuperuser
```

### Environment Variables

Create a `.env` file in the project root:

```bash
# Django
SECRET_KEY=your-very-long-random-secret-key-minimum-50-chars
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite for quick start — no PostgreSQL needed)
# DATABASE_URL=postgres://postgres:postgres@localhost:5432/docintelligence

# Redis
REDIS_URL=redis://localhost:6379/0

# Groq AI (free at console.groq.com — no credit card)
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.1-8b-instant
GROQ_MAX_TOKENS=1000

# Rate Limiting
DAILY_UPLOAD_LIMIT=20

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

### Run Everything

You need **three terminals**:

```bash
# Terminal 1 — Django dev server
python manage.py runserver

# Terminal 2 — Celery worker (processes documents)
celery -A config worker -l info -c 2

# Terminal 3 — (Optional) Celery monitoring UI
pip install flower
celery -A config flower
# Visit http://localhost:5555
```

### Test It

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=apps --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest tests/documents/test_upload.py -v

# Run without coverage (faster)
pytest --no-cov
```

### API Documentation

Once the server is running:

| URL | What You'll Find |
|-----|-----------------|
| `http://localhost:8000/api/docs/` | Swagger UI — interactive, try endpoints live |
| `http://localhost:8000/api/redoc/` | ReDoc — clean readable documentation |
| `http://localhost:8000/api/schema/` | Raw OpenAPI JSON schema |
| `http://localhost:8000/admin/` | Django admin panel |
| `http://localhost:8000/api/health/` | System health check |

### Quick API Test (curl)

```bash
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!","password_confirm":"TestPass123!"}'

# 2. Login
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!"}'
# Copy the access token from response

# 3. Upload a document
curl -X POST http://localhost:8000/api/v1/documents/upload/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "title=My Document" \
  -F "file=@/path/to/your/document.pdf"

# 4. Check processing status
curl http://localhost:8000/api/v1/documents/DOCUMENT_ID/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 5. Ask a question (once status is "completed")
curl -X POST http://localhost:8000/api/v1/documents/DOCUMENT_ID/qa/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this document about?"}'
```

---

## 📁 Project Structure

```
docintelligence/
├── config/                     # Django project configuration
│   ├── settings/
│   │   ├── base.py            # Shared settings
│   │   ├── development.py     # Local dev overrides
│   │   └── production.py      # Railway production config
│   ├── celery.py              # Celery app setup
│   ├── urls.py                # Root URL routing
│   └── wsgi.py                # WSGI entry point
│
├── apps/
│   ├── users/                 # Authentication domain
│   │   ├── models.py          # Custom User (UUID PK, email login)
│   │   ├── managers.py        # UserManager with create_user
│   │   ├── serializers.py     # Register, Profile, JWT customization
│   │   ├── views.py           # Auth endpoints
│   │   └── urls.py
│   │
│   └── documents/             # Core domain
│       ├── models.py          # Document + QAHistory models
│       ├── ai.py              # All Groq API calls (isolated)
│       ├── tasks.py           # Celery tasks with retry logic
│       ├── utils.py           # PDF extraction + text cleaning
│       ├── validators.py      # Magic bytes file validation
│       ├── webhooks.py        # Webhook delivery + HMAC signing
│       ├── serializers.py     # Request/Response schemas
│       ├── views.py           # API endpoints
│       └── urls.py
│
├── common/                    # Shared across apps
│   ├── exceptions.py          # Global exception handler
│   ├── ratelimit.py           # Daily upload limit logic
│   └── views.py               # Health check endpoint
│
├── tests/                     # All tests
│   ├── conftest.py            # Shared fixtures
│   ├── factories.py           # Factory Boy model factories
│   ├── users/
│   │   ├── test_auth.py       # Register, login, logout, blacklist
│   │   └── test_profile.py    # Profile, password change
│   └── documents/
│       ├── test_upload.py     # Upload, validation, rate limiting
│       ├── test_processing.py # Celery task, retry, webhook trigger
│       ├── test_ai.py         # Groq functions, JSON parsing
│       ├── test_qa.py         # Q&A endpoint, auth, 503 handling
│       ├── test_qa_history.py # History save, retrieval, isolation
│       ├── test_webhooks.py   # Delivery, signature, timeout
│       └── test_retry.py      # Retry endpoint, ownership checks
│
├── Procfile                   # Railway: web + worker commands
├── runtime.txt                # Python version pin
├── requirements.txt           # Production dependencies
├── requirements/
│   ├── base.txt
│   ├── development.txt        # + pytest, factory-boy, etc.
│   └── production.txt         # + gunicorn, whitenoise
└── pytest.ini                 # Test config + coverage threshold
```

---

## 🌐 API Reference

### Authentication

```
POST   /api/v1/auth/register/          Register new user
POST   /api/v1/auth/login/             Login → access + refresh tokens
POST   /api/v1/auth/logout/            Blacklist refresh token
POST   /api/v1/auth/token/refresh/     Get new access token
GET    /api/v1/auth/profile/           Get current user profile
PATCH  /api/v1/auth/profile/           Update name
POST   /api/v1/auth/change-password/   Change password
```

### Documents

```
POST   /api/v1/documents/upload/           Upload PDF/image
GET    /api/v1/documents/                  List my documents
GET    /api/v1/documents/<id>/             Get document + AI results
DELETE /api/v1/documents/<id>/             Delete document
POST   /api/v1/documents/<id>/retry/       Retry failed document
POST   /api/v1/documents/<id>/qa/          Ask a question
GET    /api/v1/documents/<id>/qa/history/  Get Q&A history
```

### System

```
GET    /api/health/     Health check (DB + Redis status)
GET    /api/docs/       Swagger UI
GET    /api/redoc/      ReDoc
GET    /api/schema/     OpenAPI JSON
```

### Document Object Shape

```json
{
  "id": "7b346f61-6a1f-4c39-ae51-1da2b929ed82",
  "title": "Q3 Financial Report",
  "original_filename": "q3_report.pdf",
  "mime_type": "application/pdf",
  "status": "completed",
  "file_size_display": "2.4 MB",
  "file_url": "https://res.cloudinary.com/...",
  "summary": "• Revenue increased 23% YoY...\n• Operating costs reduced by...",
  "extracted_entities": {
    "people": ["John Smith", "Sarah Johnson"],
    "organizations": ["Acme Corp", "Goldman Sachs"],
    "dates": ["Q3 2024", "October 15, 2024"],
    "locations": ["New York", "London"],
    "key_topics": ["revenue growth", "cost reduction", "expansion"]
  },
  "webhook_url": "https://your-server.com/webhook",
  "webhook_delivered": true,
  "created_at": "2024-10-15T10:30:00Z",
  "processed_at": "2024-10-15T10:30:18Z"
}
```

---

## 😤 Challenges Faced — The Real Ones

Building this wasn't smooth. Here are the problems that actually required thinking:

### 1. Celery + Django Settings Module in Production
**Problem:** Worker kept crashing with `ModuleNotFoundError: No module named ' config'`.
**Root Cause:** A single space before `config` in the `DJANGO_SETTINGS_MODULE` Railway environment variable. One invisible character caused hours of debugging.
**Lesson:** Always `print(repr(env_var))` to check for invisible whitespace. Cloud environment variable UIs are deceptive.

### 2. Cloudinary 401 on File Download
**Problem:** Files uploaded fine to Cloudinary but Celery worker got 401 when trying to download them for processing.
**Root Cause:** Cloudinary's default delivery type for uploaded files is `image`, which requires authentication for direct URL access. `requests.get(url)` didn't have Cloudinary credentials.
**Solution:** Use Cloudinary's signed URL generation via `cloudinary.utils.private_download_url()` for authenticated access, or set the delivery type to `raw` for new uploads.

### 3. PDF Text Extraction Garbage Output
**Problem:** Some PDFs returned garbled text like `त र  क  र ा ज  न े त` — individual characters spaced apart.
**Root Cause:** PDF used custom font encoding (`/SymbolSetEncoding`) that pypdf couldn't decode properly. PyPDF2 was worse — completely mangled these.
**Solution:** Switched to `pypdf` with `extraction_mode="layout"`, added a garbage text detector (ratio of single-character words > 70% = garbage), and built a `_clean_text()` function that removes standalone line numbers and bad encoding artifacts.

### 4. Django Test `mocker` Fixture Not Found
**Problem:** All tests using `mocker` were failing with `fixture 'mocker' not found`.
**Root Cause:** `pytest-mock` was missing from `requirements/development.txt`. It provides the `mocker` fixture — without it, all mocking tests fail.
**Lesson:** Always verify `pip list | grep mock` before writing mock-based tests.

### 5. Production Static Files Missing
**Problem:** `ValueError: Missing staticfiles manifest entry for 'rest_framework/css/bootstrap.min.css'` in production.
**Root Cause:** `CompressedManifestStaticFilesStorage` requires `collectstatic` to have run and generated a manifest file. Railway's ephemeral filesystem meant this wasn't persisting between deploys.
**Solution:** Added `python manage.py collectstatic --noinput` to the Procfile `web` command so it runs on every deploy before gunicorn starts.

### 6. Thundering Herd on Celery Retries
**Problem:** Designing retry logic — naive implementation would have all failed tasks retry at exactly the same time, hammering the Groq API simultaneously.
**Solution:** `retry_backoff=True` (exponential: 60s, 120s, 240s) + `retry_jitter=True` (randomness added to each delay). Workers spread retries across time naturally — same approach used by AWS SQS, Stripe, and every major task queue.

### 7. Ownership Check — 403 vs 404
**Problem:** Initially returned 403 (Forbidden) when a user tried to access another user's document.
**Root Cause:** 403 reveals that the resource exists — an attacker can enumerate document IDs by looking for 403 vs 404 responses.
**Solution:** Filter queryset by `owner=request.user` so non-owned documents literally don't exist in the query — 404 every time. Security through not leaking existence.

---

## 🧪 Testing Philosophy

Tests are not just about coverage numbers. Each test proves a specific contract:

```bash
# Run full test suite
pytest

# Expected output
69 passed in 48s
Coverage: 80.10% ✅
```

**Key security tests that actually matter:**

```python
# Magic bytes — fake PDF (actually EXE) must be rejected
def test_upload_wrong_file_type()

# Ownership isolation — wrong user gets 404 not 403
def test_qa_wrong_user_gets_404()

# Token blacklist — logout means logout
def test_logout_blacklisted_token_cannot_refresh()

# Anti-hallucination — prompt must contain explicit instructions
def test_anti_hallucination_prompt_included()

# Webhook signatures — HMAC header must be present
def test_webhook_includes_signature_header()
```

---

## 🚢 Deployment

Live at: **https://web-production-c1239.up.railway.app**

| Service | Platform | Details |
|---------|----------|---------|
| Django API | Railway Web | Gunicorn, 2 workers |
| Celery Worker | Railway Worker | Separate process, same code |
| PostgreSQL | Railway DB | Managed, auto-backups |
| Redis | Railway Redis | Task queue + rate limit cache |
| File Storage | Cloudinary | Free 25GB, CDN delivery |
| AI | Groq API | Free tier, Llama 3.1 8B |

### Deploy Your Own

```bash
# 1. Fork this repo

# 2. Create Railway project
#    railway.app → New Project → Deploy from GitHub

# 3. Add services: PostgreSQL + Redis (Railway provides these)

# 4. Set environment variables in Railway dashboard:
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=your-secret-key
GROQ_API_KEY=your-groq-key
CLOUDINARY_URL=cloudinary://key:secret@cloudname
GROQ_MODEL=llama-3.1-8b-instant

# Railway auto-provides: DATABASE_URL, REDIS_URL, RAILWAY_PUBLIC_DOMAIN

# 5. Push to main → Railway auto-deploys
git push origin main
```

---

## 📈 What I Learned Building This

This project was specifically designed to cover concepts tested in FAANG backend interviews:

| Concept | Where Used In This Project |
|---------|---------------------------|
| **Async task processing** | Celery document processing pipeline |
| **Message queue patterns** | Redis broker, task routing, DLQ behavior |
| **Retry + backoff algorithms** | Exponential backoff with jitter in Celery tasks |
| **Multi-tenancy** | Row-level ownership isolation on every queryset |
| **JWT security** | Refresh token rotation + blacklisting |
| **Rate limiting algorithms** | Token bucket (per-minute) + sliding window (per-day) |
| **Webhook design** | HMAC-SHA256 signing, idempotency keys, retry delivery |
| **File security** | Magic bytes validation, user-scoped storage paths |
| **Database optimization** | Composite indexes, `update_fields`, connection pooling |
| **Test design** | Factories, mocking at boundary, security contract tests |
| **Observability** | Structured JSON logging, health check endpoint |
| **12-factor app** | Split settings, env-based config, stateless processes |

---

## 🔭 What's Next

- [ ] OCR for scanned PDFs (tesseract integration)
- [ ] Docker + Docker Compose for local dev
- [ ] GitHub Actions CI/CD pipeline
- [ ] Sentry error monitoring
- [ ] Celery task progress tracking (10% → 30% → 60% → 100%)
- [ ] Multi-document Q&A
- [ ] Request ID tracing across logs

---

## 📄 License

MIT License — use it, learn from it, build on it.

---

<div align="center">

**Built with frustration, fixed with logs, deployed with relief.**

*If this helped you — star it ⭐*

</div>