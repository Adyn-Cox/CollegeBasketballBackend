#!/bin/bash
# Script to run Django server on port 5000

# Check if .env file exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found in project root!"
    echo "Please create .env file with required variables."
    exit 1
fi

# Load .env file manually
export $(grep -v '^#' .env | xargs)

# Check for virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python manage.py runserver 5001

 