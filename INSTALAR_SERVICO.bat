@echo off
title Instalador - Gestao de Ativos TI
color 0A
cls
echo ======================================================
echo      INSTALADOR AUTOMATICO - GESTAO DE ATIVOS
echo ======================================================
echo.
echo Este script vai preparar o computador para rodar o sistema.
echo Certifique-se de estar conectado a internet.
echo.
echo Pressione qualquer tecla para comecar...
pause >nul

:: 1. Verifica se o Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado!
    echo Por favor, instale o Python 3.10 ou superior antes de continuar.
    echo Marque a opcao "Add Python to PATH" na instalacao.
    echo.
    pause
    exit
)

echo [OK] Python detectado.
echo.

:: 2. Instala as dependencias do sistema
echo [1/3] Instalando bibliotecas necessarias...
pip install flask pandas openpyxl qrcode pillow waitress pywin32

:: 3. Configura para iniciar com o Windows (Método Startup Folder)
echo [2/3] Criando atalho de inicializacao...

set "SCRIPT_DIR=%~dp0"
set "TARGET_BAT=%SCRIPT_DIR%INICIAR_SISTEMA.bat"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_NAME=%STARTUP_FOLDER%\GestaoAtivosTI.lnk"

:: Cria um script VBS temporário para gerar o atalho
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%temp%\CreateShortcut.vbs"
echo sLinkFile = "%SHORTCUT_NAME%" >> "%temp%\CreateShortcut.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%temp%\CreateShortcut.vbs"
echo oLink.TargetPath = "%TARGET_BAT%" >> "%temp%\CreateShortcut.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%temp%\CreateShortcut.vbs"
echo oLink.Save >> "%temp%\CreateShortcut.vbs"
cscript /nologo "%temp%\CreateShortcut.vbs"
del "%temp%\CreateShortcut.vbs"

echo [3/3] Concluido! O sistema iniciara automaticamente ao ligar o PC.
echo.
echo Pressione qualquer tecla para iniciar o sistema agora...
pause >nul
call "%TARGET_BAT%"