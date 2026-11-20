#!/usr/bin/env bash
set -e

echo "======================================================"
echo "🎬 Boards & Beyond Studio Player & Quiz Extractor (macOS)"
echo "======================================================"

if [ ! -d "node_modules" ]; then
  echo "📦 Installing Node.js dependencies..."
  npm install
fi

echo "🚀 Starting server at http://localhost:4100 ..."
node server.js
