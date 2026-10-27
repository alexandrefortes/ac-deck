"""Prepara cópias verificadas e os arquivos locais de um pacote do jogo.

A política de seleção, diretório de saída e recibo pertence à preparação;
os mecanismos de filesystem pertencem a file_io.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import sys

from . import file_io as safe, game_config


ROOT = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
        else Path(__file__).resolve().parents[2])
BATCH_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
ROOT_FILES = ('acs.exe', 'fmod64.dll', 'fmodstudio64.dll', 'steam_api64.dll', 'python33.zip')
DIRECTORIES = ('system', 'cfg', 'content/cars/abarth500', 'content/tracks/magione',
               'content/weather/3_clear', 'content/objects3D', 'content/driver',
               'content/texture', 'content/fonts', 'content/sfx', 'content/gui',
               'apps/python/system')
REQUIRED = ROOT_FILES + ('system/cfg/inireaderdocuments.ini', 'cfg/video.ini', 'cfg/controls.ini',
                         'content/cars/abarth500/data.acd', 'content/cars/abarth500/abarth500.kn5',
                         'content/cars/abarth500/skins/0_white_scorpion/skin.ini',
                         'content/tracks/magione/magione.kn5', 'content/tracks/magione/models.ini')


def local_destination(project: Path, area: str, path: str | Path,
                       source: Path) -> Path:
    project = safe.absolute(project)
    raw = Path(path)
    destination = safe.absolute(raw if raw.is_absolute() else project / raw)
    allowed = project / "local" / area
    if destination == allowed or not safe.inside(destination, allowed):
        raise safe.SafetyError(f"Saída deve ser uma pasta nova dentro de {allowed}")
    if safe.inside(destination, source):
        raise safe.SafetyError("Saída não pode ficar dentro da origem")
    safe.check_components(destination)
    if destination.exists():
        raise safe.SafetyError(f"Destino já existe; nada será sobrescrito: {destination}")
    return destination


def validate_expected(path: Path, expected: dict) -> tuple[str, os.stat_result]:
    digest = expected.get("sha256")
    if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
        raise safe.SafetyError("Importação exige SHA-256 no inventário para cada arquivo selecionado; use --hashes")
    actual, info = safe.hash_reference_file(path)
    if (actual != digest or info.st_size != expected.get("size_bytes")
            or info.st_mtime_ns != expected.get("mtime_ns")):
        raise safe.SafetyError(f"Origem mudou desde o inventário: {path}")
    return actual, info


def selected_files(source, *, full_content=False):
    """Percorre apenas o envelope; não segue links nem escolhe outras skins."""
    paths = set(ROOT_FILES)
    directories = ('system', 'cfg', 'content', 'apps/python/system') if full_content else DIRECTORIES
    pending = [source / name for name in directories]
    while pending:
        directory = pending.pop()
        safe.check_components(directory)
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(source).as_posix()
            info = path.lstat()
            if safe.linked(info):
                raise safe.SafetyError('Link na seleção: ' + relative)
            if 'conflicted copy' in relative or '/Drivers_oculus/' in relative:
                continue
            if not full_content and relative.startswith('content/cars/abarth500/skins/'):
                if not (relative == 'content/cars/abarth500/skins/0_white_scorpion'
                        or relative.startswith('content/cars/abarth500/skins/0_white_scorpion/')):
                    continue
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            elif stat.S_ISREG(info.st_mode):
                safe.require_reference(info, path)
                paths.add(relative)
            else:
                raise safe.SafetyError('Entrada não regular: ' + relative)
    for relative in REQUIRED:
        safe.hash_reference_file(source / relative)
        if relative not in paths:
            raise safe.SafetyError('Recurso obrigatório ausente da seleção: ' + relative)
    return sorted(paths)


def prepare(game_source, batch, *, project_root=ROOT, full_content=False, progress=None):
    source = safe.source_root(game_source)
    if not BATCH_PATTERN.fullmatch(batch):
        raise safe.SafetyError('Lote inválido')
    destination = local_destination(project_root, 'work', Path('local/work')/batch, source)
    selection = selected_files(source, full_content=full_content)
    rows = []
    for index, relative in enumerate(selection):
        digest, info = safe.hash_reference_file(source/relative)
        rows.append({'relative_path': relative, 'sha256': digest,
                     'size_bytes': info.st_size, 'mtime_ns': info.st_mtime_ns})
        if progress and index % 500 == 0:
            progress('Conferindo origem', index, len(selection))
    if full_content:
        existing = destination.parent
        while not existing.exists():
            existing = existing.parent
        required_bytes = sum(row['size_bytes'] for row in rows)
        if shutil.disk_usage(existing).free < required_bytes + 512 * 1024 * 1024:
            raise safe.SafetyError('Espaço livre insuficiente para a cópia completa; nenhuma cópia iniciada')
    destination.mkdir(parents=True)
    game = destination/'game'
    game.mkdir()
    record = {'schema_version': 1, 'kind': 'deck_practice', 'status': 'preparing',
              'created_utc': datetime.now(timezone.utc).isoformat(), 'source': str(source),
              'package': str(destination), 'official_origin_status': 'not_verified',
              'selection': rows, 'copied': [], 'profile_sha256': {},
              'steam_started': False, 'game_started': False, 'sandbox_required': False}
    record['content_scope'] = 'installed_content' if full_content else 'abarth_magione_practice'
    try:
        for index, row in enumerate(rows):
            relative = row['relative_path']
            validate_expected(source/relative, row)
            safe.copy_verified(source/relative, game/relative, row['sha256'])
            record['copied'].append(relative)
            if progress and index % 500 == 0:
                progress('Copiando conteúdo', index, len(rows))
        for row in rows:
            validate_expected(source/row['relative_path'], row)
        if full_content and selected_files(source, full_content=True) != selection:
            raise safe.SafetyError('Seleção da origem mudou durante a cópia completa')
        cfg = game/'state/Assetto Corsa/cfg'
        cfg.mkdir(parents=True)
        texts = game_config.profile_texts(game)
        for path in sorted((game/'cfg').rglob('*')):
            if path.is_file() and path.relative_to(game/'cfg').as_posix() not in texts:
                target = cfg/path.relative_to(game/'cfg')
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(path.read_bytes())
        for name, raw in texts.items():
            with (cfg/name).open('xb') as stream:
                stream.write(raw)
            record['profile_sha256'][name] = hashlib.sha256(raw).hexdigest()
        for name in ('out','logs','replay','screens','setups'):
            (cfg.parent/name).mkdir()
        ini = game/'system/cfg/inireaderdocuments.ini'
        record['folder_ini_before_sha256'] = hashlib.sha256(ini.read_bytes()).hexdigest()
        # Edição apenas da cópia recém-criada, não da instalação Steam.
        ini.write_bytes(b'[FOLDER]\nBYPASS_DOCUMENT_FOLDER=1\nPROGRAM_NAME=Assetto Corsa\nCUSTOM_PATH=state/Assetto Corsa\n')
        record['status'] = 'prepared'
    except Exception as exc:
        record['status'] = 'failed'
        record['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        safe.write_new_json(destination/'prepared.json', record)
    return destination
