# RAG Backend API

Production-ready FastAPI backend for RAG-based chat application with OpenAI integration, comprehensive testing, and CI/CD pipeline.

[![Tests](https://github.com/mohamedkaif356/rag-backend-api/workflows/CI/badge.svg)](https://github.com/mohamedkaif356/rag-backend-api/actions)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com)

## 🌐 Live Demo

- **API Base**: https://rag-backend-api.onrender.com/api/v1
- **API Documentation**: https://rag-backend-api.onrender.com/docs
- **Health Check**: https://rag-backend-api.onrender.com/health
- **GitHub Repository**: https://github.com/mohamedkaif356/rag-backend-api

## 🚀 Production Deployment

This application is production-ready and can be deployed to Render.com or similar platforms.

**For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)**

### Quick Deploy to Render

1. **Push code to Git repository** (GitHub/GitLab/Bitbucket)
2. **Create new Web Service** in Render dashboard
3. **Set environment variables**:
   - `OPENAI_API_KEY` (required)
   - `DATABASE_URL` (default: `sqlite:///./rag_backend.db`)
   - `DEVICE_FINGERPRINT_SALT` (generate random string)
   - `ENVIRONMENT=production`
4. **Configure build command**: `pip install -r requirements.txt`
5. **Configure start command**: `gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete step-by-step guide.

## Quick Start (Local Development)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Setup Environment
Create a `.env` file (see `.env.example` for template):
```bash
DATABASE_URL=sqlite:///./rag_backend.db
DEVICE_FINGERPRINT_SALT=your-random-salt-here
ENVIRONMENT=development
OPENAI_API_KEY=your-openai-api-key-here
```

**Important**: 
- Get your OpenAI API key from [OpenAI Platform](https://platform.openai.com/api-keys)
- Never commit `.env` file to version control
- For production, set environment variables in your hosting platform (e.g., Render)

### 3. Initialize Database
```bash
python3 -m app.db.init_db
```

### 4. Start Server
```bash
./start_server.sh
```

Or manually:
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Story 1: Device Registration

### Endpoint: `POST /api/v1/register-device`

Register a device and receive a device token for authentication.

**Request:**
```json
{
  "app_instance_id": "uuid-generated-on-app-start",
  "device_model": "Pixel 6",
  "os_version": "14",
  "stable_device_id": "optional-stable-id"
}
```

**Response (200):**
```json
{
  "device_token": "opaque-token-string",
  "quota_remaining": 3,
  "device_fingerprint": "hashed-fingerprint"
}
```

**Error Responses:**
- `400 MISSING_FIELD`: Missing required field
- `400 INVALID_DEVICE_INFO`: Invalid device information format

## Story 3: URL Scraping & Ingestion

### Endpoint: `POST /api/v1/scrape-url`

Initiate URL scraping and ingestion. Returns immediately with ingestion_id for status polling.

**Headers:**
- `X-Device-Token`: Device authentication token (required)

**Request:**
```json
{
  "url": "https://example.com"
}
```

**Response (200):**
```json
{
  "ingestion_id": "uuid",
  "status": "PENDING",
  "estimated_time_seconds": 20
}
```

**Error Responses:**
- `400 INVALID_URL`: Invalid URL format or scheme
- `400 INTERNAL_IP_NOT_ALLOWED`: URL points to internal/reserved IP
- `400 URL_ALREADY_INGESTED`: Device has already ingested a URL (only one URL per device allowed)
- `401 UNAUTHORIZED`: Missing or invalid device token

### Endpoint: `GET /api/v1/ingestions/{ingestion_id}`

Get ingestion status by ID. Only returns ingestion if it belongs to the requesting device.

**Headers:**
- `X-Device-Token`: Device authentication token (required)

**Response (200):**
```json
{
  "id": "uuid",
  "status": "PENDING|PROCESSING|SUCCESS|FAILED",
  "url": "https://example.com",
  "chunk_count": 123,
  "token_count": 45000,
  "error_code": null,
  "error_message": null,
  "created_at": "2026-01-14T...",
  "started_at": "2026-01-14T...",
  "completed_at": "2026-01-14T..."
}
```

**Error Responses:**
- `401 UNAUTHORIZED`: Missing or invalid device token
- `403 FORBIDDEN`: Ingestion belongs to different device
- `404 NOT_FOUND`: Ingestion not found

**Status Transitions:**
- `PENDING` → `PROCESSING` → `SUCCESS` or `FAILED`
- On failure: `error_code` and `error_message` are populated

## Story 4: RAG Query API

### Endpoint: `POST /api/v1/query`

Submit a query about your ingested content. Returns immediately with query_id for status polling.

**Headers:**
- `X-Device-Token`: Device authentication token (required)

**Request:**
```json
{
    "question": "What is machine learning?",
    "max_chunks": 5,
    "temperature": 0.7
}
```

**Response (200):**
```json
{
    "query_id": "uuid",
    "status": "PENDING",
    "estimated_time_seconds": 5
}
```

**Error Responses:**
- `400 INVALID_QUESTION`: Question too short (< 10 chars) or too long (> 500 chars)
- `401 UNAUTHORIZED`: Missing or invalid device token
- `403 QUOTA_EXHAUSTED`: Device quota is 0

### Endpoint: `GET /api/v1/queries/{query_id}`

Get query status and answer by ID. Only returns query if it belongs to the requesting device.

**Headers:**
- `X-Device-Token`: Device authentication token (required)

**Response (200):**
```json
{
    "id": "uuid",
    "question": "What is machine learning?",
    "answer": "Machine learning is a method of data analysis...",
    "status": "SUCCESS",
    "chunk_count_used": 5,
    "token_count": 150,
    "sources": [
        {
            "ingestion_id": "uuid",
            "url": "https://example.com",
            "chunk_id": "uuid_0",
            "relevance_score": 0.85,
            "text_snippet": "Machine learning is a method..."
        }
    ],
    "error_code": null,
    "error_message": null,
    "created_at": "2026-01-14T...",
    "completed_at": "2026-01-14T..."
}
```

**Error Responses:**
- `401 UNAUTHORIZED`: Missing or invalid device token
- `403 FORBIDDEN`: Query belongs to different device
- `404 NOT_FOUND`: Query not found

**Status Transitions:**
- `PENDING` → `PROCESSING` → `SUCCESS` or `FAILED`
- On success: `answer`, `sources`, `chunk_count_used`, and `token_count` are populated
- On failure: `error_code` and `error_message` are populated

## Testing

### cURL Commands

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Register Device:**
```bash
curl -X POST "http://localhost:8000/api/v1/register-device" \
  -H "Content-Type: application/json" \
  -d '{
    "app_instance_id": "test-uuid-123",
    "device_model": "Pixel 6",
    "os_version": "14"
  }'
```

**Test Error (Missing Field):**
```bash
curl -X POST "http://localhost:8000/api/v1/register-device" \
  -H "Content-Type: application/json" \
  -d '{
    "device_model": "Pixel 6",
    "os_version": "14"
  }'
```

**Scrape URL (requires device token):**
```bash
# First, register device to get token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/register-device" \
  -H "Content-Type: application/json" \
  -d '{"app_instance_id":"test-123","device_model":"Test","os_version":"14"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['device_token'])")

# Then scrape URL
curl -X POST "http://localhost:8000/api/v1/scrape-url" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: $TOKEN" \
  -d '{"url": "https://example.com"}'
```

**Check Ingestion Status:**
```bash
curl "http://localhost:8000/api/v1/ingestions/{ingestion_id}" \
  -H "X-Device-Token: $TOKEN"
```

**Test Invalid URL:**
```bash
curl -X POST "http://localhost:8000/api/v1/scrape-url" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: $TOKEN" \
  -d '{"url": "http://127.0.0.1"}'
```

**Submit Query (requires ingested content):**
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: $TOKEN" \
  -d '{"question": "What is this website about?"}'
```

**Get Query Status:**
```bash
curl "http://localhost:8000/api/v1/queries/{query_id}" \
  -H "X-Device-Token: $TOKEN"
```

**Test Invalid Question:**
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: $TOKEN" \
  -d '{"question": "short"}'
```

### E2E Test Script

Run the comprehensive end-to-end tests:
```bash
python3 test_story3.py  # Story 3: URL Scraping
python3 test_story4.py  # Story 4: RAG Query
```

**Story 3 tests:**
- Device registration
- URL scraping
- Status polling
- Error handling (invalid URLs, internal IPs)
- Authorization (device isolation)

**Story 4 tests:**
- Full RAG flow (scrape → query → get answer)
- Answer generation with sources
- Error handling (invalid questions, no content, quota exhausted)
- Authorization (device isolation)

### Postman Collection

Import `RAG_Backend_Complete_Collection.json` into Postman for pre-configured requests.

## Testing

The project includes comprehensive unit and integration tests to ensure code quality and reliability.

### Running Tests

**Run all tests:**
```bash
pytest
```

**Run with coverage report:**
```bash
pytest --cov=app --cov-report=html
```

**Run specific test file:**
```bash
pytest tests/test_url_validator.py
```

**Run with verbose output:**
```bash
pytest -v
```

### Test Structure

- **Unit Tests**: Test individual service functions (`tests/test_*.py`)
  - `test_url_validator.py` - URL validation logic
  - `test_chunker.py` - Text chunking logic
  - `test_query_service.py` - Query service functions

- **Integration Tests**: Test API endpoints (`tests/test_api_*.py`)
  - `test_api_devices.py` - Device registration endpoints
  - `test_api_ingestions.py` - URL ingestion endpoints
  - `test_api_queries.py` - Query endpoints
  - `test_health.py` - Health check endpoint

### Test Coverage

The project aims for 60%+ test coverage. Coverage reports are generated in HTML format:
```bash
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

### CI/CD

Tests run automatically on every push via GitHub Actions (`.github/workflows/ci.yml`):
- Linting with ruff
- Format checking with black
- Test execution with coverage reporting
- Supports Python 3.11 and 3.12

## Local Network Access

To allow access from other devices on the same Wi-Fi:

1. Find your local IP:
   ```bash
   ipconfig getifaddr en0  # macOS
   ```

2. Server is already configured to accept connections (`--host 0.0.0.0`)

3. Share your IP with friends: `http://YOUR_IP:8000`

## Project Structure

```
app/
├── main.py                 # FastAPI app and CORS setup
├── core/
│   ├── config.py          # Settings from environment
│   ├── errors.py           # Standardized error classes
│   └── background_tasks.py # Thread pool executor
├── db/
│   ├── session.py          # Database session and Base
│   ├── models.py           # SQLAlchemy models (Device, DeviceToken, Ingestion, Query, QueryChunk)
│   └── init_db.py          # Database initialization
├── services/
│   ├── url_validator.py    # URL validation logic
│   ├── scraper.py          # HTML fetching & extraction
│   ├── chunker.py          # Text chunking
│   ├── embeddings.py       # OpenAI embedding service
│   ├── vector_db.py        # Chroma integration
│   ├── ingestion_worker.py  # Async ingestion pipeline
│   ├── llm_service.py      # OpenAI chat completion service
│   ├── query_service.py    # RAG query logic (embed, search, context)
│   └── query_worker.py     # Async query processing pipeline
├── api/
│   ├── deps.py             # FastAPI dependencies (get_current_device)
│   └── v1/
│       └── routes/
│           ├── devices.py   # Device registration endpoint
│           ├── ingestions.py # URL scraping & status endpoints
│           └── queries.py   # RAG query endpoints
└── schemas/
    ├── devices.py          # Device schemas
    ├── ingestions.py       # Ingestion schemas
    └── queries.py          # Query schemas
```

## Important Limitations & Improvements

### Limitations

1. **One URL Per Device**: Each device can only ingest one URL. Attempting to scrape a second URL will return a `400 URL_ALREADY_INGESTED` error with the existing URL.

2. **Query Quota**: Each device has a quota of **3 queries total**. Once exhausted, further queries will return a `403 QUOTA_EXHAUSTED` error.

3. **URL-Specific Queries**: Queries only search chunks from the device's ingested URL. The vector database is organized by `device_id` + `ingestion_id` (URL) to ensure proper isolation.

4. **Website Anti-Bot Protection**: Some websites (like Medium.com, LinkedIn, etc.) have strong anti-bot protection (e.g., Cloudflare) that may block scraping attempts even with browser-like headers. These sites will return `403 HTTP_ERROR` with a message indicating anti-bot protection. This is expected behavior for protected sites. Try using URLs from sites without such protection.

### Recent Improvements

1. **Enhanced Scraping**: The scraper now uses BeautifulSoup4 as the primary extraction method, with readability-lxml as fallback. This improves support for:
   - Product/e-commerce websites
   - Product listings and detail pages
   - Blog posts and articles
   - General content pages

2. **Better Content Extraction**: The scraper intelligently extracts:
   - Product titles, descriptions, and prices
   - Product specifications and features
   - Main content from various page structures
   - Schema.org structured data when available

3. **Vector DB Organization**: Chunks are now properly organized by device and URL, ensuring queries only search relevant content.

## Features

- ✅ Device registration with opaque token authentication
- ✅ Device fingerprinting for quota management
- ✅ Idempotent registration (preserves quota on re-registration)
- ✅ URL validation (format, internal IPs, length)
- ✅ Async URL scraping with background processing
- ✅ Enhanced content extraction using BeautifulSoup4 (primary) and readability-lxml (fallback)
- ✅ Support for product/e-commerce websites, blog posts, and general content pages
- ✅ Text chunking with token-based splitting
- ✅ OpenAI embeddings generation
- ✅ Chroma vector database integration
- ✅ Status polling for ingestion progress
- ✅ Device authorization (users can only access their ingestions)
- ✅ RAG query functionality (semantic search + AI answers)
- ✅ Vector search with device filtering
- ✅ Answer generation using OpenAI GPT-4o-mini
- ✅ Source attribution with relevance scores
- ✅ Query quota management
- ✅ Comprehensive error handling
- ✅ Standardized error responses
- ✅ SQLite database for MVP
- ✅ CORS enabled for cross-origin requests

## Error Codes

### Device Registration
- `MISSING_FIELD` - Missing required field
- `INVALID_DEVICE_INFO` - Invalid device information format

### URL Scraping
- `INVALID_URL` - Invalid URL format or scheme
- `INTERNAL_IP_NOT_ALLOWED` - URL points to internal/reserved IP
- `URL_ALREADY_INGESTED` - Device has already ingested a URL (only one URL per device allowed)
- `UNAUTHORIZED` - Missing or invalid device token
- `FORBIDDEN` - Access denied (wrong device)
- `NOT_FOUND` - Ingestion not found

### Ingestion Status
- `NETWORK_TIMEOUT` - Request timed out
- `HTTP_ERROR` - HTTP error response
- `NO_CONTENT` - No readable content extracted
- `UNKNOWN_ERROR` - Unexpected error during processing

### RAG Query
- `INVALID_QUESTION` - Question too short or too long
- `NO_CONTENT` - No ingested content available for device
- `QUOTA_EXHAUSTED` - Device quota is 0
- `UNAUTHORIZED` - Missing or invalid device token
- `FORBIDDEN` - Access denied (wrong device)
- `NOT_FOUND` - Query not found
