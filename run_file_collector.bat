@ECHO OFF

:: --- Licensing & Core Environment ---
set foundry_LICENSE=4101@URJA-MC-02
set ADSKFLEX_LICENSE_FILE=2080@URJA-MC-02

:: --- Path Definitions ---
set "KATANA_ROOT=C:\Program Files\Katana8.0v4"
set "KTOA_ROOT=C:\Users\render\ktoa\ktoa-4.4.3.1-kat8.0-windows"
set DEFAULT_RENDERER=arnold
set "KATANA_TAGLINE=With KtoA 4.4.3.1 and Arnold 7.4.3.1"
set "KATANAUSD_ROOT=%KATANA_ROOT%\plugins\Resources\Usd"

:: --- System Path & Resources ---
set USD_KATANA_ALLOW_CUSTOM_MATERIAL_SCOPES=true
set "path=%KTOA_ROOT%\bin;%KATANAUSD_ROOT%\lib;%KATANAUSD_ROOT%\plugin\Libs;%path%"
set "KATANA_RESOURCES=%KTOA_ROOT%;%KATANAUSD_ROOT%\plugin;%KTOA_ROOT%\USD\KatanaUsdArnold;%KATANA_RESOURCES%"
set "FNPXR_PLUGINPATH=%KTOA_ROOT%\USD\Viewport;%FNPXR_PLUGINPATH%"
set "PYTHONPATH=%KATANAUSD_ROOT%\lib\python;%PYTHONPATH%"

:: --- Headless Analysis Implementation ---
:: Check if enough arguments were provided
if "%~2"=="" (
    echo [ERROR] Missing arguments.
    echo Usage: analyze_assets.bat ^<input_file.katana^> ^<output_list.txt^>
    pause
    exit /b
)

set INPUT_KATANA=%1
set OUTPUT_FILE=%2
set SCRIPT_PATH="\\172.17.116.185\renderprod\Data\Naba\Dev\Katana\Scripts\data_collector.py"

echo [INFO] Starting Headless Asset Analysis...

:: Launch Katana in Script Mode
"%KATANA_ROOT%\bin\katanaBin.exe" --script %SCRIPT_PATH% -- %INPUT_KATANA% %OUTPUT_FILE%

echo [INFO] Analysis Complete.