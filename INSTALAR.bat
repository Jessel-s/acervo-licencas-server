@echo off
color 0A
echo ==================================================
echo      INSTALADOR DO SISTEMA DE ATIVOS
echo ==================================================
echo.
echo [1/2] Verificando e atualizando o instalador (PIP)...
python -m pip install --upgrade pip
echo.
echo [2/2] Instalando bibliotecas necessarias...
pip install -r requirements.txt
echo.
echo ==================================================
echo      INSTALACAO CONCLUIDA COM SUCESSO!
echo ==================================================
echo.
echo Agora voce ja pode usar o arquivo 'INICIAR_SISTEMA.bat'
pause