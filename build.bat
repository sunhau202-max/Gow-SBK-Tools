@echo off
title Build GoW WAD SBK Tool
python -m pip install --upgrade pip pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name GoW_SBK_Tool gow_wad_sbk_tool.py
echo.
echo Selesai. Hasil: dist\GoW_SBK_Tool.exe
pause
