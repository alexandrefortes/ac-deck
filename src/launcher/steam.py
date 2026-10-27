"""Adapta a invocação e o ambiente Steam/Proton preservando a identidade real."""
import os
from pathlib import Path
import sys

from . import file_io as safe


def steam_command(command, source, package):
    """Conserva runtime/verb/argumentos; troca exatamente um alvo conhecido."""
    original = str(Path(source)/'AssettoCorsa.exe')
    if not command or any(not isinstance(v,str) or not v or '\0' in v for v in command):
        raise ValueError('Comando Steam vazio ou inválido')
    if '%command%' in command:
        raise ValueError('A Steam precisa expandir %command%. Cole esta linha em '
                         'Assetto Corsa > Propriedades > Geral > Opções de inicialização '
                         'na Steam e clique em Jogar.')
    positions = [i for i,v in enumerate(command) if v == original]
    if len(positions) != 1:
        raise ValueError('Esperado exatamente um AssettoCorsa.exe da instalação declarada')
    index = positions[0]
    if index < 2 or command[index-1] not in ('run','waitforexitandrun') or Path(command[index-2]).name != 'proton':
        raise ValueError('O alvo não está numa invocação Proton reconhecida')
    result = list(command)
    result[index] = str(Path(package)/'game/acs.exe')
    return result


def steam_environment(environment, package):
    if environment.get('SteamAppId') != '244210':
        raise ValueError('Inicie pela entrada Assetto Corsa da Steam; AppID não será fabricado')
    if environment.get('SteamGameId', '244210') != '244210':
        raise ValueError('Contexto Steam divergente')
    if not environment.get('STEAM_COMPAT_DATA_PATH'):
        raise ValueError('Prefixo Steam/Proton ausente; não iniciar runtime separado')
    result = dict(environment)
    result['STEAM_COMPAT_INSTALL_PATH'] = str(Path(package)/'game')
    for name in ('PYTHONHOME','PYTHONOPTIMIZE','PYTHONPATH'):
        result.pop(name, None)
    return result


def run_from_steam(package, command):
    if sys.platform != 'linux':
        raise ValueError('Execução desta entrada requer Linux e a Steam')
    package = safe.source_root(package)
    record = safe.read_json(package/'prepared.json')
    if record.get('kind') != 'deck_practice' or record.get('status') != 'prepared':
        raise ValueError('Preparação não concluída')
    argv = steam_command(command, record['source'], package)
    environment = steam_environment(os.environ, package)
    expected = next(row['sha256'] for row in record['selection'] if row['relative_path']=='acs.exe')
    digest, _ = safe.hash_reference_file(package/'game/acs.exe')
    if digest != expected:
        raise ValueError('Executável da cópia mudou')
    os.chdir(package/'game')
    os.execvpe(argv[0], argv, environment)
