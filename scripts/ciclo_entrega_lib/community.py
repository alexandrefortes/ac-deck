"""Candidato comunitário local: fontes curadas, SDK persistente e recibos retomáveis."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from .common import CycleError, atomic_json, check_path, digest, file_state, process_env, read_json
from .publication import Git

STEPS = ('preflight', 'snapshot', 'test', 'build', 'package', 'verify')
SDK_PROBE = '''import importlib.metadata as m, importlib.util as u, json, platform, pathlib, sys
names={'pyinstaller':'PyInstaller','pyinstaller-hooks-contrib':'_pyinstaller_hooks_contrib','Pillow':'PIL'}
print(json.dumps(dict(python=platform.python_version(),platform=sys.platform,architecture=platform.machine(),
 packages={n:m.version(n) for n in names},
 locations={n:str(pathlib.Path(u.find_spec(module).origin).resolve()) for n,module in names.items()})))'''


def inventory(root):
    root = Path(root)
    check_path(root)
    if not root.is_dir():
        raise CycleError('Diretório ausente: '+str(root))
    return {p.relative_to(root).as_posix(): file_state(p) for p in sorted(root.rglob('*'))
            if p.is_file() or p.is_symlink()}


def python_inventory(root):
    """Links do próprio SDK são registrados, sem seguir links para fora dele."""
    root = Path(root).resolve(strict=True)
    rows = {}
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            if not path.resolve(strict=True).is_relative_to(root):
                raise CycleError('Link do SDK aponta para fora da árvore: '+name)
            rows[name] = dict(link=os.readlink(path))
        elif path.is_file():
            row = file_state(path)
            rows[name] = dict(sha256=row['sha256'], size=row['size'])
    return rows


def sdk_inventory(root, local, output):
    """Operação explícita de setup; nunca é chamada automaticamente durante build."""
    path = Path(output).absolute()
    check_path(path)
    if path.exists():
        raise CycleError('Inventário já existe; preserve-o e use outro arquivo para revisão.')
    rows = python_inventory(local['sdk']['python_root'])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(dict(schema=1, files=rows), stream, sort_keys=True, indent=2)
        stream.write('\n')
    return dict(inventory=str(path), entries=len(rows), sha256=file_state(path)['sha256'])


def source_inputs(root, local):
    from scripts import exportar_ac_deck as exporter
    from scripts import build_launcher_linux as builder
    public = (root/exporter.MANIFEST).exists()
    notices = Path(local.get('community', {}).get('notices', root))
    check_path(notices)
    rows = {}
    for name in exporter.selected_sources():
        source = name if public else exporter.SOURCE_ALIASES.get(name, name)
        rows[name] = dict(source_path=source, **exporter.fingerprint(root/source))
    for name in builder.COMMUNITY_NOTICES:
        rows[name] = dict(source_path=str(notices/name), **exporter.fingerprint(notices/name))
    for name in (exporter.MANIFEST, 'community-changes-manifest.json'):
        if (root/name).exists():
            rows[name] = dict(source_path=name, **exporter.fingerprint(root/name))
    git = Git(root, env={'GIT_OPTIONAL_LOCKS': '0'})
    top = git.run('rev-parse', '--show-toplevel', check=False)
    base = (git.text('rev-parse', 'HEAD') if top.returncode == 0
            and Path(top.stdout.decode().strip()).resolve() == root else None)
    return dict(source_tree='working-tree', source_base=base, files=rows)


def check_work_modes(work):
    check_path(work)
    work.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.ac-deck-mode-', dir=work)
    try:
        for mode in (0o644, 0o755):
            os.fchmod(descriptor, mode)
            if os.fstat(descriptor).st_mode & 0o777 != mode:
                raise CycleError('community.work não preserva modos POSIX 644/755; use um filesystem Linux.')
    finally:
        os.close(descriptor)
        Path(name).unlink()


def inputs(root, recipe, local):
    sdk, config = local.get('sdk', {}), local.get('community', {})
    required = ('python_root', 'python_manifest', 'native', 'font', 'licenses')
    if (not sdk.get('python') or not isinstance(sdk['python'], list)
            or any(not sdk.get(k) or not Path(sdk[k]).is_absolute() for k in required)
            or not config.get('work') or not Path(config['work']).is_absolute()):
        raise CycleError('Configure SDK e community.work absolutos em local/ciclo-entrega.json.')
    work = Path(config['work']).absolute()
    protected = [Path(sdk[name]).absolute() for name in
                 ('python_root', 'native', 'licenses', 'font', 'python_manifest')]
    if any(work == path or work.is_relative_to(path) or path.is_relative_to(work) for path in protected):
        raise CycleError('community.work deve ficar separado da árvore e das entradas do SDK.')
    if work == root or root.is_relative_to(work):
        raise CycleError('community.work não pode conter a origem.')
    if work.exists() and not work.is_dir():
        raise CycleError('community.work existente deve ser um diretório; arquivo preservado.')
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise CycleError('Perfil comunitário exige execução explícita no Linux x86_64/WSL.')
    check_work_modes(work)
    python_root = Path(sdk['python_root']).resolve(strict=True)
    executable = Path(sys.executable).resolve(strict=True)
    if not executable.is_relative_to(python_root) or sdk['python'] != [str(Path(sys.executable).absolute())]:
        raise CycleError('Execute o controlador com o sdk.python configurado, sem trocar o runtime.')
    observed = json.loads(subprocess.check_output(sdk['python']+['-B', '-c', SDK_PROBE],
                         env=process_env({'PYTHONNOUSERSITE':'1'})))
    if (observed['python'] != recipe['sdk']['python'] or observed['packages'] != recipe['sdk']['packages']
            or observed['platform'] != 'linux' or observed['architecture'] != 'x86_64'
            or any(not Path(path).is_relative_to(python_root) for path in observed['locations'].values())):
        raise CycleError('SDK incompatível com as versões fixadas na receita.')
    python_files = python_inventory(python_root)
    expected = read_json(sdk['python_manifest'])['files']
    def approved(name, row):
        actual = python_files.get(name)
        if 'link' in row:
            return actual == row
        return (actual is not None and actual.get('sha256') == row.get('sha256')
                and actual.get('size') == row.get('size', row.get('size_bytes')))
    if set(python_files) != set(expected) or any(not approved(name, row) for name, row in expected.items()):
        raise CycleError('SDK diverge do inventário aprovado; não atualizar nem baixar dependências na build.')
    native, licenses = inventory(sdk['native']), inventory(sdk['licenses'])
    if not native or not licenses or not file_state(sdk['font']):
        raise CycleError('SDK exige bibliotecas, fonte e avisos não vazios.')
    tools = {}
    for name in ('readelf', 'ldd'):
        path = shutil.which(name)
        if not path:
            raise CycleError('Ferramenta ausente no backend: '+name)
        tools[name] = dict(path=path, state=file_state(Path(path).resolve()))
    check_path(work)
    source = source_inputs(root, local)
    dependencies = {}
    elf_inputs = [Path(sdk['native'])/name for name in native]
    elf_inputs += [python_root/name for name in python_files if '.so' in Path(name).name
                   or Path(name).name in ('python3.13', 'run', 'run_d')]
    dependency_env = process_env({'LD_LIBRARY_PATH': sdk['native'], 'PYTHONNOUSERSITE': '1'})
    for path in elf_inputs:
        if path.is_symlink() or path.read_bytes()[:4] != b'\x7fELF':
            continue
        dependency_env['LD_LIBRARY_PATH'] = sdk['native']+':'+str(path.parent)
        result = subprocess.run(['ldd', str(path)], env=dependency_env, capture_output=True, text=True)
        if result.returncode or 'not found' in result.stdout:
            raise CycleError('Dependência ELF indisponível no SDK: '+str(path))
        for name in re.findall(r'(?:=>\s+|^\s*)(/[^\s()]+)', result.stdout, re.MULTILINE):
            resolved = str(Path(name).resolve())
            dependencies[resolved] = file_state(resolved)
    return dict(**source, recipe=recipe, config=dict(sdk=sdk, community=config),
                sdk=dict(observed=observed, python_manifest=file_state(sdk['python_manifest']),
                         python_files=python_files, native=native, font=file_state(sdk['font']), licenses=licenses),
                environment=dict(platform=platform.platform(), libc=list(platform.libc_ver()),
                                 executable=str(executable), tools=tools, dependencies=dependencies,
                                 variables={key:os.environ.get(key) for key in
                                            ('LANG', 'LC_ALL', 'TZ', 'SOURCE_DATE_EPOCH')}))


def verify_snapshot(tree, rows):
    from scripts.exportar_ac_deck import fingerprint
    actual = set()
    check_path(tree)
    for directory, directories, files in os.walk(tree):
        for name in list(directories):
            path = Path(directory)/name
            if path.is_symlink():
                raise CycleError('Link inesperado no snapshot: '+str(path))
            if path.relative_to(tree).as_posix() == 'local/work':
                directories.remove(name)
        actual.update((Path(directory)/name).relative_to(tree).as_posix() for name in files)
    if actual != set(rows):
        raise CycleError('Snapshot tem arquivos ausentes ou extras.')
    for name, row in rows.items():
        if fingerprint(tree/name) != {k: row[k] for k in ('sha256', 'size_bytes', 'mode')}:
            raise CycleError('Snapshot mudou: '+name)


class Runner:
    def __init__(self, root, folder, state, recipe, local):
        self.root, self.folder, self.state = root, folder, state
        self.recipe, self.local = recipe, local
        self.log = None

    def command(self, args, *, cwd=None, env=None, timeout=None):
        child = process_env()
        child['PYTHONNOUSERSITE'] = '1'
        for name in ('LD_LIBRARY_PATH', 'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER'):
            child.pop(name, None)
        child.update(env or {})
        with self.log.open('ab') as stream:
            result = subprocess.run([str(x) for x in args], cwd=cwd or self.root,
                                    env=child, stdout=stream, stderr=stream, timeout=timeout)
        if result.returncode:
            raise CycleError(f'Subprocesso terminou com status {result.returncode}; log: {self.log}')

    def artifact(self, step, result, plan):
        from .community_verify import verify_bundle
        if step == 'snapshot':
            verify_snapshot(Path(result['tree']), plan['inputs']['files'])
            return digest(plan['inputs']['files'])
        if step == 'test':
            return digest(file_state(result['log']))
        if step in ('build', 'package', 'verify'):
            if file_state(result['archive'])['sha256'] != result['archive_sha256']:
                raise CycleError('Arquivo tar diverge do hash registrado pelo builder.')
            value = dict(bundle=verify_bundle(result['bundle'], plan['inputs']),
                         archive=file_state(result['archive']))
            if step == 'package':
                value['relocated'] = verify_bundle(result['relocated'], plan['inputs'])
            if step == 'verify':
                value['evidence'] = inventory(result['evidence'])
            return digest(value)
        return None

    def previous(self, step):
        row = self.state['steps'].get(step, {})
        if row.get('status') != 'done':
            raise CycleError('Etapa necessária ainda não concluiu: '+step)
        return row['result']

    def perform(self, step, plan, attempt):
        from . import community_verify as checks
        if step == 'preflight':
            return dict(input_sha256=digest(plan['inputs']), status='verified')
        if step == 'snapshot':
            destination = Path(self.local['community']['work'])/plan['id']/('source-'+attempt.name)
            check_path(destination)
            destination.mkdir(parents=True)
            from src.launcher.file_io import copy_verified
            for name, row in plan['inputs']['files'].items():
                source = self.root/row['source_path']
                copy_verified(source, destination/name, row['sha256'])
                (destination/name).chmod(row['mode'])
            verify_snapshot(destination, plan['inputs']['files'])
            return dict(tree=str(destination))
        tree = Path(self.previous('snapshot')['tree'])
        verify_snapshot(tree, plan['inputs']['files'])
        sdk = self.local['sdk']
        if step == 'test':
            started = time.monotonic()
            self.command(sdk['python']+['-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                         cwd=tree, env={'LD_LIBRARY_PATH': sdk['native']})
            text = self.log.read_text(errors='replace')
            counts = re.findall(r'Ran (\d+) tests? in', text)
            if not counts:
                raise CycleError('Suíte não produziu contagem de testes; confira o log.')
            return dict(tests=int(counts[-1]), skipped=sum(map(int, re.findall(r'skipped=(\d+)', text))),
                        log=str(self.log), process_seconds=round(time.monotonic()-started, 3))
        if step == 'build':
            self.previous('test')
            batch = 'community-'+attempt.name
            self.command(sdk['python']+['-B', str(tree/'scripts/build_launcher_linux.py'), '--community',
                         '--lote', batch, '--bibliotecas', sdk['native'], '--font', sdk['font'],
                         '--licenses-dir', sdk['licenses'], '--community-notices', str(tree)], cwd=tree)
            result = read_json(tree/'local/work'/batch/'result.json')
            return {k: result[k] for k in ('bundle', 'archive', 'archive_sha256', 'archive_bytes', 'timings')}
        runtime = Path(self.local['community']['work'])/plan['id']/('runtime-'+attempt.name)
        check_path(runtime)
        runtime.mkdir(parents=True)
        if step == 'package':
            result = dict(self.previous('build'))
            started = time.monotonic()
            relocated = runtime/'relocation check'/'package with spaces'
            checks.verify_archive(result['archive'], result['bundle'], relocated)
            result['relocated'] = str(relocated)
            result['package_validation_seconds'] = round(time.monotonic()-started, 3)
            return result
        result = dict(self.previous('package'))
        checks.verify(result, plan['inputs'], tree, runtime, self.command, sdk)
        result.update(evidence=str(runtime/'evidence'), candidate='validated-local', published=False,
                      physical_deck=False, accepted=False)
        return result

    def execute(self, plan, until=None):
        if any(step not in STEPS for step in plan['steps']):
            raise CycleError('Etapa de promoção não pertence ao candidato comunitário.')
        for step in plan['steps']:
            input_started = time.monotonic()
            current_inputs = inputs(self.root, self.recipe, self.local)
            input_seconds = round(time.monotonic()-input_started, 3)
            if current_inputs != plan['inputs']:
                raise CycleError('Fontes/SDK/receita/ambiente divergem do plano; preserve e crie outro ciclo.')
            old = self.state['steps'].get(step, {})
            if old.get('status') == 'done':
                if old.get('input') != digest(current_inputs) or self.artifact(step, old['result'], plan) != old.get('artifact'):
                    raise CycleError('Artefato concluído mudou; preserve e revise antes de retomar.')
                print(step+': reutilizado', flush=True)
            else:
                attempt = self.folder/'attempts'/(step+'-'+uuid.uuid4().hex[:12])
                check_path(attempt)
                attempt.mkdir(parents=True)
                self.log = attempt/'run.log'
                self.log.touch()
                row = dict(status='running', input=digest(current_inputs), log=str(self.log),
                           input_verification_seconds=input_seconds,
                           started_utc=datetime.now(timezone.utc).isoformat(), attempt=str(attempt))
                self.state['steps'][step] = row
                atomic_json(self.folder/'state.json', self.state)
                atomic_json(attempt/'receipt.json', row)
                started = time.monotonic()
                try:
                    result = self.perform(step, plan, attempt)
                    row['result'] = result
                    artifact = self.artifact(step, result, plan)
                    after_started = time.monotonic()
                    after = inputs(self.root, self.recipe, self.local)
                    row['post_input_verification_seconds'] = round(time.monotonic()-after_started, 3)
                    if after != current_inputs:
                        raise CycleError('Entradas mudaram durante a etapa; preserve o resultado para revisão.')
                    row.update(status='done', artifact=artifact)
                except Exception as exc:
                    row.update(status='failed', error=str(exc))
                    raise
                finally:
                    row['seconds'] = round(time.monotonic()-started, 3)
                    atomic_json(attempt/'receipt.json', row)
                    atomic_json(self.folder/'state.json', self.state)
                print(step+': concluído', flush=True)
            if step == until:
                break
        return self.state
