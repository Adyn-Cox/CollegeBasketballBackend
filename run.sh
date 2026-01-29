#!/bin/bash
# Script to run FastAPI server on port 5001

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

# Run FastAPI with uvicorn
uvicorn app:app --host 0.0.0.0 --port 5000 --reload
