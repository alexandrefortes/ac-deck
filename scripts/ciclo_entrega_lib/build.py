"""Snapshot Git por bytes/modos e execução do builder existente com SDK explícito."""
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import uuid

from .common import CycleError, atomic_json, check_path, digest, file_state, read_json, relative

PROBE = '''import importlib.metadata as m, json, platform, sys
print(json.dumps(dict(python=platform.python_version(), platform=sys.platform,
 architecture=platform.machine(), packages={n:m.version(n) for n in
 ('pyinstaller','pyinstaller-hooks-contrib','Pillow')})))'''


def source_entries(git, commit='HEAD'):
    # Repasses/aceites não fazem parte do executável. Manuais incluídos fazem.
    from scripts.build_launcher_linux import SOURCES, CSP_DOCS
    explicit = set(SOURCES+CSP_DOCS) | {'scripts/deck_bootstrap.sh', 'scripts/ciclo-entrega.json'}
    result = {}
    for line in git.run('ls-tree', '-r', '-z', commit, '--', 'src', 'scripts', 'docs', 'licenses').stdout.split(b'\0'):
        if not line:
            continue
        header, raw_name = line.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        if name in explicit or name.startswith(('src/', 'licenses/')) or (name.startswith('scripts/') and name.endswith('.py')):
            mode, kind, oid = header.decode().split()
            if kind != 'blob' or mode not in ('100644', '100755'):
                raise CycleError('Snapshot exige arquivo regular: '+name)
            result[name] = [mode, oid]
    return result


def snapshot(git, destination, commit, entries):
    check_path(destination)
    if destination.exists():
        verify_snapshot(git, destination, entries)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='snapshot-', dir=destination.parent) as temporary:
        root = Path(temporary)/'tree'
        root.mkdir()
        archive = git.run('archive', '--format=tar', commit, '--', *sorted(entries)).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar:
                if member.isdir():
                    continue
                name = relative(member.name)
                if name not in entries or not member.isfile():
                    raise CycleError('Entrada inesperada no snapshot Git: '+name)
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(tar.extractfile(member).read())
                path.chmod(0o755 if entries[name][0] == '100755' else 0o644)
        verify_snapshot(git, root, entries)
        root.rename(destination)
    return destination


def verify_snapshot(git, root, entries):
    for name, (mode, oid) in entries.items():
        path = root/name
        state = file_state(path)
        if state is None or git.text('hash-object', '--no-filters', '--', str(path)) != oid:
            raise CycleError('Bytes do snapshot divergem do commit: '+name)
        if os.name != 'nt' and bool(state['mode'] & 0o111) != (mode == '100755'):
            raise CycleError('Modo do snapshot diverge do commit: '+name)


def backend_snapshot(tree, entries, sdk, run):
    # Linux precisa conferir modos mesmo quando o controlador roda em Windows.
    manifest = {name: dict(sha256=file_state(tree/name)['sha256'], mode=int(mode, 8) & 0o777)
                for name, (mode, _) in entries.items()}
    atomic_json(tree/'snapshot-inputs.json', manifest)
    script = '''import hashlib,json,os,pathlib,sys
root=pathlib.Path(sys.argv[1]); rows=json.loads((root/'snapshot-inputs.json').read_text())
for name,row in rows.items():
 p=root/name
 if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
  raise RuntimeError('Snapshot bytes changed: '+name)
for name,row in rows.items():
 p=root/name; p.chmod(row['mode'])
 if p.stat().st_mode & 0o777 != row['mode']:
  raise RuntimeError('Snapshot mode unavailable: '+name)
'''
    run(sdk['python']+['-c', script, mapped(tree, sdk)])


def mapped(path, sdk):
    """Mapeamento explícito de caminho local para o backend (por exemplo WSL)."""
    path = Path(path).resolve()
    if not sdk.get('path_map'):
        return str(path)
    for item in sdk['path_map']:
        base = Path(item['local']).resolve()
        if path == base or path.is_relative_to(base):
            return item['backend'].rstrip('/')+'/'+path.relative_to(base).as_posix()
    raise CycleError('Sem mapeamento explícito para o backend: '+str(path))


def sdk_inputs(sdk):
    if not sdk.get('python') or not sdk.get('native') or not sdk.get('font') or not sdk.get('licenses'):
        raise CycleError('SDK não configurado: informe python, native, font e licenses em local/ciclo-entrega.json.')
    paths = [Path(sdk['native']), Path(sdk['font']), Path(sdk['licenses'])]
    if not paths[0].is_dir() or not paths[2].is_dir() or not paths[1].is_file():
        raise CycleError('SDK incompleto: bibliotecas/avisos devem ser pastas e font um arquivo existente.')
    result = {}
    for path in paths:
        check_path(path)
        if path.is_dir():
            files = sorted(p for p in path.rglob('*') if p.is_file() or p.is_symlink())
            for item in files:
                result[str(item.resolve())] = file_state(item)
        else:
            result[str(path.resolve())] = file_state(path)
    if not any(Path(name).is_relative_to(paths[2].resolve()) for name in result):
        raise CycleError('Pasta de avisos do SDK vazia; forneça as licenças do runtime e bibliotecas.')
    command = sdk['python']
    if not isinstance(command, list) or not command or not all(isinstance(p, str) and p for p in command):
        raise CycleError('sdk.python deve ser uma lista de argumentos.')
    # Registrar o executável local quando existe; versões do backend são verificadas por probe.
    executable = shutil.which(command[0])
    if executable:
        result['controller_executable'] = file_state(Path(executable).resolve())
    return dict(config=sdk, files=result)


def verify_bundle(path, *, installed=False):
    from scripts import atualizar_entrega_deck as delivery
    path = Path(path)
    if installed:
        delivery._target_path(path, 'manifest.json')
    rows, raw = delivery._read_manifest(path)
    if not installed and delivery._source_files(path) != set(rows) | {'manifest.json'}:
        raise CycleError('Pacote tem arquivos ausentes ou extras.')
    for name, row in rows.items():
        delivery._check_file(delivery._target_path(path, name) if installed else path/name, row)
    return digest({name: file_state(path/name) for name in rows} | {'manifest': raw.hex()})


def csp_input(local):
    value = local.get('csp_zip')
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise CycleError('csp_zip deve indicar um arquivo CSP existente.')
    path = Path(value).absolute()
    state = file_state(path)
    if state is None:
        raise CycleError('csp_zip não encontrado: '+str(path))
    return dict(path=str(path), state=state)


def run_build(git, folder, recipe, local, source_commit, entries, run):
    sdk = local.get('sdk', {})
    sdk_before = sdk_inputs(sdk)
    probe = run(sdk['python']+['-c', PROBE], capture=True)
    observed = json.loads(probe)
    expected = recipe['sdk']
    if (observed['platform'] != 'linux' or observed['architecture'] != 'x86_64'
            or observed['python'] != expected['python'] or observed['packages'] != expected['packages']):
        raise CycleError('SDK incompatível com a receita; configure o runtime declarado, sem troca automática.')
    for tool in ('readelf',):
        # A existência no backend é conferida pelo próprio subprocesso.
        run(sdk['python']+['-c', 'import shutil,sys;sys.exit(0 if shutil.which(sys.argv[1]) else 1)', tool])
    # O payload é verificado integralmente antes de reutilizar qualquer arquivo estático.
    payload = Path(local.get('payload', git.root/'entrega/deck')).resolve()
    payload_hash = verify_bundle(payload)
    csp_zip = csp_input(local)
    inputs = dict(source=entries, sdk=sdk_before, payload=payload_hash, recipe=recipe,
                  build_number=local['build_number'])
    if csp_zip is not None:inputs['csp_zip'] = csp_zip
    fingerprint = digest(inputs)
    tree = snapshot(git, folder/'sources'/fingerprint, source_commit, entries)
    backend_snapshot(tree, entries, sdk, run)
    attempt = folder/'build-attempt.json'
    prior = read_json(attempt) if attempt.exists() else {}
    batch = prior['batch'] if prior.get('fingerprint') == fingerprint else 'cycle-'+fingerprint[:20]
    batch_root = tree/'local/work'/batch
    result_path = batch_root/'result.json'
    complete_bundle = batch_root/'papao-linux-x86_64'
    if result_path.exists():
        try:
            result = read_json(result_path)
        except ValueError:
            result = None
    else:
        result = None
    if result is None and (complete_bundle/'manifest.json').exists():
        # Manifesto é gravado depois de código/metadados. Conferir antes de recuperar.
        verify_bundle(complete_bundle)
        result = dict(bundle=str(complete_bundle), archive=None, recovered=True)
    if result is None and batch_root.exists():
        # Uma build incompleta nunca é promovida. Outra tentativa conserva o lote anterior.
        batch += '-'+uuid.uuid4().hex[:8]
    options = ['-B', mapped(tree/'scripts/build_launcher_linux.py', sdk), '--lote', batch,
               '--bibliotecas', mapped(Path(sdk['native']), sdk), '--font', mapped(Path(sdk['font']), sdk),
               '--licenses-dir', mapped(Path(sdk['licenses']), sdk), '--reuse-delivery', mapped(payload, sdk),
               '--source-commit', source_commit, '--build-number', str(local['build_number'])]
    if csp_zip is not None:
        options += ['--csp-zip', mapped(Path(csp_zip['path']), sdk)]
    if result is None:
        atomic_json(attempt, dict(fingerprint=fingerprint, batch=batch))
        run(sdk['python']+options)
        result = read_json(tree/'local/work'/batch/'result.json')
    # Caminhos retornados pelo backend são traduzidos de volta explicitamente.
    for key in ('bundle', 'archive'):
        if result.get(key) and sdk.get('path_map') and not result.get('recovered'):
            for item in sdk['path_map']:
                backend = item['backend'].rstrip('/')+'/'
                if result[key].startswith(backend):
                    result[key] = str(Path(item['local'])/result[key][len(backend):])
                    break
            else:
                raise CycleError('Resultado do backend sem mapeamento local.')
    verify_bundle(result['bundle'])
    if sdk_inputs(sdk) != sdk_before or verify_bundle(payload) != payload_hash or csp_input(local) != csp_zip:
        raise CycleError('SDK/payload/ZIP CSP mudou durante a build; não publicar o resultado.')
    info = read_json(Path(result['bundle'])/'build-info.json')
    if info.get('source_commit') != source_commit or info.get('build_number') != str(local['build_number']):
        raise CycleError('Metadados da build não correspondem ao ciclo.')
    if csp_zip is not None and info.get('csp', {}).get('archive_sha256') != csp_zip['state']['sha256']:
        raise CycleError('CSP da build não corresponde ao ZIP informado.')
    for name, sha in info['source_sha256'].items():
        if file_state(tree/name)['sha256'] != sha:
            raise CycleError('Fontes da build divergem do snapshot: '+name)
    if tuple(map(int, (info['highest_glibc_symbol'] or '0.0').split('.'))) > tuple(map(int, expected['maximum_glibc'].split('.'))):
        raise CycleError('Build exige GLIBC acima da receita; revise o SDK.')
    return result
