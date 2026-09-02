[Setup]
; Configurações Gerais do Instalador
; AppId garante que futuras atualizações substituam a versão antiga corretamente
AppId={{ACERVO-TI-APP-ID-1000}
AppName=Acervo TI
AppVersion=1.0
AppPublisher=Seu Nome ou Sua Empresa
DefaultDirName={autopf}\Acervo TI
DefaultGroupName=Acervo TI
DisableProgramGroupPage=yes
OutputDir=InstaladorFinal
OutputBaseFilename=Instalar_AcervoTI
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Dirs]
; [IMPORTANTE] Concede permissão total de escrita na pasta de instalação.
; Necessário para que o sistema possa criar/modificar o banco de dados (patrimonio_ti.db),
; a licença (licenca.key) e os logs (sistema_erros.log) sem erros de "Acesso Negado".
Name: "{app}"; Permissions: users-full

[Tasks]
; Opção para criar atalho na área de trabalho
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Ícones Adicionais:"

[Files]
; Copia TODO o conteúdo da pasta de build (gerada pelo build_seguro.py) para a pasta de instalação do cliente.
; A flag 'recursesubdirs' garante que as pastas 'templates' e 'static' sejam incluídas.
Source: "blindado\dist\AcervoTI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Cria os atalhos no Menu Iniciar e na Área de Trabalho
Name: "{group}\Acervo TI"; Filename: "{app}\AcervoTI.exe"
Name: "{group}\Desinstalar Acervo TI"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Acervo TI"; Filename: "{app}\AcervoTI.exe"; Tasks: desktopicon

[Run]
; Inicia o sistema automaticamente após a instalação
Filename: "{app}\AcervoTI.exe"; Description: "Iniciar o Acervo TI agora"; Flags: nowait postinstall skipifsilent
