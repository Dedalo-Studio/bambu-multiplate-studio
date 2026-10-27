@echo off
if exist "%~dp0dist\BambuPlateMerger\BambuPlateMerger.exe" (
    start "" "%~dp0dist\BambuPlateMerger\BambuPlateMerger.exe" %*
) else (
    start "" pythonw "%~dp0bambu_merger_app.py" %*
)
