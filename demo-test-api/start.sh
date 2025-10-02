#!/bin/bash

# Demo Test API Startup Script
# This script sets up and starts the Demo Test API for APE testing

set -e

echo "🚀 Starting Demo Test API..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ and try again."
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version 18+ is required. Current version: $(node --version)"
    exit 1
fi

echo "✅ Node.js version: $(node --version)"

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
else
    echo "✅ Dependencies already installed"
fi

# Build the project
echo "🔨 Building project..."
npm run build

# Set default environment variables if not set
export PORT=${PORT:-3000}
export NODE_ENV=${NODE_ENV:-production}
export SESSION_SECRET=${SESSION_SECRET:-demo-secret}
export ERROR_RATE_503=${ERROR_RATE_503:-0.05}
export ERROR_RATE_500=${ERROR_RATE_500:-0.01}
export RESPONSE_DELAY_MIN=${RESPONSE_DELAY_MIN:-50}
export RESPONSE_DELAY_MAX=${RESPONSE_DELAY_MAX:-200}

echo "🔧 Configuration:"
echo "   Port: $PORT"
echo "   Environment: $NODE_ENV"
echo "   Error Rate (503): $ERROR_RATE_503"
echo "   Error Rate (500): $ERROR_RATE_500"
echo "   Response Delay: ${RESPONSE_DELAY_MIN}-${RESPONSE_DELAY_MAX}ms"

# Start the server
echo "🌟 Starting Demo Test API on port $PORT..."
echo "📍 Health check: http://localhost:$PORT/api/health"
echo "📍 API documentation: http://localhost:$PORT/"
echo ""
echo "Press Ctrl+C to stop the server"

npm start