"""Usa a instalação Steam diretamente; guarda só catálogo/configuração local."""
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import sys
import uuid

from . import file_io as safe, game_config, package_setup
from . import content


def attach(source, batch, *, project_root):
    source = safe.source_root(source)
    if not package_setup.BATCH_PATTERN.fullmatch(batch):
        raise ValueError('Lote inválido')
    package = package_setup.local_destination(project_root,'work',Path('local/work')/batch,source)
    # Somente o executável e os quatro INIs pequenos; nenhum asset é copiado.
    references = []
    for name in ('acs.exe','cfg/video.ini','cfg/controls.ini'):
        sha, info = safe.hash_reference_file(source/name)
        references.append(dict(relative_path=name,sha256=sha,size_bytes=info.st_size))
    texts = game_config.profile_texts(source)
    catalog = content.scan(source)
    package.mkdir(parents=True)
    cfg = package/'cfg'
    cfg.mkdir()
    for name,data in texts.items():
        with (cfg/name).open('xb') as stream:
            stream.write(data)
    safe.write_new_json(package/'catalog.json',catalog)
    record = dict(schema_version=1,kind='deck_installed_game',status='prepared',
        content_scope='installed_content',game_mode='installed',source=str(source),
        selection=references,created_utc=datetime.now(timezone.utc).isoformat(),
        game_copied=False,steam_started=False,game_started=False,official_origin_status='not_verified')
    safe.write_new_json(package/'prepared.json',record)
    return package


def game_path(package, record):
    if record.get('game_mode') == 'installed':
        return safe.source_root(record['source'])
    return safe.source_root(Path(package)/'game')


def load_catalog(package, game, *, refresh=False):
    """Renova uma vez o catálogo legado, sob a trava do launcher.

    Preserva os bytes anteriores em cópia independente. Não copia o jogo,
    altera a seleção ou modifica os metadados de origem.
    refresh=True atualiza o snapshot em memória na abertura do produto,
    sem regravar um catálogo que já usa o formato atual.
    """
    package = safe.source_root(package)
    path = package/'catalog.json'
    catalog = safe.read_json(path)
    version = catalog.get('catalog_version')
    if version == content.CATALOG_VERSION:
        if not refresh:
            return catalog
        updated=content.scan(game)
        if not updated['cars'] or not updated['tracks'] or not updated['weather']:
            raise ValueError('Cannot refresh catalog: installed content is incomplete')
        return updated
    if type(version) is int and version > content.CATALOG_VERSION:
        raise ValueError('Catalog was created by a newer launcher')
    safe.require_reference(path.lstat(),path)
    before = path.read_bytes()
    updated = content.scan(game)
    if not updated['cars'] or not updated['tracks'] or not updated['weather']:
        raise ValueError('Cannot refresh catalog: installed content is incomplete')
    token = uuid.uuid4().hex
    backup = package/('catalog-previous-'+token+'.json')
    temporary = package/('catalog-refresh-'+token+'.json')
    safe.write_new_json(temporary,updated)
    safe.check_components(path)
    safe.require_reference(path.lstat(),path)
    if path.read_bytes() != before:
        raise ValueError('Catalog changed during refresh; previous file preserved')
    with backup.open('xb') as stream:
        stream.write(before)
    temporary.replace(path)
    return updated


def documents(environment):
    prefix = environment.get('STEAM_COMPAT_DATA_PATH')
    if not prefix:
        raise ValueError('Prefixo Steam/Proton ausente')
    anchor = Path(prefix)/'pfx/drive_c/users/steamuser/Documents'
    if not anchor.is_dir():
        raise ValueError('Documents do Proton ainda não existe; abra o jogo uma vez pela Steam')
    # O link Documents é criado normalmente pelo Proton, não é uma importação.
    return anchor.resolve(strict=True)


def config_path(game, environment, explicit=None):
    if explicit is not None:
        path = safe.absolute(explicit)
    else:
        game = safe.absolute(game)
        config = game/'system/cfg/inireaderdocuments.ini'
        safe.check_components(config)
        folders = game_config.parse_ini(config)
        custom = folders.get('FOLDER','CUSTOM_PATH',fallback='')
        if custom:
            base = game/safe.relative_file(custom)
        elif folders.getint('FOLDER','BYPASS_DOCUMENT_FOLDER',fallback=0) == 1:
            base = game
        else:
            program = folders.get('FOLDER','PROGRAM_NAME',fallback='Assetto Corsa')
            base = documents(environment)
            if program:
                base /= safe.relative_file(program)
        path = base/'cfg'
    safe.check_components(path)
    return path


def remove_copy(package, *, execute=False):
    """Limpa só game/ de um lote copiado, com o menu parado. Preserva state/."""
    if sys.platform != 'linux':
        raise ValueError('A limpeza da cópia é um comando Linux para o Deck')
    import fcntl
    package = safe.source_root(package)
    record = safe.read_json(package/'prepared.json')
    if (record.get('status') != 'prepared' or record.get('content_scope') != 'installed_content'
            or record.get('kind') != 'deck_practice' or record.get('game_mode') == 'installed'):
        raise ValueError('Limpeza aceita somente o lote de cópia completa, nunca a instalação original')
    game = safe.source_root(package/'game')
    source = safe.source_root(record['source'])
    if (game.parent != package or game == source or game.is_relative_to(source)
            or source.is_relative_to(game) or source.is_relative_to(package)):
        raise ValueError('Destino de limpeza confunde cópia e original')
    expected = next(row['sha256'] for row in record['selection'] if row['relative_path']=='acs.exe')
    if safe.hash_reference_file(game/'acs.exe')[0] != expected:
        raise ValueError('Executável da cópia diverge; não apagar este diretório')
    # Sem seguir links durante a verificação ou a exclusão recursiva.
    for folder, directories, files in os.walk(game, followlinks=False):
        for name in directories+files:
            path=Path(folder)/name
            if safe.linked(path.lstat()):
                raise ValueError('Link inesperado na cópia; limpeza interrompida: '+str(path))
    result=dict(target=str(game),source_preserved=str(source),executed=False,
                game_data_preserved=None)
    if not execute:
        return result
    lock=package/'launcher/active.lock'
    safe.check_components(lock)
    lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a+b') as stream:
        safe.require_reference(os.fstat(stream.fileno()),lock)
        try:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('O menu desta cópia ainda está em uso; feche-o antes da limpeza') from error
        state=game/'state'
        if state.exists():
            preserved=package/('dados-da-copia-'+uuid.uuid4().hex[:8])
            if not preserved.resolve().is_relative_to(package):
                raise ValueError('Destino de dados fora do lote')
            state.rename(preserved)
            result['game_data_preserved']=str(preserved)
        shutil.rmtree(game)
        result['executed']=True
        safe.write_new_json(package/('copy-removed-'+uuid.uuid4().hex[:8]+'.json'),result)
    return result
