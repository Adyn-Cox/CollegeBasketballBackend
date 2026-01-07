# CollegeBasketballBackend

Backend for college basketball predictor using Django REST Framework with Supabase authentication.

## Prerequisites

- Python 3.12+
- PostgreSQL database
- Supabase account (for authentication)

## Setup

### 1. Create Python Virtual Environment

Create and activate a virtual environment:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate
```

**Note:** On Windows, use `.venv\Scripts\activate` instead.

You should see `(.venv)` in your terminal prompt when activated.

### 2. Install Dependencies

Install required Python packages:

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the project root with the following variables:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_ANON_KEY=your-anon-key
```

**Where to find Supabase values:**
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_JWT_SECRET`: Supabase Dashboard → Settings → API → JWT Secret
- `SUPABASE_ANON_KEY`: Supabase Dashboard → Settings → API → anon/public key

### 4. Database Migrations

Run database migrations to create the necessary tables:

```bash
./migrate.sh
```

Or manually:

```bash
python manage.py makemigrations authentication
python manage.py migrate
```

**Note:** Make sure your PostgreSQL database is running and the `DATABASE_URL` in `.env` is correct.

### 5. Run the Application

Start the Django development server on port 5000:

```bash
./run.sh
```

Or manually:

```bash
python manage.py runserver 5000
```

The server will be available at `http://127.0.0.1:5000/`

## API Endpoints

All authentication endpoints are public (no token required):

- **POST** `/api/auth/login` - Login and save user/tokens
  - Body: `{ "access_token": "...", "refresh_token": "..." }`
  
- **POST** `/api/auth/logout` - Logout and remove refresh token
  - Body: `{ "refresh_token": "..." }`
  
- **POST** `/api/auth/refresh` - Refresh access token
  - Body: `{ "refresh_token": "..." }`

## Project Structure

```
├── authentication/     # Authentication app
│   ├── models.py       # SupabaseUser model
│   ├── views.py        # API endpoints
│   ├── middleware.py   # Token validation middleware
│   └── utils.py        # JWT validation utilities
├── config/             # Django project settings
│   ├── settings.py     # Main configuration
│   └── urls.py         # URL routing
├── manage.py           # Django management script
├── requirements.txt    # Python dependencies
├── migrate.sh          # Migration script
└── run.sh              # Run server script
```

## Troubleshooting

- **Virtual environment not activating:** Make sure you're in the project root directory
- **Database connection errors:** Verify `DATABASE_URL` in `.env` is correct and PostgreSQL is running
- **Module not found errors:** Make sure virtual environment is activated and dependencies are installed
- **Port 5000 already in use:** Change the port in `run.sh` or kill the process using port 5000
