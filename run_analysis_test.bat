@ECHO OFF
REM Test script to demonstrate Katana analysis workflow
REM This would normally call katanaBin.exe --script analyze_katana.py -- <input.katana> <output_dir>

echo [INFO] Starting Katana Analysis Test...
echo [INFO] This test demonstrates the workflow that would be used in production

REM Set up paths
set INPUT_KANANA=Samples\sample.katana
set OUTPUT_DIR=renderfarm_test

REM Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo [INFO] Input file: %INPUT_KANANA%
echo [INFO] Output directory: %OUTPUT_DIR%

REM In a real environment, this would be:
REM "C:\Program Files\Katana8.0v4\bin\katanaBin.exe" --script analyze_katana.py -- %INPUT_KANANA% %OUTPUT_DIR%

REM For testing purposes, we'll just show what the command would be
echo [INFO] In production, this would execute:
echo [INFO] katanaBin.exe --script analyze_katana.py -- %INPUT_KANANA% %OUTPUT_DIR%
echo [INFO] 
echo [INFO] The analysis script would generate:
echo [INFO]   - %OUTPUT_DIR%\create_log.txt
echo [INFO]   - %OUTPUT_DIR%\katana_file_list.txt  
echo [INFO]   - %OUTPUT_DIR%\web_ui_data.json

echo [INFO] Test completed.