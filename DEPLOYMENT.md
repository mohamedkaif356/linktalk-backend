# Complete Deployment Guide

Step-by-step guide to deploy RAG Backend API from GitHub to Render.com.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Create GitHub Repository](#step-1-create-github-repository)
3. [Step 2: Push Code to GitHub](#step-2-push-code-to-github)
4. [Step 3: Deploy to Render.com](#step-3-deploy-to-rendercom)
5. [Step 4: Verify Deployment](#step-4-verify-deployment)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- ✅ GitHub account ([mohamedkaif356](https://github.com/mohamedkaif356))
- ✅ Render.com account (free tier works)
- ✅ OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- ✅ Git installed on your machine

---

## Step 1: Create GitHub Repository

### Using GitHub Web Interface

1. Go to: https://github.com/new
2. **Repository Settings**:
   - **Owner**: `mohamedkaif356`
   - **Repository name**: `rag-backend-api`
   - **Description**: `Production-ready FastAPI backend for RAG-based chat application`
   - **Visibility**: ✅ Public (for portfolio)
   - **Initialize**: ❌ Uncheck all (README, .gitignore, license)
3. Click **"Create repository"**

---

## Step 2: Push Code to GitHub

### 2.1 Initialize Git (If Not Already)

```bash
cd "/Users/kaifbagwan/Downloads/RAG backend 2"

# Check if git is initialized
if [ ! -d .git ]; then
    git init
    git branch -M main
fi
```

### 2.2 Stage and Commit Files

```bash
# Stage all files
git add .

# Verify secrets are NOT included
git status --ignored | grep -E "\.env|\.db|chroma_db"
# Should show these as ignored ✅

# Create commit
git commit -m "feat: Production-ready RAG Backend API with comprehensive testing and CI/CD"
```

### 2.3 Push to GitHub

```bash
# Add remote
git remote add origin https://github.com/mohamedkaif356/rag-backend-api.git

# Push to GitHub
git push -u origin main
```

**Authentication**: If prompted, use **Personal Access Token** (not password)
- Create token: https://github.com/settings/tokens
- Scope: `repo` (full control)

### 2.4 Verify Repository

Visit: `https://github.com/mohamedkaif356/rag-backend-api`

Check:
- ✅ All files present
- ✅ `.env` NOT visible (gitignored)
- ✅ Tests directory present
- ✅ CI/CD workflow file present

---

## Step 3: Deploy to Render.com

### 3.1 Create Render Account

1. Go to: https://render.com
2. Sign up (free tier works)
3. Verify email

### 3.2 Create New Web Service

1. **Dashboard** → **"New +"** → **"Web Service"**
2. **Connect GitHub**:
   - Click "Connect account" if not connected
   - Authorize Render to access repositories
   - Select: `rag-backend-api`
3. **Configure Service**:
   - **Name**: `rag-backend-api`
   - **Region**: Choose closest (e.g., `Oregon (US West)`)
   - **Branch**: `main`
   - **Root Directory**: (leave empty)
   - **Python Version**: **CRITICAL** - Set to `3.11.11` (or `3.11`) in the dropdown. This overrides the default Python 3.13 which causes build failures.
   - **OR** add environment variable `PYTHON_VERSION=3.11.11` in the Environment tab

### 3.3 Build & Start Commands

**Build Command:**
```bash
pip install --upgrade pip setuptools wheel && pip install -r requirements.txt
```

**CRITICAL**: You MUST set Python version to **3.11.9** in Render's service settings (see step 3.2). The `runtime.txt` file alone is not enough - Render may ignore it. You must explicitly set it in the dashboard.

**Start Command:**
```bash
gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

**Important**: 
- The project includes a `runtime.txt` file that pins Python to 3.11.9
- **You must also explicitly set Python version to 3.11.9 in Render's service settings** (see step 3.2 above)
- Python 3.13 causes build failures because `pydantic-core` (Rust-based) doesn't have pre-built wheels for Python 3.13 yet

### 3.4 Set Environment Variables

Click **"Environment"** tab, add:

| Variable | Value | How to Get |
|----------|-------|------------|
| `OPENAI_API_KEY` | `sk-proj-...` | Your actual OpenAI API key from [OpenAI Platform](https://platform.openai.com/api-keys) |
| `DATABASE_URL` | `sqlite:///./rag_backend.db` | SQLite for MVP |
| `DEVICE_FINGERPRINT_SALT` | `[generate]` | Run: `openssl rand -hex 32` |
| `ENVIRONMENT` | `production` | Set to production mode |

**Generate Salt:**
```bash
openssl rand -hex 32
# Copy the output and use as DEVICE_FINGERPRINT_SALT value
```

### 3.5 Deploy

1. Click **"Create Web Service"**
2. Wait for build (2-5 minutes)
3. Monitor build logs
4. Service URL: `https://rag-backend-api.onrender.com`

---

## Step 4: Verify Deployment

### 4.1 Health Check

```bash
curl https://rag-backend-api.onrender.com/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "database": {"status": "ok", "latency_ms": 1.23},
  "vector_db": {"status": "ok", "latency_ms": 2.45},
  "openai": {"status": "configured", "latency_ms": 0}
}
```

### 4.2 API Documentation

Visit: `https://rag-backend-api.onrender.com/docs`

You should see the Swagger UI with all available endpoints.

### 4.3 Test Device Registration

```bash
curl -X POST "https://rag-backend-api.onrender.com/api/v1/register-device" \
  -H "Content-Type: application/json" \
  -d '{
    "app_instance_id": "test-uuid-123",
    "device_model": "Test Device",
    "os_version": "1.0"
  }'
```

**Expected Response:**
```json
{
  "device_token": "abc123...",
  "quota_remaining": 3,
  "device_fingerprint": "hash..."
}
```

---

## Troubleshooting

### Service Won't Start

**Symptoms:**
- Build succeeds but service shows "Unhealthy"
- Logs show startup errors

**Solutions:**
- Check environment variables are set correctly
- Verify `OPENAI_API_KEY` is valid
- Check start command is correct
- Review logs for specific error messages

### Database Connection Errors

**Symptoms:**
- Health check shows database error
- API returns 500 errors

**Solutions:**
- Verify `DATABASE_URL` is correct
- For SQLite: Ensure path is writable
- Check Render logs for specific errors

### OpenAI API Errors

**Symptoms:**
- Ingestion/query endpoints fail
- Error: "OpenAI API key not configured"

**Solutions:**
- Verify `OPENAI_API_KEY` is set in environment variables
- Check API key is valid (starts with `sk-`)
- Verify API key has sufficient quota
- Check OpenAI API status

### Build Failures

**Symptoms:**
- Build fails during `pip install`

**Solutions:**
- Check `requirements.txt` is present
- Verify Python version compatibility
- Check for dependency conflicts
- Review build logs for specific errors

### Getting Help

- **Render Support**: [Render Support](https://render.com/docs/support)
- **Application Logs**: Check Render dashboard logs
- **Health Endpoint**: `/health` provides system status
- **API Docs**: `/docs` for endpoint documentation

---

## Important Notes

### Render Free Tier Limitations

- **Spins down after 15 minutes** of inactivity
- **Cold start**: First request after spin-down takes ~30 seconds
- **Solution**: Use Render paid tier or keep-alive service for production

### Database Persistence

- **SQLite on Render**: Data is **ephemeral** (lost on restart)
- **For Production**: Consider Render PostgreSQL addon
- **For MVP/Portfolio**: SQLite is acceptable

### API Key Security

- ✅ Never commit `.env` file
- ✅ Always use environment variables
- ✅ Rotate keys periodically
- ✅ Monitor usage in OpenAI dashboard

---

## Quick Reference

### Service URLs

- **API Base**: `https://rag-backend-api.onrender.com/api/v1`
- **Health Check**: `https://rag-backend-api.onrender.com/health`
- **API Docs**: `https://rag-backend-api.onrender.com/docs`

### Environment Variables Summary

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | OpenAI API key |
| `DATABASE_URL` | ✅ Yes | Database connection |
| `DEVICE_FINGERPRINT_SALT` | ✅ Yes | Salt for hashing |
| `ENVIRONMENT` | ✅ Yes | Environment name |

---

**Last Updated**: 2026-01-15
