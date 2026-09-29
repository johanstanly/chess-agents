@echo off
rem Starts a small local web server for the replay website and opens it.
rem Leave this window open while you use the page. Close it to stop.
cd /d "%~dp0docs"
start "" http://localhost:8000/
python -m http.server 8000
