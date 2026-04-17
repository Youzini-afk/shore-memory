@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\win-build.ps1" %*
