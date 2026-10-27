"""Retira o antigo HUD gerido da pasta carregada pelo CSP, preservando seus dados."""
from pathlib import Path

from . import file_io as safe


def remove_managed(package, game):
    """Chamador mantém active.lock e já validou o vínculo, antes de abrir o menu."""
    package, game = Path(package), Path(game)
    folder = game/'apps/lua/GT7HUD'
    receipt = package/'launcher/gt7-hud.json'
    legacy = package/'launcher/gt7-hud-112.json'
    for path in (folder, receipt, legacy):
        safe.check_components(path)
    if not folder.exists():
        return
    record_path = receipt if receipt.exists() else legacy
    if not record_path.exists():
        return
    record = safe.read_json(record_path)
    if (record.get('schema_version') != 1
            or record.get('version') not in ('1.1.2', '1.3.1')
            or record.get('status') not in ('ready', 'installing')
            or record.get('folder') != str(folder)
            or record.get('state_folder') != str(package/'launcher/gt7-hud-data')):
        raise ValueError('Retired HUD receipt differs; preserve existing files')
    destination = game/'apps/retired/GT7HUD'
    safe.check_components(destination)
    if destination.exists():
        raise FileExistsError('Retired HUD backup already exists; preserve both copies')
    destination.parent.mkdir(parents=True, exist_ok=True)
    folder.rename(destination)
