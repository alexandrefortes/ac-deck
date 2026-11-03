"""Seleção literal, commit com compare-and-swap e reconciliação antes do push."""
import os
import hashlib
from pathlib import Path
import subprocess
import uuid

from .common import (CycleError, atomic_json, check_path, file_state, locked,
                     process_env, read_json, relative, sync_directory)


def failure(operation, result):
    text = result.stderr.decode('utf-8', errors='replace').lower()
    causes = [
        (('permission denied', 'operation not permitted', 'read-only'), 'permissão de acesso'),
        (('could not resolve', 'could not connect', 'failed to connect', 'timed out'), 'rede/proxy'),
        (('authentication failed', 'could not read username', '403', '401'), 'autenticação/autorização'),
        (('index.lock', 'cannot lock ref'), 'concorrência/trava Git'),
        (('non-fast-forward', 'fetch first', 'rejected'), 'remoto avançado ou regra da branch'),
        (('identity unknown', 'unable to auto-detect'), 'identidade de autoria ausente'),
    ]
    cause = next((label for needles, label in causes if any(n in text for n in needles)),
                 'configuração ou estado Git')
    return CycleError(f'Git {operation}: {cause} (status {result.returncode}). '
                      'Confira o estado e a configuração local; retome após corrigir. Sem retry automático.')


class Git:
    def __init__(self, root, options=None, env=None):
        self.root = Path(root).resolve()
        self.options = list(options or [])
        self.env = process_env(env)
        for key in ('GIT_INDEX_FILE', 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR',
                    'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'):
            self.env.pop(key, None)
        self.env.update(GIT_TERMINAL_PROMPT='0', GIT_LITERAL_PATHSPECS='1')

    def run(self, *args, data=None, index=None, check=True, extra_env=None):
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        if index is not None:
            env['GIT_INDEX_FILE'] = str(Path(index).resolve())
        try:
            result = subprocess.run(['git', *self.options, '-C', str(self.root), *args],
                                    input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        except FileNotFoundError as exc:
            raise CycleError('Git indisponível. Configure a ferramenta neste ambiente.') from exc
        if check and result.returncode:
            raise failure(args[0], result)
        return result

    def text(self, *args, **kwargs):
        return self.run(*args, **kwargs).stdout.decode('utf-8').strip()

    def path(self, name):
        path = Path(self.text('rev-parse', '--git-path', name))
        return path if path.is_absolute() else self.root/path

    def entries(self, index=None):
        rows = {}
        for item in self.run('ls-files', '--stage', '-z', index=index).stdout.split(b'\0'):
            if not item:
                continue
            header, path = item.split(b'\t', 1)
            mode, oid, stage = header.decode().split()
            if stage != '0':
                raise CycleError('Índice contém conflito; resolva antes de publicar.')
            rows[path.decode('utf-8')] = [mode, oid]
        return rows

    def ancestor(self, older, newer):
        result = self.run('merge-base', '--is-ancestor', older, newer, check=False)
        if result.returncode not in (0, 1):
            raise failure('merge-base', result)
        return result.returncode == 0


def hooks_absent(git):
    # commit-tree não executa os hooks de commit. Recusar em vez de ignorá-los.
    for name in ('pre-commit', 'prepare-commit-msg', 'commit-msg', 'post-commit'):
        path = git.path('hooks')/name
        if path.is_file() and (os.name == 'nt' or os.access(path, os.X_OK)):
            raise CycleError('Hook de commit ativo: '+name+'. Use o fluxo habitual com esse hook; '
                             'o ciclo não o desativa nem publica ignorando-o.')


def index_records(git, entries, paths):
    zero = '0'*len(git.text('rev-parse', 'HEAD'))
    return b''.join(((' '.join(entries[name]) if entries.get(name) else '0 '+zero)+
                     '\t'+name+'\0').encode('utf-8') for name in paths)


def prepare(git, folder, paths, message, *, branch='main', remote=None, exemptions=None):
    folder = Path(folder).resolve()
    receipt = folder/'publication.json'
    if receipt.exists():
        state = read_json(receipt)
        if (sorted(set(paths)) != state['paths'] or message.rstrip() != state['subject']
                or branch != state['branch'] or remote != state['remote']):
            raise CycleError('Publicação já preparada com outras entradas; use outro ciclo.')
        return state
    hooks_absent(git)
    paths = sorted(set(relative(p) for p in paths))
    if not paths or not message.strip():
        raise CycleError('Seleção e mensagem precisam ser explícitas.')
    git.run('check-ref-format', 'refs/heads/'+branch)
    if remote and (remote.startswith('-') or '://' in remote or '/' in remote or '\\' in remote):
        raise CycleError('Informe o nome de um remote configurado, sem URL ou credencial.')
    if remote:
        git.run('remote', 'get-url', '--push', remote)
    local_ref = git.text('symbolic-ref', 'HEAD')
    base = git.text('rev-parse', 'HEAD')
    original = git.entries()
    folder.mkdir(parents=True, exist_ok=True)
    index = folder/'publication.index'
    check_path(index)
    if index.exists():
        index.unlink()  # Só o índice privado; nenhuma referência foi alterada nesta fase.
    git.run('read-tree', base, index=index)
    base_entries = git.entries(index)
    before = {p: file_state(git.root/p) for p in paths}
    if any(before[p] is None and p not in base_entries for p in paths):
        raise CycleError('Arquivo inexistente e não rastreado no commit-base na seleção.')
    git.run('add', '--all', '--pathspec-from-file=-', '--pathspec-file-nul',
            data=b''.join(p.encode()+b'\0' for p in paths), index=index)
    desired = git.entries(index)
    for p in paths:
        if desired.get(p, ['100644'])[0] not in ('100644', '100755'):
            raise CycleError('Selecione somente arquivos regulares: '+p)
        if original.get(p) not in (base_entries.get(p), desired.get(p)):
            raise CycleError('Staging parcial/divergente na seleção; preserve e revise: '+p)
    if {p: file_state(git.root/p) for p in paths} != before:
        raise CycleError('Seleção mudou durante a preparação.')
    tree = git.text('write-tree', index=index)
    if tree == git.text('rev-parse', base+'^{tree}'):
        raise CycleError('Seleção sem alterações para commit.')
    exemptions = exemptions or {}
    for p, sha in exemptions.items():
        entry = desired.get(p)
        if (p not in before or not before[p] or before[p]['sha256'] != sha or not entry
                or hashlib.sha256(git.run('cat-file', 'blob', entry[1]).stdout).hexdigest() != sha):
            raise CycleError('Exceção de whitespace sem hash exato nos bytes staged: '+p)
    for p in paths:
        if p not in exemptions and git.run('diff', '--cached', '--check', base, '--', p,
                                          index=index, check=False).returncode:
            raise CycleError('Whitespace inválido em arquivo próprio: '+p)
    identity = {}
    for role in ('AUTHOR', 'COMMITTER'):
        # Salvar identidade/data antes de criar o objeto torna commit-tree repetível.
        ident = git.text('var', 'GIT_'+role+'_IDENT')
        person, date = ident.rsplit('> ', 1)
        name, email = person.rsplit(' <', 1)
        identity.update({f'GIT_{role}_NAME': name, f'GIT_{role}_EMAIL': email,
                         f'GIT_{role}_DATE': date})
    token = uuid.uuid4().hex
    state = dict(schema=1, token=token, base=base, branch=branch, local_ref=local_ref,
                 remote=remote, root=str(git.root), tree=tree, paths=paths, files=before,
                 original_index={p: original.get(p) for p in paths},
                 desired_index={p: desired.get(p) for p in paths}, identity=identity,
                 subject=message.rstrip(), message=message.rstrip()+'\n\nDelivery-Cycle: '+token+'\n',
                 commit=None, synced=False, published=False)
    atomic_json(receipt, state)
    return state


def _check_commit(git, commit, state):
    return (git.text('rev-parse', commit+'^{tree}') == state['tree']
            and git.text('rev-list', '--parents', '-n', '1', commit).split() == [commit, state['base']]
            and git.text('log', '-1', '--format=%B', commit) == state['message'].strip())


def _sync_index(git, folder, state):
    path = git.path('index')
    lock = path.with_name(path.name+'.lock')
    check_path(lock)
    # O lock nativo também protege contra git add/commit de outras sessões.
    try:
        stream = lock.open('xb')
    except FileExistsError as exc:
        raise CycleError('index.lock existente. Confira a operação Git ativa; não remova por idade/PID.') from exc
    owned = os.fstat(stream.fileno())
    try:
        current = git.entries()
        for p in state['paths']:
            if current.get(p) not in (state['original_index'][p], state['desired_index'][p]):
                raise CycleError('Staging mudou; preserve e revise: '+p)
        if git.text('rev-parse', 'HEAD') != state['commit']:
            raise CycleError('HEAD avançou antes de sincronizar o índice. Revise o staging.')
        temporary = folder/'sync.index'
        check_path(temporary)
        if path.exists():
            temporary.write_bytes(path.read_bytes())
        else:
            git.run('read-tree', state['base'], index=temporary)
        git.run('update-index', '-z', '--index-info', index=temporary,
                data=index_records(git, state['desired_index'], state['paths']))
        stream.write(temporary.read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
        os.replace(lock, path)
        sync_directory(path.parent)
    finally:
        stream.close()
        if lock.exists() and (lock.stat().st_dev, lock.stat().st_ino) == (owned.st_dev, owned.st_ino):
            lock.unlink()


def publish(git, folder, *, push=False):
    folder = Path(folder).resolve()
    receipt = folder/'publication.json'
    common = Path(git.text('rev-parse', '--git-common-dir'))
    if not common.is_absolute():
        common = git.root/common
    with locked(common/'ciclo-entrega.lock'):
        state = read_json(receipt)
        if str(git.root) != state['root'] or git.text('symbolic-ref', 'HEAD') != state['local_ref']:
            raise CycleError('Checkout/branch mudou após o plano.')
        hooks_absent(git)
        head = git.text('rev-parse', 'HEAD')
        commit = state['commit']
        if commit is None:
            if head != state['base']:
                raise CycleError('HEAD avançou; revise a integração e crie outro plano.')
            if {p: file_state(git.root/p) for p in state['paths']} != state['files']:
                raise CycleError('Seleção mudou após preparar o commit; faça novo plano.')
            current = git.entries()
            if any(current.get(p) not in (state['original_index'][p], state['desired_index'][p])
                   for p in state['paths']):
                raise CycleError('Staging mudou após o plano; preserve e revise.')
            if git.text('write-tree', index=folder/'publication.index') != state['tree']:
                raise CycleError('Índice da publicação divergiu.')
            sign = git.text('config', '--get', 'commit.gpgSign', check=False).lower() == 'true'
            commit = git.text('commit-tree', state['tree'], '-p', state['base'],
                              *(['-S'] if sign else []), data=state['message'].encode(),
                              extra_env=state['identity'])
            state['commit'] = commit
            atomic_json(receipt, state)  # Intenção durável antes de mover a referência.
        if not _check_commit(git, commit, state):
            raise CycleError('Commit registrado divergiu; revise sem recriar commit.')
        if head == state['base']:
            git.run('update-ref', '-m', 'delivery-cycle '+state['token'],
                    state['local_ref'], commit, state['base'])
        elif not git.ancestor(commit, head):
            raise CycleError('HEAD divergiu; integre sem recriar o commit registrado.')
        if not state['synced']:
            _sync_index(git, folder, state)
            state['synced'] = True
            atomic_json(receipt, state)
        if push:
            remote = state['remote']
            if not remote:
                raise CycleError('Remote explícito necessário para push.')
            ref = 'refs/heads/'+state['branch']
            # ls-remote usa URL de push (pode diferir da URL de fetch).
            destination = git.text('remote', 'get-url', '--push', remote)

            def tip():
                rows = git.text('ls-remote', '--refs', destination, ref).splitlines()
                return rows[0].split()[0] if rows else None

            def contains(observed):
                if not observed:
                    return False
                if git.run('cat-file', '-e', observed+'^{commit}', check=False).returncode:
                    git.run('fetch', '--no-tags', '--no-write-fetch-head', destination, ref)
                return git.ancestor(commit, observed)

            observed = tip()
            if not contains(observed):
                if observed and not git.ancestor(observed, commit):
                    raise CycleError('Remoto avançou/divergiu. Revise e integre; nenhum force ou retry.')
                result = git.run('push', destination, commit+':'+ref, check=False)
                observed = tip()  # Resposta perdida pode esconder um push efetivado.
                if not contains(observed):
                    raise failure('push não confirmado', result)
            state.update(published=True, remote_tip=observed)
            atomic_json(receipt, state)
        return state
