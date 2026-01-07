# Setup Instructions

## 1. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Or if using a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Database Migrations

After installing dependencies and creating your `.env` file, run:

```bash
./migrate.sh
```

Or manually:

```bash
cd src
python3 manage.py makemigrations authentication
python3 manage.py migrate
```

This will create the necessary tables in your PostgreSQL database.

## 4. Run the Server

The server runs on port 5000 by default:

```bash
./run.sh
```

Or manually:

```bash
cd src
python3 manage.py runserver 5000
```

## API Endpoints

- `POST /api/auth/login` - Login and save user/tokens
- `POST /api/auth/logout` - Logout and remove refresh token
- `POST /api/auth/refresh` - Refresh access token

All endpoints are public and don't require authentication.

