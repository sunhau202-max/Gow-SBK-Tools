@echo off
title Build - Gow SBK Tools by Nicho
python -m pip install --upgrade pip pyinstaller
python -m PyInstaller --noconfirm --onedir --windowed --name SBK_Tools --icon icon.ico gow_wad_sbk_tool.py
if errorlevel 1 goto fail

rem Rakit paket: SBK Tools\ (folder program) + txt di sebelahnya
if exist "paket" rmdir /s /q "paket"
mkdir "paket"
xcopy /e /i /y "dist\SBK_Tools" "paket\SBK Tools" >nul
for %%F in (Readme-Indo.txt Readme-Eng.txt Leia-me-Br.txt Informasi-Indo.txt Information-Eng.txt Informacoes-Br.txt Katalog_SBK.txt) do copy /y "%%F" "paket\" >nul
echo.
echo Selesai. Hasil ada di folder "paket" (zip isinya menjadi "SBK Tools.zip").
pause
exit /b 0

:fail
echo Build gagal.
pause
exit /b 1
