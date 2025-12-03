@echo off
REM Автозапуск VoiceCapture при старте Windows
REM Предполагается, что проект находится в E:\PO\PHYTON\Voice
REM и используется глобальное окружение Python 3.12 (без venv)

cd /d E:\PO\PHYTON\Voice

REM Показываем, каким Python запускаем приложение
echo Starting VoiceCapture with system Python...
python --version
echo.

REM Запускаем распознаватель и не скрываем ошибки
python src\main.py
pause