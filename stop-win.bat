@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\win-stop.ps1" %*
