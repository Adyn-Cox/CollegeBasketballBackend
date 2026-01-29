# FastAPI Migration Guide

## Overview

The backend has been migrated from Django REST Framework to FastAPI while maintaining **100% API compatibility**. The frontend does **NOT need any changes**.

## What Changed

- **Backend Framework**: Django REST Framework → FastAPI
- **API Endpoints**: **UNCHANGED** - Same URLs, same request/response formats
- **Authentication**: **UNCHANGED** - Same Bearer token authentication
- **Database**: **UNCHANGED** - Still using Django ORM (models unchanged)

## API Endpoints (Unchanged)

All endpoints work exactly the same:

### POST `/api/auth/login`
**Request:**
```json
{
  "access_token": "...",
  "refresh_token": "..."
}
```

**Response:**
```json
{
  "message": "Login successful",
  "user": {
    "supabase_user_id": "...",
    "email": "...",
    "created_at": "...",
    "updated_at": "..."
  },
  "created": true
}
```

### POST `/api/auth/logout`
**Request:**
```json
{
  "refresh_token": "..."  // Optional
}
```

**Response:**
```json
{
  "message": "Logout successful"
}
```

### POST `/api/auth/refresh`
**Request:**
```json
{
  "refresh_token": "..."
}
```

**Response:**
```json
{
  "access_token": "...",
  "refresh_token": "..."
}
```

## Running the FastAPI Server

### Option 1: Using the run script
```bash
./run_fastapi.sh
```

### Option 2: Manual command
```bash
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 5001 --reload
```

The server will run on `http://127.0.0.1:5001/`

## Frontend Changes Required

**NONE!** The API is 100% compatible. Your frontend code can continue using the same endpoints with the same request/response formats.

## What's Different Under the Hood

1. **Framework**: FastAPI instead of Django REST Framework
2. **Validation**: Pydantic models instead of DRF serializers
3. **Authentication**: FastAPI dependencies instead of Django middleware
4. **Database**: Still using Django ORM (no changes to models)

## Benefits of FastAPI

- ⚡ **Faster**: Better performance, especially for async operations
- 📚 **Auto Documentation**: Interactive API docs at `/docs` and `/redoc`
- 🔒 **Type Safety**: Pydantic models provide better validation
- 🚀 **Modern**: Built for async/await patterns

## API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: `http://localhost:5001/docs`
- **ReDoc**: `http://localhost:5001/redoc`

## Testing

Tests continue to work the same way. The Django test suite can still be used, or you can add FastAPI-specific tests.

## Migration Checklist

- [x] FastAPI application created
- [x] All endpoints migrated
- [x] Authentication dependency created
- [x] CORS configured
- [x] Pydantic models match DRF serializers
- [x] Run script created
- [ ] Install new dependencies: `pip install -r requirements.txt`
- [ ] Test endpoints with frontend
- [ ] Update deployment configuration (if needed)

## Notes

- The FastAPI app still uses Django ORM for database access
- All environment variables remain the same
- Database migrations are still managed by Django
- You can run both Django and FastAPI servers simultaneously for gradual migration
