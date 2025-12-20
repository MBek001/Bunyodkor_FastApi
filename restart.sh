#!/bin/bash

echo "🔄 Cleaning Python cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

echo "✅ Cache cleaned!"
echo "🚀 Start server with: uvicorn app.main:app --reload"
