@echo off
echo ======================================================
echo Boards ^& Beyond Studio Player ^& Quiz Extractor (Windows)
echo ======================================================
if not exist "node_modules" (
  echo Installing Node.js dependencies...
  call npm install
)
start "" http://localhost:4100
node server.js
