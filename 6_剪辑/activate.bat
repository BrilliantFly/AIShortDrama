@echo off
set "CUTDIR=%~dp0"
set "PATH=%CUTDIR%tools\ffmpeg;%PATH%"
echo.
echo ==== AIShortDrama edit environment ====
echo ffmpeg path: %CUTDIR%tools\ffmpeg
echo.
where ffmpeg
where ffprobe
echo.
echo Ready. Examples:
echo   ffmpeg -version
echo   python "%CUTDIR%tools\drama-edit\scripts\edit_tool.py" --help
echo.
cmd /k
