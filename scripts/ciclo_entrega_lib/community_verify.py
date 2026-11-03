"""Conferências independentes do pacote comunitário e de seu código compilado."""
import ast
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import tarfile

from .common import CycleError, atomic_json, check_path, digest, file_state, read_json, relative


def verify_bundle(bundle, inputs):
    from .community import inventory
    bundle = Path(bundle)
    actual = inventory(bundle)
    rows = read_json(bundle/'manifest.json')['files']
    expected = {}
    for row in rows:
        name = relative(row['path'])
        if name in expected or not re.fullmatch(r'[0-9a-f]{64}', row['sha256']):
            raise CycleError('Entrada duplicada/inválida no manifesto comunitário.')
        expected[name] = row
    if set(actual) != set(expected)|{'manifest.json'} or 'ac-deck' not in expected:
        raise CycleError('Pacote comunitário tem arquivos ausentes ou extras.')
    for name, row in expected.items():
        if actual[name]['sha256'] != row['sha256'] or actual[name]['size'] != row['size_bytes']:
            raise CycleError('Arquivo do pacote diverge: '+name)
        if (name.split('/')[0].casefold() in ('csp', 'mods', 'assets', 'local', 'state', 'launcher',
                                             'userdata', 'steamapps', 'content')
                or (name.lower().endswith(('.exe', '.dll', '.zip', '.7z', '.rar', '.wav', '.mp3', '.ogg', '.mp4'))
                    and name != '_internal/base_library.zip')):
            raise CycleError('Payload não comunitário no pacote: '+name)
    if not actual['ac-deck']['mode'] & 0o111:
        raise CycleError('Executável comunitário perdeu o modo de execução.')
    info = read_json(bundle/'build-info.json')
    if info.get('distribution') != 'community' or info.get('source_commit') is not None:
        raise CycleError('Metadados de distribuição/fontes divergem do candidato de working tree.')
    for name in ('csp', 'csp_fonts', 'gt5_camera', 'bacc_cameras', 'rogue_toasty_assets',
                 'rogue_album_assets', 'reused_payload_manifest'):
        if info.get(name) is not None:
            raise CycleError('Payload privado nos metadados: '+name)
    from scripts.build_launcher_linux import COMMUNITY_SOURCES, COMMUNITY_NOTICES
    if set(info['source_sha256']) != set(COMMUNITY_SOURCES):
        raise CycleError('Seleção de fontes compiladas diverge do builder.')
    for name, sha in info['source_sha256'].items():
        if inputs['files'][name]['sha256'] != sha:
            raise CycleError('Fonte compilada diverge do snapshot: '+name)
    if set(info['community_notice_sha256']) != set(COMMUNITY_NOTICES):
        raise CycleError('Avisos comunitários ausentes/extras.')
    for name, sha in info['community_notice_sha256'].items():
        if actual[name]['sha256'] != sha or inputs['files'][name]['sha256'] != sha:
            raise CycleError('Aviso comunitário diverge: '+name)
    for name, row in inputs['sdk']['licenses'].items():
        if actual['licenses/sdk/'+name]['sha256'] != row['sha256']:
            raise CycleError('Aviso do SDK diverge: '+name)
    if {n.removeprefix('licenses/sdk/') for n in actual if n.startswith('licenses/sdk/')} != set(inputs['sdk']['licenses']):
        raise CycleError('Inventário de avisos do SDK diverge.')
    for row in info['native_inputs']:
        if (inputs['sdk']['native'][row['source_name']]['sha256'] != row['sha256']
                or actual['_internal/'+row['soname']]['sha256'] != row['sha256']):
            raise CycleError('Biblioteca nativa diverge do SDK.')
    if (info['font']['sha256'] != inputs['sdk']['font']['sha256']
            or actual['_internal/ui/'+info['font']['name']]['sha256'] != info['font']['sha256']):
        raise CycleError('Fonte UI diverge do SDK.')
    return digest(actual)


def verify_archive(archive, bundle, destination):
    from .community import inventory
    archive, bundle, destination = Path(archive), Path(bundle), Path(destination)
    expected = inventory(bundle)
    check_path(destination)
    destination.mkdir(parents=True)
    observed = {}
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            name = relative(member.name)
            if name == bundle.name and member.isdir():
                continue
            prefix = bundle.name+'/'
            if not name.startswith(prefix):
                raise CycleError('Arquivo fora da raiz do pacote no tar.')
            name = relative(name[len(prefix):])
            if member.isdir():
                if not any(n.startswith(name+'/') for n in expected):
                    raise CycleError('Diretório inesperado no tar.')
                continue
            if not member.isfile() or name not in expected or name in observed:
                raise CycleError('Link, duplicata ou arquivo inesperado no tar.')
            path = destination/name
            path.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, path.open('xb') as target:
                shutil.copyfileobj(source, target)
            path.chmod(member.mode)
            observed[name] = file_state(path)
    if observed != expected:
        raise CycleError('Arquivo tar diverge dos bytes/modos do pacote.')
    return digest(observed)


def elf_checks(bundle, inputs, output):
    from .common import process_env
    from .community import inventory
    bundle = Path(bundle)
    env = process_env()
    env.pop('LD_LIBRARY_PATH', None)
    env['LD_LIBRARY_PATH'] = str(bundle/'_internal')
    collect = bundle.parent/'build/ac-deck/COLLECT-00.toc'
    mapping = {row[0]:row for row in ast.literal_eval(collect.read_text())[0]}
    known_hashes = {row['sha256'] for row in inputs['sdk']['python_files'].values() if 'sha256' in row}
    known_hashes.update(row['sha256'] for row in inputs['sdk']['native'].values())
    known_hashes.update(row['sha256'] for row in inputs['environment']['dependencies'].values())
    rows, versions = [], set()
    for name, state in inventory(bundle).items():
        path = bundle/name
        with path.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
        raw = subprocess.check_output(['readelf', '--version-info', str(path)], env=env, text=True)
        versions.update(re.findall(r'GLIBC_(\d+\.\d+)', raw))
        linked = subprocess.run(['ldd', str(path)], env=env, capture_output=True, text=True)
        if linked.returncode or 'not found' in linked.stdout:
            raise CycleError('Dependência do pacote indisponível: '+name)
        row = dict(path=name, sha256=state['sha256'], ldd=linked.stdout)
        if name == 'ac-deck':
            row['origin'] = 'PyInstaller bootloader plus archived application; verified by compiled probe'
        else:
            key, chain = name.removeprefix('_internal/'), []
            while key in mapping and mapping[key][2] == 'SYMLINK':
                if key in chain:
                    raise CycleError('Ciclo de origem ELF no COLLECT.')
                chain.append(key)
                key = posixpath.normpath(posixpath.join(posixpath.dirname(key), mapping[key][1]))
            if key not in mapping:
                raise CycleError('Origem ELF ausente do COLLECT: '+name)
            origin = Path(mapping[key][1]).resolve(strict=True)
            if file_state(origin)['sha256'] != state['sha256'] or state['sha256'] not in known_hashes:
                raise CycleError('Origem ELF não corresponde ao SDK/ambiente inventariado: '+name)
            row['origin'] = str(origin)
        rows.append(row)
    maximum = max(versions, key=lambda s:tuple(map(int, s.split('.'))), default='0.0')
    if (tuple(map(int, maximum.split('.'))) > tuple(map(int, inputs['recipe']['sdk']['maximum_glibc'].split('.')))
            or maximum != read_json(bundle/'build-info.json')['highest_glibc_symbol']):
        raise CycleError('GLIBC excede o limite ou diverge dos metadados.')
    atomic_json(output, dict(files=rows, maximum_glibc=maximum, collect_sha256=file_state(collect)['sha256']))


def verify(result, inputs, tree, attempt, run, sdk):
    from .community import inventory
    bundle, moved = Path(result['bundle']), Path(result['relocated'])
    evidence = attempt/'evidence'
    evidence.mkdir()
    verify_bundle(bundle, inputs)
    if verify_bundle(moved, inputs) != verify_bundle(bundle, inputs):
        raise CycleError('Pacote relocado diverge.')
    elf_checks(bundle, inputs, evidence/'elf.json')
    outside = attempt/'unrelated working directory'
    outside.mkdir()
    home = outside/'synthetic home'
    home.mkdir()
    env = dict(HOME=str(home), XDG_DATA_HOME=str(home/'data'), XDG_CONFIG_HOME=str(home/'config'),
               XDG_CACHE_HOME=str(home/'cache'))
    for prefix, location in (('original', bundle), ('relocated', moved)):
        for label, args in (('fresh', ['--help']), ('repeat', ['--help']),
                            ('install', ['install', '--help']), ('restore', ['restore-steam', '--help'])):
            run([location/'ac-deck', *args], cwd=outside, env=env, timeout=30)
    installed = attempt/'bootstrap check'/'installed package with spaces'
    run(sdk['python']+['-B', str(tree/'scripts/install_ac_deck.py'), '--accept-terms', '--archive', str(result['archive']),
                      '--sha256', result['archive_sha256'], '--destination', str(installed)],
        cwd=outside, env=env, timeout=120)
    if verify_bundle(installed, inputs) != verify_bundle(bundle, inputs):
        raise CycleError('Bootstrap diverge do arquivo verificado.')
    run([installed/'ac-deck', '--help'], cwd=outside, env=env, timeout=30)
    fixtures = attempt/'fixtures'
    shutil.copytree(tree/'tests', fixtures/'tests')
    probe = tree/'scripts/ciclo_entrega_lib/community_probe.py'
    run(sdk['python']+['-B', str(probe), '--bundle', str(moved), '--snapshot', str(tree),
                      '--tests', str(fixtures), '--output', str(evidence/'compiled')], cwd=outside,
        env=dict(env, LD_LIBRARY_PATH=str(moved/'_internal')), timeout=180)
    compiled = read_json(evidence/'compiled/compiled.json')
    if compiled['source_product_imports'] or any(compiled[key] for key in ('errors', 'failures', 'skips')):
        raise CycleError('Probe compilado falhou ou usou fontes externas.')
    atomic_json(evidence/'validation.json', dict(status='validated-local-candidate', source_tree='working-tree',
                source_base=inputs['source_base'], input_sha256=digest(inputs),
                archive_sha256=file_state(result['archive'])['sha256'],
                manifest_sha256=file_state(bundle/'manifest.json')['sha256'],
                compiled_tests=compiled['tests'], offscreen_images=len(compiled['images']),
                bootstrap=True, informational_cli=True, relocation=True, published=False,
                physical_deck=False, accepted=False,
                limits=['Synthetic/offscreen checks do not establish real Deck performance or user acceptance',
                        'Licensing coverage and publication remain separate review gates']))
