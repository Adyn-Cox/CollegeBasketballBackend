#!/bin/bash
# Script to run database migrations
# Installs dependencies and runs migrations

# Check if .env file exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found in project root!"
    echo "Please create .env file with DATABASE_URL and other required variables."
    exit 1
fi

# Load .env file manually (in case python-dotenv isn't installed yet)
export $(grep -v '^#' .env | xargs)

# Check for virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "No virtual environment found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
fi

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Creating migrations..."
python manage.py makemigrations authentication
echo "Running migrations..."
python manage.py migrate

echo "Migrations completed!"

