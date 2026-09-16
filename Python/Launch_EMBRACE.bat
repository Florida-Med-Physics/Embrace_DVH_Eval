@echo off
cd /d "%~dp0"
py EMBRACE2_EQD2_Excel_Autogenerator.py
if errorlevel 1 pause
