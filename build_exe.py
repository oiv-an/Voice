import PyInstaller.__main__
import shutil
from pathlib import Path
import os

def build():
    # Очистка предыдущих сборок
    if Path("dist").exists():
        shutil.rmtree("dist")
    if Path("build").exists():
        shutil.rmtree("build")
    
    # Создаем папку build заранее, чтобы избежать ошибки FileNotFoundError
    Path("build").mkdir(exist_ok=True)

    # Параметры PyInstaller
    args = [
        "src/main.py",  # Точка входа
        "--name=VoiceCapture",  # Имя exe
        "--onefile",  # Один файл
        "--noconsole",  # Без консоли (GUI приложение)
        "--clean",  # Очистка кэша
        
        # Добавляем ассеты (иконки и т.д.)
        "--add-data=assets;assets",
        
        # Скрытые импорты, которые PyInstaller может не найти
        "--hidden-import=pynput.keyboard._win32",
        "--hidden-import=pynput.mouse._win32",
        "--hidden-import=pyperclip",
        "--hidden-import=yaml",
        "--hidden-import=loguru",
        
        # Иконка приложения (если есть)
        # "--icon=assets/icon.ico", 
    ]

    print("Starting build with PyInstaller...")
    PyInstaller.__main__.run(args)
    print("Build finished!")

if __name__ == "__main__":
    build()