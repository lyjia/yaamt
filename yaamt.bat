@echo off
REM YAAMT CLI launcher for Windows
REM This script activates the virtual environment and runs the YAAMT CLI

.venv\Scripts\python.exe src\yaamt.py %*
