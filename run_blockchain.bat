@echo off
setlocal enabledelayedexpansion

if "%NODE_PORT%"=="" set "NODE_PORT=8224"
set "COMPOSE_FILE=docker-compose.yml"
set "PORT=%NODE_PORT%"
set "BASE_URL=http://localhost:%PORT%"

echo ========================================
echo  Blockchain educational node
echo ========================================
echo  edu-node    %BASE_URL%    (container port 8000)
echo ========================================

call :start_service
if errorlevel 1 goto start_failed
call :show_running
goto show_menu

:show_menu
echo.
echo ==============================
echo   [k] stop, keep images and the chain volume
echo   [q] stop and remove images, keep the chain volume
echo   [v] full cleanup (images, volume, and host .runtime)
echo   [r] restart
echo ==============================

:main_loop
set "CHOICE="
set /p "CHOICE=Enter selection (k/q/v/r): " || goto do_stop
if /I "%CHOICE%"=="k" goto do_stop
if /I "%CHOICE%"=="q" goto do_cleanup
if /I "%CHOICE%"=="v" goto do_cleanup_volumes
if /I "%CHOICE%"=="r" goto do_restart
echo Invalid selection. Enter k, q, v, or r.
goto show_menu

:do_stop
echo.
echo Stopping containers...
docker compose -f "%COMPOSE_FILE%" down
if errorlevel 1 goto command_failed
echo Done.
goto end_script

:do_cleanup
echo.
echo Stopping containers...
docker compose -f "%COMPOSE_FILE%" down --remove-orphans
if errorlevel 1 goto command_failed
call :remove_images
echo Done.
goto end_script

:do_cleanup_volumes
echo.
echo Stopping containers and removing volumes...
docker compose -f "%COMPOSE_FILE%" down --volumes --remove-orphans
if errorlevel 1 goto command_failed
call :remove_images
if exist ".runtime" rmdir /s /q ".runtime"
echo Done.
goto end_script

:do_restart
echo.
echo Restarting...
docker compose -f "%COMPOSE_FILE%" down
if errorlevel 1 goto command_failed
call :start_service
if errorlevel 1 goto start_failed
call :show_running
goto show_menu

:start_service
echo Starting the educational node...
docker compose -f "%COMPOSE_FILE%" up --build -d
if errorlevel 1 exit /b 1
set /a WAITED=0
:start_wait_loop
curl -fsS "%BASE_URL%/health" >nul 2>nul
if not errorlevel 1 goto :eof
timeout /t 1 /nobreak >nul
set /a WAITED+=1
if !WAITED! GEQ 60 (
    echo The educational node did not answer %BASE_URL%/health within 60s.
    echo Check logs with: docker compose -f %COMPOSE_FILE% logs
    exit /b 1
)
goto start_wait_loop

:show_running
echo.
echo Services are running
echo   API:      %BASE_URL%
echo   API docs: %BASE_URL%/docs
echo   Health:   %BASE_URL%/health
goto :eof

:remove_images
echo.
echo Removing images...
for /f "delims=" %%I in ('docker compose -f "%COMPOSE_FILE%" config --images 2^>nul') do (
    echo Found image: %%I
    docker rmi -f "%%I" 2>nul
)
for /f "delims=" %%I in ('docker images --format "{{.Repository}}:{{.Tag}}" ^| findstr /I "blockchain"') do (
    echo Found image: %%I
    docker rmi -f "%%I" 2>nul
)
echo Images removed.
goto :eof

:start_failed
echo Docker Compose did not start.
goto end_script

:command_failed
echo A Docker command failed.
goto end_script

:end_script
pause
exit /b 0
