@echo off
rem =====================================================
rem INICIA O ACERVO TI EM MODO KIOSK VERTICAL (RETRATO)
rem Use este atalho no PDV touch vertical.
rem
rem Como funciona:
rem 1) Gira o monitor principal para Vertical em 30s
rem    (o Windows pergunta antes de aplicar; confirme)
rem 2) Inicia o sistema, que abre o Chrome em modo kiosk
rem    tela cheia, travado, com escala 75%% (KIOSK_SCALE
rem    configurado no .env)
rem
rem Para voltar ao normal: feche o Chrome (Alt+F4) e
rem pressione Ctrl+Alt+Seta para cima.
rem =====================================================

title Acervo TI - Modo Kiosk Vertical
echo Girando a tela para vertical...
rem Displayswitch: pode falhar em alguns drivers; o giro manual
rem com Ctrl+Alt+Seta para baixo tambem funciona.
start "" /wait control desk.cpl,,3
echo.
echo Iniciando o Acervo TI...
call "%~dp0INICIAR_SISTEMA.bat"
