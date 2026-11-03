"""Prepare an ac-deck installation without launching Steam or the game."""
from pathlib import Path
from contextlib import contextmanager
import hashlib
import re
import stat
import sys
import time
import uuid
import zipfile

from . import community_download, csp, file_io as safe, install_discovery, installed


def _verify_kit(kit, archive):
    """Compare the kit with the selected archive, not only its own manifest."""
    digest, _ = safe.hash_reference_file(archive)
    if digest != csp.ARCHIVE_SHA256:
        raise ValueError('Saved CSP archive does not match the selected SHA-256')
    manifest = csp.verify(kit)
    selected = {row['path']: (row['sha256'], row['size_bytes']) for row in manifest['files']}
    observed, total = {}, 0
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            name = safe.relative_file(item.filename.rstrip('/'))
            if stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
                raise ValueError('Unsupported CSP archive member')
            if item.is_dir():
                continue
            if name in observed:
                raise ValueError('Duplicate CSP archive member')
            total += item.file_size
            if total > 256 * 1024 * 1024:
                raise ValueError('CSP archive contents exceed the extraction limit')
            hashed = hashlib.sha256()
            with source.open(item) as stream:
                while chunk := stream.read(1024 * 1024):
                    hashed.update(chunk)
            observed[name] = (hashed.hexdigest(), item.file_size)
    if observed != selected or safe.hash_reference_file(archive)[0] != digest:
        raise ValueError('CSP kit does not match the selected archive')
    return manifest


def prepare(root, game):
    """Prepare a pinned CSP kit and an attachment to an existing game.

    Existing complete owned data is reused only after verification. Incomplete
    or unknown data is preserved and reported for explicit recovery.
    """
    root = safe.source_root(root)
    game = install_discovery.validate_game(game)
    if csp.VERSION != '0.3.1':
        raise ValueError('Installer requires CSP 0.3.1; this build has not been updated and validated yet')
    kit = root / 'csp'
    package = root / 'local/work/community'
    archive = root / 'local/csp-source.zip'
    safe.check_components(kit)
    safe.check_components(package)
    safe.check_components(archive)
    if kit.exists():
        if not archive.is_file():
            raise ValueError('Existing CSP kit has no verified source archive; it was preserved')
        _verify_kit(kit, archive)
    else:
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            staging = archive.with_name('csp-source-' + uuid.uuid4().hex + '.zip')
            community_download.download(csp.URL, staging, csp.ARCHIVE_SHA256)
            safe.rename_new(staging, archive)
        elif safe.hash_reference_file(archive)[0] != csp.ARCHIVE_SHA256:
            raise ValueError('Existing CSP archive differs; it was preserved')
        staging = archive.parent / ('csp-kit-' + uuid.uuid4().hex)
        csp.unpack(archive, staging)
        _verify_kit(staging, archive)
        safe.rename_new(staging, kit)
    if package.exists():
        record = safe.read_json(package / 'prepared.json')
        if (record.get('kind') != 'deck_installed_game' or record.get('status') != 'prepared'
                or record.get('game_mode') != 'installed' or record.get('source') != str(game)):
            raise ValueError('Existing attachment differs; it has been preserved')
    else:
        package = installed.attach(game, 'community', project_root=root)
    return package


def choose_game(*, prompt=input, output=print):
    """Choose a declared game or accept a path without searching all disks."""
    try:
        found = install_discovery.discover()
    except (OSError, ValueError, safe.SafetyError) as error:
        output('Could not read Steam library metadata: ' + str(error))
        found = []
    if len(found) == 1:
        output('Found Assetto Corsa: ' + str(found[0]))
        return install_discovery.validate_game(found[0])
    if found:
        output('Choose an Assetto Corsa installation:')
        for number, path in enumerate(found, 1):
            output(f'{number}. {path}')
    else:
        output('Install the original Assetto Corsa (Steam App 244210) from Steam first, then run the same command again.')
        output('If it is already installed, you can enter its Steam game folder below.')
    try:
        choice = prompt('Enter a number or the full game folder path (Enter to stop): ').strip()
    except EOFError:
        choice = ''
    if choice.isdecimal() and 1 <= int(choice) <= len(found):
        return install_discovery.validate_game(found[int(choice) - 1])
    if not choice:
        raise ValueError('No game found or selected. Install Assetto Corsa from Steam, then run the same command again.')
    return install_discovery.validate_game(Path(choice).expanduser())


def steam_roots(home=None):
    home = safe.source_root(home if home is not None else Path.home())
    roots = (home / '.local/share/Steam', home / '.steam/steam',
             home / '.var/app/com.valvesoftware.Steam/.local/share/Steam')
    result = []
    for path in roots:
        if path.is_dir():
            root = safe.source_root(path.resolve(strict=True))
            if root not in result:
                result.append(root)
    return result


def preflight_csp(root, game, package):
    """Detect game-side CSP conflicts without modifying the game."""
    manifest = _verify_kit(root / 'csp', root / 'local/csp-source.zip')
    receipt = package / 'launcher/csp.json'
    safe.check_components(receipt)
    if receipt.exists():
        record = safe.read_json(receipt)
        if (record.get('status') == 'ready'
                and csp._known_previous(record.get('version'), record.get('archive_sha256'))):
            # csp.install checks every old/new destination and owns backup/resume.
            return
        if (record.get('status') not in ('installing', 'ready')
                or record.get('version') != csp.VERSION
                or record.get('archive_sha256') != csp.ARCHIVE_SHA256
                or record.get('files') != manifest.get('files')):
            raise ValueError('Existing CSP receipt needs explicit recovery before changing Steam')
        if record.get('previous'):
            previous = record['previous']
            if (record['status'] != 'installing' or not isinstance(previous, dict)
                    or not csp._known_previous(previous.get('version'), previous.get('archive_sha256'))):
                raise ValueError('Existing CSP upgrade receipt needs explicit recovery before changing Steam')
            return
    for row in manifest['files']:
        path = game / safe.relative_file(row['path'])
        safe.check_components(path)
        if path.exists() and csp.digest(path) != row['sha256']:
            raise ValueError('Existing CSP file differs from the required version; it was preserved: ' + str(path))


def preflight_attachment(game, package):
    record = safe.read_json(package / 'prepared.json')
    if (record.get('kind') != 'deck_installed_game' or record.get('status') != 'prepared'
            or record.get('game_mode') != 'installed' or record.get('source') != str(game)):
        raise ValueError('Game attachment does not match; it was preserved')
    selection = record.get('selection')
    if not isinstance(selection, list):
        raise ValueError('Game attachment has no valid executable inventory')
    rows = [row for row in selection if isinstance(row, dict) and row.get('relative_path') == 'acs.exe']
    if (len(rows) != 1 or not isinstance(rows[0].get('sha256'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', rows[0]['sha256'])
            or safe.hash_reference_file(game / 'acs.exe')[0] != rows[0]['sha256']):
        raise ValueError('Game executable changed since attachment; Steam was not modified')


def _wait_for_steam_closed(output):
    """Wait only during this setup, without signalling or restarting processes."""
    from . import steam_install_options
    deadline = time.monotonic() + 300
    explained = False
    while True:
        try:
            steam_install_options._steam_closed()
            return
        except steam_install_options.ProcessesRunning:
            if not explained:
                output('Close Steam completely (Steam > Exit), Assetto Corsa and the launcher. Setup waits up to 5 minutes and continues automatically. Ctrl+C stops setup.')
                explained = True
            if time.monotonic() >= deadline:
                raise ValueError('Steam, the game or launcher is still running. Close them and run the same command again; prepared files were preserved.')
            time.sleep(2)


def _run_locked(root, *, prompt, output):
    from . import steam_install_options
    output('Keep Steam, Assetto Corsa and the launcher closed during setup.')
    _wait_for_steam_closed(output)
    launcher = root / 'ac-deck'
    safe.require_reference(launcher.lstat(), launcher)
    game = choose_game(prompt=prompt, output=output)
    output('Preparing the CSP kit and game attachment. No game files are copied.')
    package = prepare(root, game)
    preflight_attachment(game, package)
    preflight_csp(root, game, package)
    roots = steam_roots()
    if not roots:
        raise ValueError('Steam data directory not found; the prepared files were preserved')
    choices = []
    for steam_root in roots:
        try:
            if game not in install_discovery.discover_from_root(steam_root):
                continue
            choices.extend((steam_root, account)
                           for account in steam_install_options.discover_accounts(steam_root))
        except (OSError, ValueError, safe.SafetyError) as error:
            output(f'Cannot inspect Steam accounts in {steam_root}: {error}')
    if not choices:
        raise ValueError('No Steam root declares this game and has a local account configuration; the prepared files were preserved')
    receipt_dir = package / 'launcher'
    safe.check_components(receipt_dir)
    receipt = receipt_dir / 'steam-install-receipt.json'
    safe.check_components(receipt)
    selected = None
    if receipt.exists():
        previous = safe.read_json(receipt)
        selected = next((choice for choice in choices
                         if previous.get('account') == choice[1]
                         and previous.get('target') == str(choice[0] / 'userdata' / choice[1] / 'config/localconfig.vdf')), None)
    if selected is None:
        preferred = []
        for steam_root in dict.fromkeys(choice[0] for choice in choices):
            accounts = [account for candidate, account in choices if candidate == steam_root]
            try:
                account = steam_install_options.preferred_account(steam_root, accounts)
            except (OSError, ValueError, safe.SafetyError) as error:
                output(f'Cannot determine the recent Steam account in {steam_root}: {error}')
                continue
            if account is not None:
                preferred.append((steam_root, account))
        if len(preferred) == 1:
            selected = preferred[0]
    if selected is None and len(choices) == 1:
        selected = choices[0]
    if selected is None:
        output('Select the Steam account to configure:')
        for index, (steam_root, account) in enumerate(choices, 1):
            output(f'{index}. Account {account} in {steam_root}')
        answer = prompt('Account number: ').strip()
        if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
            raise ValueError('No Steam account selected; the prepared files were preserved')
        selected = choices[int(answer) - 1]
    steam_root, account = selected
    output(f'Using Steam account {account}.')
    if game not in install_discovery.discover_from_root(steam_root):
        raise ValueError('Steam no longer declares the selected game; configuration was not changed')
    preflight_attachment(game, package)
    preflight_csp(root, game, package)
    _wait_for_steam_closed(output)
    csp.install(root / 'csp', package)
    receipt_dir.mkdir(mode=0o700, exist_ok=True)
    safe.source_root(receipt_dir)
    steam_install_options.install(steam_root, account, receipt, launcher, package,
                                  steam_closed_confirmed=True)
    output('Setup complete. Start Assetto Corsa from its existing Steam entry.')
    return package


@contextmanager
def _setup_lock(root):
    if sys.platform != 'linux':
        raise ValueError('Installation requires Linux')
    import fcntl
    import os
    root = safe.source_root(root)
    local = root / 'local'
    safe.check_components(local)
    local.mkdir(mode=0o700, exist_ok=True)
    safe.source_root(local)
    lock = local / 'community-install.lock'
    safe.check_components(lock)
    with lock.open('a+b') as stream:
        safe.require_reference(os.fstat(stream.fileno()), lock)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Another installation is in progress') from error
        yield root


def run(root, *, prompt=input, output=print):
    """Set up automatically, asking only for ambiguous or missing local data."""
    with _setup_lock(root) as root:
        return _run_locked(root, prompt=prompt, output=output)


def restore_steam(root, *, prompt=input, output=print):
    """Restore only the recorded Steam launch option if it is unchanged."""
    from . import steam_install_options
    with _setup_lock(root) as root:
        receipt = root / 'local/work/community/launcher/steam-install-receipt.json'
        record = safe.read_json(receipt)
        target = safe.absolute(record.get('target', ''))
        if len(target.parents) < 4 or target.name != 'localconfig.vdf':
            raise ValueError('Steam receipt has an invalid target')
        steam_root = safe.source_root(target.parents[3])
        output('Close Steam and Assetto Corsa before restoring the launch option.')
        if prompt('Type CLOSED when both are closed: ').strip() != 'CLOSED':
            raise ValueError('Steam configuration was not changed')
        steam_install_options.restore(steam_root, record.get('account'), receipt,
                                      steam_closed_confirmed=True)
        output('The recorded Steam launch option was restored.')
