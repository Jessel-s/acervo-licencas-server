@echo off
color 0B
echo =======================================================
echo   GERADOR DE EXECUTAVEL BLINDADO (MODO COMERCIAL)
echo =======================================================
echo.
echo [1/3] Instalando PyInstaller (Ferramenta de compilacao)...
pip install pyinstaller
echo.

echo [2/3] Criando o executavel unico (.exe)...
echo       Isso protege seu codigo fonte contra alteracoes.
echo.
:: O comando abaixo cria um EXE unico, inclui as pastas necessarias e esconde o console se quiser (neste caso mantemos o console para ver o IP)
pyinstaller --noconfirm --onefile --console --name "SistemaAtivos" --add-data "templates;templates" --add-data "static;static" app.py

echo.
echo [3/3] Limpeza de arquivos temporarios...
rmdir /s /q build
del /q SistemaAtivos.spec

echo.
echo =======================================================
echo   SUCESSO! O arquivo 'SistemaAtivos.exe' esta na pasta 'dist'.
echo   Para vender: Entregue apenas o .exe e a pasta 'dist'.
echo =======================================================
pause