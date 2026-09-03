import os
import subprocess
import shutil
import sys

# Garante que o script rode na pasta correta do projeto, independente de onde for chamado
os.chdir(os.path.abspath(os.path.dirname(__file__)))

print("=== INICIANDO BLINDAGEM E COMPILACAO DO ACERVO TI ===")

# 1. Instalar ferramentas garantindo que estão atualizadas
print("\n1. Instalando todas as dependencias do projeto via requirements.txt...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

# 2. Obfuscar o código fonte
print("\n2. Blindando o codigo fonte com PyArmor...")
arquivos_py = (
    "app.py auth.py database.py inventory.py maintenance.py movements.py settings.py "
    "storeroom.py utils.py models.py availability.py backup.py database_local.py "
    "licenca_manager.py supabase_login.py supabase_session.py sync_queue.py "
    "sync_supabase.py restaurar_supabase.py configurar_cliente.py"
)
subprocess.run(f"pyarmor gen -O blindado {arquivos_py}", shell=True)

# 3. Copiar interface e pastas necessárias
print("\n3. Copiando arquivos de interface para a area segura...")
for pasta in ['templates', 'static']:
    if os.path.exists(pasta):
        shutil.copytree(pasta, f"blindado/{pasta}", dirs_exist_ok=True)

    shutil.copy2('.env.example', 'blindado/.env.example')

# 4. Encontrar a biblioteca criptografada que o PyArmor gera
try:
    runtime_folder = [f for f in os.listdir('blindado') if f.startswith('pyarmor_runtime_')][0]
except IndexError:
    print("Erro: Pasta do PyArmor runtime nao encontrada. A blindagem falhou.")
    exit(1)

# 5. Compilar tudo em .exe usando PyInstaller
print("\n4. Gerando o Executavel (.exe) protegido...")
os.chdir('blindado')

# --- CORREÇÃO CRÍTICA: Força a inclusão da DLL do Python ---
# PyInstaller pode se perder com o código ofuscado e não incluir o motor principal do Python.
py_version_str = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
python_dll_path = os.path.join(os.path.dirname(sys.executable), py_version_str)

if not os.path.exists(python_dll_path):
    print(f"\n[ERRO CRÍTICO] A DLL do Python '{py_version_str}' não foi encontrada em '{os.path.dirname(sys.executable)}'.")
    print("O build não pode continuar. Verifique a integridade da sua instalação do Python.")
    exit(1)

pyinstaller_args = [
    'pyinstaller',
    '--name', 'AcervoTI',
    '--add-data', 'templates;templates',
    '--add-data', 'static;static',
    '--add-data', '../templates/ticket_58mm.html;templates', # Inclui o template usado pela rota de impressão
    '--add-data', '../license_secret.bin;.', # CRÍTICO: Inclui a chave secreta para validação de licença
    '--add-data', '../arialbd.ttf;.',
    '--add-data', f'{runtime_folder};{runtime_folder}',
    '--add-binary', f'{python_dll_path};_internal',
    '--icon', '../static/favicon.png',
    '--windowed',
    '--noconfirm',
    # Lista de imports ocultos para o PyInstaller encontrar dentro do código blindado
    # Coleta de dados de pacotes complexos
    '--collect-data', 'lxml',
    '--collect-data', 'pytz',
    '--collect-data', 'tzdata',
    # Imports que o PyInstaller pode ter dificuldade de achar em código ofuscado
    '--hidden-import', 'cryptography',
    '--hidden-import', 'cryptography.fernet',
    '--hidden-import', 'PIL.Image',
    '--hidden-import', 'pandas._libs.tslibs.base',
    '--hidden-import', 'werkzeug.security',
    '--hidden-import', 'logging.handlers',
    '--hidden-import', 'requests',
    '--hidden-import', 'dotenv',
    '--hidden-import', 'supabase',
    # Módulos do próprio projeto
    '--hidden-import', 'auth', '--hidden-import', 'database', '--hidden-import', 'inventory',
    '--hidden-import', 'utils', '--hidden-import', 'maintenance', '--hidden-import', 'movements', '--hidden-import', 'storeroom',
    '--hidden-import', 'settings', '--hidden-import', 'models', '--hidden-import', 'availability', '--hidden-import', 'backup',
    '--hidden-import', 'database_local', '--hidden-import', 'licenca_manager', '--hidden-import', 'supabase_login',
    '--hidden-import', 'supabase_session', '--hidden-import', 'sync_queue', '--hidden-import', 'sync_supabase',
    # Arquivo de entrada
    'app.py'
]

try:
    subprocess.run(pyinstaller_args, check=True)
    subprocess.run([
        'pyinstaller', '--name', 'ConfigurarCliente', '--console', '--onefile', '--noconfirm',
        '--hidden-import', 'cryptography.fernet', '--hidden-import', 'dotenv',
        'configurar_cliente.py',
    ], check=True)
except subprocess.CalledProcessError:
    print("\n[ERRO CRITICO] A compilacao falhou! Verifique os erros no texto acima.")
    exit(1)

print("\n=== SUCESSO! ===")
print(f"Seu sistema blindado esta pronto na pasta: {os.path.abspath(os.path.join('dist', 'AcervoTI'))}")