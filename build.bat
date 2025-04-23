@echo off
REM === 1) Nettoyage avant build ===
if exist build      rd /s /q build
if exist dist       rd /s /q dist
if exist yt_gui.spec del    /q yt_gui.spec

REM === 2) Activation du venv local ===
call dependances\Scripts\activate.bat

REM === 3) Build ONEFILE avec PyInstaller ===
dependances\Scripts\pyinstaller.exe ^
  --onefile ^
  --windowed ^
  --icon "icons\logo.ico" ^
  --add-data "icons;icons" ^
  --add-binary "dependances\Scripts\yt-dlp.exe;." ^
  --add-binary "dependances\Scripts\ffmpeg.exe;." ^
  yt_gui.py
if errorlevel 1 (
  echo [ERROR] La compilation a échoue.
  pause
  exit /b 1
)

REM === 4) Copier config.ini à côté de l'exe ===
copy /Y config.ini dist\

REM === 5) Cleanup après build ===
if exist build      rd /s /q build
if exist yt_gui.spec del    /q yt_gui.spec

echo.
echo [OK] Build terminé !
echo   - EXE : dist\yt_gui.exe
echo   - INI : dist\config.ini
pause
