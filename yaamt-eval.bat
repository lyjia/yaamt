@echo off
REM YAAMT Analyzer Evaluation launcher for Windows
REM This script activates the virtual environment and runs the analyzer evaluator

.venv\Scripts\python.exe src\yaamt-eval.py %*
