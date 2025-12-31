@echo off
REM Автозапуск VoiceCapture при старте Windows
REM Предполагается, что проект находится в текущей директории
REM и используется глобальное окружение Python 3.12 (без venv)

cd /d "%~dp0"

REM Показываем, каким Python запускаем приложение
echo Starting VoiceCapture with system Python...
python --version
echo.

REM Запускаем распознаватель и не скрываем ошибки
python src\main.py
pause