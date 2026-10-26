@echo off
REM Build lokal di Windows (butuh Python 3.10+). Hasil: dist\NotchIsland\NotchIsland.exe
python -m pip install --upgrade pip
pip install pyinstaller -r requirements.txt
pyinstaller --noconfirm --clean --onedir --noconsole --icon assets\icon.ico --name NotchIsland --collect-submodules winrt --hidden-import winrt.windows.media.control --hidden-import winrt.windows.storage.streams --hidden-import winrt.windows.ui.notifications --hidden-import winrt.windows.ui.notifications.management --hidden-import PIL.ImageTk notch_island.py
echo.
echo Selesai. Jalankan: dist\NotchIsland\NotchIsland.exe
echo Untuk installer, buka installer\NotchIsland.iss dengan Inno Setup lalu Compile.
pause
