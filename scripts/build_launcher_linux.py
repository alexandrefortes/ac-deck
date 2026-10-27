#!/usr/bin/env python3
"""Gera um launcher Linux em pasta nova, com Python e SDL2 locais.

Requer PyInstaller no Python que executa este script. Não instala dependências,
inclui jogo ou altera a Steam. As entradas nativas são bibliotecas já obtidas.
"""
from datetime import datetime, timezone
import hashlib
import gzip
import importlib.metadata
import json
import lzma
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.launcher import csp, font_support, gt5_camera, bacc_camera

SOURCES = ('scripts/jogo_deck.py', 'scripts/pratica_deck.py',
           'scripts/inventario_importacao.py', 'src/launcher/__init__.py',
           'src/launcher/content.py', 'src/launcher/catalogue.py', 'src/launcher/window.py',
           'src/launcher/campaigns.py', 'src/launcher/campaign_ui.py', 'src/launcher/native_menu.py', 'src/launcher/ui_render.py', 'src/launcher/history_records.py',
           'src/launcher/one_shot_ui.py', 'src/launcher/ai_activity.py', 'src/launcher/favorites.py',
           'src/launcher/rogue.py', 'src/launcher/rogue_generator.py', 'src/launcher/rogue_ui.py',
           'src/launcher/finish_capture.py',
           'src/launcher/rogue_rewards.py', 'src/launcher/rogue_rewards_ui.py',
           'src/launcher/rogue_result_ui.py', 'src/launcher/rogue_duration.py',
           'src/launcher/rogue_toasty_session.py', 'src/launcher/rogue_toasty_install.py',
           'src/launcher/rogue_toasty.py', 'src/launcher/rogue_toasty_app.py',
           'src/launcher/rogue_toasty_assets.py',
           'src/launcher/session_settings.py', 'src/launcher/session_process.py',
           'src/launcher/graphics.py', 'src/launcher/graphics_settings.py', 'src/launcher/controls.py', 'src/launcher/csp.py',
           'src/launcher/installed.py', 'src/launcher/previews.py',
           'src/launcher/diagnostics.py',
           'src/launcher/font_support.py',
           'src/launcher/conditions.py',
           'src/launcher/event_synthetizer.py', 'src/launcher/player_history.py',
           'src/launcher/ai_events.py', 'src/launcher/api_credentials.py',
           'src/launcher/ai_preferences.py', 'src/launcher/ai_recomposition.py',
           'src/launcher/ai_settings_ui.py', 'src/launcher/session_prompt.py', 'src/launcher/ai_usage.py', 'src/launcher/ai_report.py',
           'src/launcher/semantic_catalogue.py', 'src/launcher/dictation.py',
           'src/launcher/results.py', 'src/launcher/history_retention.py',
           'src/launcher/linear_gamma.py',
           'src/launcher/comfort.py',
           'src/launcher/chase_camera.py', 'src/launcher/hud_cleanup.py', 'src/launcher/gt5_camera.py',
           'src/launcher/bacc_camera.py',
           'src/launcher/driving_haptics.py', 'src/launcher/driving_haptics_app.py',
           'licenses/ACC-DualSense-Feedback.txt',
           'src/launcher/practice_session.py', 'src/launcher/assists_config.py',
           'src/launcher/application.py', 'src/launcher/game_config.py',
           'src/launcher/package_setup.py', 'src/launcher/steam.py', 'src/launcher/file_io.py',
           'scripts/build_launcher_linux.py')
COMMUNITY_SOURCES = tuple(name for name in SOURCES if name != 'scripts/inventario_importacao.py')
CSP_DOCS = ('docs/session-prompt.md', 'docs/manual-configuracao-csp.md', 'docs/csp-configuracoes-gerenciadas.json',
            'docs/analise-csp-horario-shader-020.md', 'docs/configuracoes-otimizadas-steam-deck.md',
            'docs/analise-csp-linear-021.md', 'docs/hud-camera-deck.md', 'docs/contrato-pratica-sessao.md',
            'docs/resultados-sessao.md', 'docs/event-synthetizer-opcoes.md', 'docs/pista-optimum.md',
            'docs/ui-launcher-044.md', 'docs/ui-launcher-045.md', 'docs/ui-launcher-046.md', 'docs/haptics-steam-deck.md',
            'docs/ui-launcher-048.md', 'docs/ui-launcher-051.md', 'docs/performance-052.md', 'docs/traction-control.md', 'docs/shadow-distance.md', 'docs/graphics-settings.md', 'docs/catalogue-player-experience.md', 'docs/session-lifecycle-058.md',
            'docs/ai-generator-reform.md', 'docs/ai-curation-060.md', 'docs/dictation-errors-061.md', 'docs/dictation-capture-062.md',
            'docs/dictation-input-063.md', 'docs/ai-history-064.md', 'docs/ui-synth-065.md', 'docs/ai-variety-066.md', 'docs/ui-time-search-067.md', 'docs/plano-favoritos.md', 'docs/ai-manual-time-069.md', 'docs/ui-text-scroll-071.md', 'docs/events-campanhas-072.md', 'docs/ui-profile-one-shot.md')


CSP_DOCS += ('docs/ui-synth-layout-078.md', 'docs/rogue-mode.md', 'docs/rogue-balanceamento.md',
             'docs/rogue-toasty.md', 'docs/rogue-tempo.md', 'docs/rogue-ui-086.md',
             'docs/rogue-album.md')


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def command(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def bundle_toasty_assets(asset_root, bundle):
    """Copy only the validated distribution; never fetch or alter its inputs."""
    from src.launcher import file_io as safe
    from src.launcher import rogue_toasty_assets
    source = safe.source_root(asset_root)
    bundle = safe.source_root(bundle)
    if source == bundle or source.is_relative_to(bundle) or bundle.is_relative_to(source):
        raise ValueError('Toasty asset source and build destination must be separate')
    payload = rogue_toasty_assets.load_distribution(source)
    destination = bundle/'assets/rogue-toasty'
    safe.check_components(destination)
    if destination.exists():
        raise FileExistsError('Toasty asset destination already exists; preserve it')
    destination.mkdir(parents=True)
    rows = []
    for name in rogue_toasty_assets.DISTRIBUTION_NAMES:
        raw = payload[name]
        target = destination/name
        with target.open('xb') as output:
            output.write(raw)
        target.chmod(0o644)
        expected = hashlib.sha256(raw).hexdigest()
        if digest(target) != expected:
            raise RuntimeError('Toasty asset copy changed: '+name)
        rows.append(dict(path=target.relative_to(bundle).as_posix(),
                         sha256=expected, size_bytes=len(raw)))
    if rogue_toasty_assets.load_distribution(source) != payload:
        raise RuntimeError('Toasty asset source changed during copy')
    if rogue_toasty_assets.load_distribution(destination) != payload:
        raise RuntimeError('Toasty asset destination differs after copy')
    return dict(source=source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else source.name,
                files=rows, verification='Fixed distribution sizes and SHA-256; no network',
                media_rights='See assets/rogue-toasty/media-rights.json')


def bundle_rogue_album_assets(asset_root, bundle):
    """Copy the pinned album kit, preserving its images and provenance bytes."""
    from src.launcher import file_io as safe
    from src.launcher import rogue_rewards
    source = safe.source_root(asset_root)
    bundle = safe.source_root(bundle)
    if source == bundle or source.is_relative_to(bundle) or bundle.is_relative_to(source):
        raise ValueError('Rogue album source and build destination must be separate')
    payload = rogue_rewards.load_album_distribution(source)
    destination = bundle/'assets/rogue-album'
    safe.check_components(destination)
    if destination.exists():
        raise FileExistsError('Rogue album destination already exists; preserve it')
    destination.mkdir(parents=True)
    rows = []
    for name in rogue_rewards.ALBUM_DISTRIBUTION_NAMES:
        raw = payload[name]
        target = destination/name
        with target.open('xb') as output:
            output.write(raw)
        target.chmod(0o644)
        expected = hashlib.sha256(raw).hexdigest()
        if digest(target) != expected:
            raise RuntimeError('Rogue album copy changed: '+name)
        rows.append(dict(path=target.relative_to(bundle).as_posix(),
                         sha256=expected, size_bytes=len(raw)))
    if rogue_rewards.load_album_distribution(source) != payload:
        raise RuntimeError('Rogue album source changed during copy')
    if rogue_rewards.load_album_distribution(destination) != payload:
        raise RuntimeError('Rogue album destination differs after copy')
    return dict(source=source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else source.name,
                files=rows, verification='Fixed distribution sizes and SHA-256; no network',
                scope='Eight original meme images and accompanying provenance/notices')



def reuse_static_payload(source, bundle, *, csp_zip=None):
    """Reaproveita CSP/mods/fontes por manifesto; nunca runtime, código ou metadados antigos."""
    from scripts import atualizar_entrega_deck as delivery
    from scripts.ciclo_entrega_lib.build import verify_bundle
    before = verify_bundle(source)
    rows, _ = delivery._read_manifest(source)
    info = json.loads((source/'build-info.json').read_text(encoding='utf-8'))
    for name, row in rows.items():
        if not name.startswith(('csp/', 'csp-fonts/', 'mods/')):
            continue
        if csp_zip is not None and name.startswith('csp/'):
            continue
        if name in ('mods/gt7-hud-1.1.2-personal.zip', 'mods/GT7.HUD.-.v1.3.1.zip'):
            continue
        destination = bundle/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        delivery._copy_file(source/name, destination, row)
    release = json.loads((source/'release.json').read_text(encoding='utf-8'))
    for row in release['compressed_files'] if csp_zip is None else []:
        if row['source'] not in ('csp/dwrite.dll.gz', 'csp/dwrite.dll.xz') or row['target'] != 'csp/dwrite.dll':
            raise ValueError('Arquivo compactado desconhecido na entrega de origem')
        destination = bundle/'csp/dwrite.dll'
        decompress = lzma.open if row['source'].endswith('.xz') else gzip.open
        with decompress(bundle/row['source'], 'rb') as src, destination.open('xb') as dst:
            shutil.copyfileobj(src, dst)
        if digest(destination) != row['sha256'] or destination.stat().st_size != row['size_bytes']:
            raise ValueError('DLL CSP descompactado diverge da origem')
        (bundle/row['source']).unlink()
        checksum = bundle/'csp/dwrite.dll.sha256'
        if checksum.exists():
            checksum.unlink()
    if csp_zip is not None:
        info['csp'] = csp.unpack(csp_zip, bundle/'csp')
    if not (bundle/'csp/dwrite.dll').is_file() or not info.get('csp'):
        raise ValueError('Payload CSP incompleto')
    font_support.verify(bundle/'csp-fonts')
    if verify_bundle(source) != before:
        raise ValueError('Payload estático mudou durante a cópia')
    return {key: info.get(key) for key in ('csp', 'csp_fonts', 'gt5_camera', 'bacc_cameras')}


def build(batch, native_dir, *, csp_zip=None, gt5_zip=None, bacc_dir=None,
          toasty_assets=None, rogue_album_assets=None, font=None, licenses_dir=None,
          reuse_delivery=None, source_commit=None, build_number=None, community=False):
    if community and any(value is not None for value in
                         (csp_zip, gt5_zip, bacc_dir, reuse_delivery,
                          toasty_assets, rogue_album_assets)):
        raise ValueError('Community builds cannot include private CSP, mods, media or delivery payloads')
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise ValueError('Execute em Linux x86_64, inclusive WSL2')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', batch):
        raise ValueError('Lote inválido')
    if source_commit is not None and not re.fullmatch(r'[0-9a-f]{40,64}', source_commit):
        raise ValueError('Commit de fontes inválido')
    if reuse_delivery is not None and any((gt5_zip, bacc_dir)):
        raise ValueError('Escolha payload verificado ou arquivos originais, sem mistura')
    reused = None
    if reuse_delivery is not None:
        from scripts.ciclo_entrega_lib.build import verify_bundle
        reuse_delivery = Path(reuse_delivery).resolve(strict=True)
        reused = verify_bundle(reuse_delivery)
    if gt5_zip is not None and csp_zip is None:
        raise ValueError('GT5 camera requires the CSP build')
    gt5_manifest = gt5_camera.inspect(gt5_zip) if gt5_zip is not None else None
    if bacc_dir is not None and csp_zip is None:
        raise ValueError('BACC cameras require the CSP build')
    bacc_manifest = ([bacc_camera.inspect(Path(bacc_dir)/spec['archive'], mode)
                      for mode, spec in bacc_camera.SPECS.items()]
                     if bacc_dir is not None else (None if community else []))
    version = importlib.metadata.version('pyinstaller')
    font=Path(font) if font is not None else Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    font_sha256=csp.digest(font)
    native_dir = native_dir.resolve(strict=True)
    work = ROOT/'local/work'/batch
    if work.exists():
        raise FileExistsError('Lote já existe: '+str(work))
    source_paths = COMMUNITY_SOURCES if community else SOURCES+(CSP_DOCS if csp_zip is not None or reused else ())
    before = {p: digest(ROOT/p) for p in source_paths}
    from src.launcher import rogue_toasty_assets, rogue_rewards
    toasty_source = album_source = None
    toasty_before = album_before = None
    if not community:
        asset_base = reuse_delivery if reused else ROOT/'entrega/deck'
        toasty_source = Path(toasty_assets) if toasty_assets is not None else asset_base/'assets/rogue-toasty'
        toasty_before = rogue_toasty_assets.load_distribution(toasty_source)
        album_source = Path(rogue_album_assets) if rogue_album_assets is not None else asset_base/'assets/rogue-album'
        album_before = rogue_rewards.load_album_distribution(album_source)
    work.mkdir(parents=True)
    native = work/'native'
    native.mkdir()
    inputs = []
    # Apenas os ELF regulares da pasta explicitamente selecionada. Os links
    # SONAME do pacote de origem não são importados ou seguidos.
    for source in sorted(native_dir.iterdir()):
        if not stat.S_ISREG(source.lstat().st_mode) or '.so' not in source.name:
            continue
        raw = command('readelf', '-d', str(source), capture_output=True).stdout
        match = re.search(r'\(SONAME\).*\[([^/\]]+)\]', raw)
        name = match[1] if match else source.name
        target = native/name
        with source.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst)
        sha = digest(source)
        if sha != digest(target):
            raise RuntimeError('Cópia nativa divergente: '+source.name)
        inputs.append(dict(source_name=source.name, soname=name, sha256=sha,
                           size_bytes=source.stat().st_size))
    if not (native/'libSDL2-2.0.so.0').is_file():
        raise ValueError('SDL2 Linux ausente da seleção explícita')
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = str(native)+((':'+env['LD_LIBRARY_PATH']) if env.get('LD_LIBRARY_PATH') else '')
    env['PYINSTALLER_CONFIG_DIR'] = str(work/'pyinstaller-cache')
    executable_name = 'ac-deck' if community else 'papao'
    bundle_name = executable_name+'-linux-x86_64'
    args = [sys.executable, '-m', 'PyInstaller', '--onedir', '--noupx',
            '--log-level', 'WARN', '--name', executable_name, '--paths', str(ROOT),
            '--distpath', str(work/'dist'), '--workpath', str(work/'build'),
            '--specpath', str(work), '--add-data', str(font)+':ui']
    for row in inputs:
        args += ['--add-binary', str(native/row['soname'])+':.']
    args.append(str(ROOT/'scripts/jogo_deck.py'))
    with (work/'build.log').open('x') as log:
        command(*args, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    raw = work/'dist'/executable_name
    # O PyInstaller gera links próprios. A distribuição usa cópias regulares,
    # recusando qualquer link que aponte para fora do resultado desta build.
    for path in raw.rglob('*'):
        if path.is_symlink() and not path.resolve(strict=True).is_relative_to(raw.resolve()):
            raise ValueError('Link externo no resultado: '+str(path))
    bundle = work/bundle_name
    shutil.copytree(raw, bundle, symlinks=False)
    toasty_manifest = bundle_toasty_assets(toasty_source, bundle) if not community else None
    album_manifest = bundle_rogue_album_assets(album_source, bundle) if not community else None
    csp_manifest = csp.unpack(csp_zip, bundle/'csp') if csp_zip is not None and not reused else None
    if gt5_zip is not None:
        from src.launcher import file_io as safe
        safe.copy_verified(Path(gt5_zip), bundle/'mods'/gt5_camera.ARCHIVE_NAME,
                            gt5_camera.ARCHIVE_SHA256)
    if bacc_dir is not None:
        from src.launcher import file_io as safe
        for spec in bacc_camera.SPECS.values():
            safe.copy_verified(Path(bacc_dir)/spec['archive'], bundle/'mods'/spec['archive'], spec['sha256'])
    font_manifest = (font_support.bundle(bundle/'csp-fonts', font.parent,
                     Path('/usr/share/doc/fonts-dejavu-core/copyright'))
                     if csp_manifest else None)
    if reused:
        reused_info = reuse_static_payload(reuse_delivery, bundle, csp_zip=csp_zip)
        csp_manifest = reused_info['csp']
        font_manifest = reused_info['csp_fonts']
        gt5_manifest = reused_info['gt5_camera']
        bacc_manifest = reused_info['bacc_cameras']
    if csp_manifest:
        manual = bundle/'manual'
        manual.mkdir()
        for name in CSP_DOCS:
            shutil.copyfile(ROOT/name, manual/Path(name).name)
    licenses = bundle/'licenses'
    licenses.mkdir()
    shutil.copyfile(ROOT/'licenses/ACC-DualSense-Feedback.txt',licenses/'ACC-DualSense-Feedback.txt')
    copyright_root = native_dir.parent.parent/'share/doc'
    if copyright_root.is_dir():
        for path in copyright_root.glob('*/copyright'):
            shutil.copyfile(path, licenses/(path.parent.name+'.txt'))
    imaging = importlib.metadata.distribution('Pillow')
    for relative in imaging.files or ():
        if '/licenses/' in str(relative):
            file=Path(imaging.locate_file(relative))
            if file.is_file():
                name=str(relative).split('/licenses/',1)[1].replace('/','-')
                shutil.copyfile(file,licenses/('Pillow-'+name))
    # Avisos dos componentes Python e bibliotecas do próprio Ubuntu usados.
    pyi = importlib.metadata.distribution('pyinstaller')
    for relative in pyi.files or ():
        if 'COPYING' in str(relative).upper():
            file = Path(pyi.locate_file(relative))
            if file.is_file():
                shutil.copyfile(file, licenses/'PyInstaller.txt')
                break
    owners = {f'python{sys.version_info.major}.{sys.version_info.minor}-minimal',
              f'libpython{sys.version_info.major}.{sys.version_info.minor}-stdlib','fonts-dejavu-core'}
    native_sonames = {row['soname'] for row in inputs}
    for path in (bundle/'_internal').iterdir():
        if not path.is_file() or path.name in native_sonames:
            continue
        # dpkg-query não modifica o banco de pacotes.
        if licenses_dir is not None or not shutil.which('dpkg-query'):
            continue
        result = subprocess.run(['dpkg-query', '-S', '*/'+path.name],
                                text=True, capture_output=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                owners.add(line.split(': ', 1)[0].split(':')[0])
    for owner in sorted(owners):
        copyright_file = Path('/usr/share/doc')/owner/'copyright'
        if licenses_dir is None and copyright_file.is_file():
            shutil.copyfile(copyright_file, licenses/(owner+'.txt'))
    if licenses_dir is not None:
        from src.launcher import file_io as safe
        notices = safe.source_root(licenses_dir)
        for notice in sorted(notices.rglob('*')):
            safe.check_components(notice)
            if notice.is_file():
                destination = licenses/'sdk'/notice.relative_to(notices)
                destination.parent.mkdir(parents=True, exist_ok=True)
                safe.copy_verified(notice, destination, digest(notice))
    after = {p: digest(ROOT/p) for p in source_paths}
    if before != after:
        raise RuntimeError('Fontes mudaram durante a build; preserve o lote e gere outro')
    if csp.digest(font)!=font_sha256:
        raise RuntimeError('Fonte tipográfica mudou durante o build')
    if not community and rogue_toasty_assets.load_distribution(toasty_source) != toasty_before:
        raise RuntimeError('Assets Toasty mudaram durante a build; preserve o lote e gere outro')
    if not community and rogue_rewards.load_album_distribution(album_source) != album_before:
        raise RuntimeError('Assets do álbum mudaram durante a build; preserve o lote e gere outro')
    versions = set()
    for path in bundle.rglob('*'):
        if path.is_file():
            with path.open('rb') as stream:
                elf = stream.read(4) == b'\x7fELF'
            if elf:
                result = command('readelf', '--version-info', str(path), capture_output=True)
                versions.update(re.findall(r'GLIBC_(\d+\.\d+)', result.stdout))
    info = dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
                kind='launcher_linux', architecture=platform.machine(),
                public_name='ac-deck', ui_language='en',
                distribution='community' if community else 'private',
                content_policy=('Launcher and licensed runtime dependencies only; no game, DLC, '
                                'Steam data, Proton prefix, CSP, mod archives or private media'
                                if community else 'Selected private payloads verified by pinned manifests'),
                python=platform.python_version(), pyinstaller=version,pillow=imaging.version,
                pyinstaller_hooks=importlib.metadata.version('pyinstaller-hooks-contrib'),
                source_commit=source_commit, build_number=build_number,
                reused_payload_manifest=reused,
                build_libc=platform.libc_ver(),
                highest_glibc_symbol=max(versions, key=lambda s:tuple(map(int,s.split('.')))) if versions else None,
                source_sha256=before, native_inputs=inputs,
                font=dict(name=font.name,sha256=font_sha256),
                csp_fonts=font_manifest,
                gt5_camera=gt5_manifest,
                bacc_cameras=bacc_manifest,
                rogue_toasty_assets=toasty_manifest,
                rogue_album_assets=album_manifest,
                scope='launcher autoral, Python e bibliotecas'+('; CSP selecionado para entrega privada' if csp_manifest else '')+'; sem jogo, Steam, Proton ou prefixo',
                csp=({k:v for k,v in csp_manifest.items() if k != 'files'} if csp_manifest else None),
                steam_os_observed=False)
    (bundle/'build-info.json').write_text(json.dumps(info, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    (bundle/'LEIA-ME.txt').write_text(
        'ac-deck — launcher Linux x86_64\n\n'
        f'./{executable_name} --help\n'
        f'./{executable_name} vincular --jogo "/instalacao/assettocorsa" --lote jogo\n\n'
        'Na Steam, opções de inicialização do Assetto Corsa:\n'
        f'"/pasta/{executable_name}" steam --pacote local/work/jogo -- %command%\n\n'
        'Python, SDL2 e leitor de imagens acompanham o launcher. Steam, licença, jogo e Proton ficam na plataforma.\n'
        'vincular usa a instalação original; não copia carros, pistas ou executável.\n'
        'Este build não comprova relocação dos dados do jogo ou execução offline.\n'
        + ('Distribuição comunitária: sem CSP, mods ou mídia privada. Use sua instalação legítima do jogo.\n'
           if community else '')
        + (f'\nCSP {csp_manifest["version"]} incluído. ./papao csp-info confere o payload.\n'
           'O modo steam acrescenta dwrite.dll/extension ao jogo declarado, sem copiar carros/pistas.\n'
           'Use --sem-csp antes de -- para executar a referência sem carregar o patch.\n'
           'Graphics > Profile: Performance, Quality, CSP Performance, CSP Quality. Troca vale na próxima sessão.\n'
           'Perfis base usam dwrite do Wine; perfis CSP usam WeatherFX base e cor linear sempre Off.\n'
           'CSP Quality revisado: sombras 1024/100 m, reflexos 512/uma face, grama Off e fumaça simplificada.\n'
           'Menu sem desenho durante a corrida; ao recuperar foco, mostra Finishing session com Start bloqueado.\n'
           'Preferências de conforto ficam salvas independentemente do perfil. Sol/Pure não incluídos.\n'
           'Fontes DejaVu com licença em csp-fonts/; aliases ausentes são copiados ao prefixo do jogo, com recibo.\n'
           'csp-fonts-restore --pacote PACOTE --prefixo COMPATDATA reverte apenas as cópias do recibo, com o jogo fechado.\n'
           'CSP usa WINE_DBGHELP_OLD_PDB=1 no filho, preservando valor explícito da entrada Steam.\n'
           'Aba Controle: Original/Assistido e ajustes do analógico. R3 alterna Race/Drift.\n'
           'Overrides CSP cobrem o state da cópia e Documents normal do Proton, com histórico.\n'
           'Pure e Sol não acompanham este pacote.\n' if csp_manifest else ''), encoding='utf-8')
    rows = []
    for path in sorted(bundle.rglob('*')):
        if path.is_symlink():
            raise ValueError('Link retido na distribuição')
        if path.is_file():
            rows.append(dict(path=path.relative_to(bundle).as_posix(), sha256=digest(path),
                             size_bytes=path.stat().st_size))
    (bundle/'manifest.json').write_text(json.dumps(dict(files=rows), indent=2)+'\n', encoding='utf-8')
    archive = work/(bundle_name+'.tar.gz')
    def archive_member(member):
        member.uid = member.gid = 0
        member.uname = member.gname = ''
        return member
    with tarfile.open(archive, 'x:gz', format=tarfile.PAX_FORMAT) as tar:
        tar.add(bundle, arcname=bundle.name, filter=archive_member)
    summary = dict(bundle=str(bundle), archive=str(archive), archive_sha256=digest(archive),
                   archive_bytes=archive.stat().st_size, files=len(rows)+1, build=info)
    (work/'result.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k != 'build'}, ensure_ascii=False))
    return summary


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lote', required=True)
    parser.add_argument('--bibliotecas', type=Path, required=True)
    parser.add_argument('--font', type=Path, help='Fonte TTF explícita para a interface')
    parser.add_argument('--licenses-dir', type=Path, help='Avisos do SDK; dispensa consultas dpkg')
    parser.add_argument('--reuse-delivery', type=Path, help='Reutiliza somente payload estático conferido pelo manifesto')
    parser.add_argument('--source-commit')
    parser.add_argument('--build-number')
    parser.add_argument('--community', action='store_true',
                        help='Distribuição comunitária sem CSP, mods ou mídia privada')
    parser.add_argument('--csp-zip', type=Path, help='ZIP CSP com SHA-256 fixado; substitui o CSP de --reuse-delivery, sem baixar arquivos')
    parser.add_argument('--gt5-camera-zip', type=Path, help='ZIP GT5 pessoal fixado, para a entrega privada')
    parser.add_argument('--bacc-dir', type=Path, help='Pasta com os dois ZIPs BACC pessoais fixados')
    parser.add_argument('--toasty-assets', type=Path,
                        help='Pasta rogue-toasty validada; padrão: entrega/deck/assets/rogue-toasty; sem rede')
    parser.add_argument('--rogue-album-assets', type=Path,
                        help='Pasta rogue-album validada; padrão: entrega/deck/assets/rogue-album; sem rede')
    args = parser.parse_args()
    try:
        build(args.lote, args.bibliotecas, csp_zip=args.csp_zip, gt5_zip=args.gt5_camera_zip,
              bacc_dir=args.bacc_dir, toasty_assets=args.toasty_assets,
              rogue_album_assets=args.rogue_album_assets, font=args.font, licenses_dir=args.licenses_dir,
              reuse_delivery=args.reuse_delivery, source_commit=args.source_commit,
              build_number=args.build_number, community=args.community)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error)+'\n')
