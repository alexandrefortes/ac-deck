#!/usr/bin/env python3
"""Ciclo de entrega portável (Python >= 3.10). Estado local; nenhuma instalação global."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.ciclo_entrega_lib.common import (CycleError, atomic_json, check_path, digest,
                                             file_state, locked, process_env, read_json, relative)
from scripts.ciclo_entrega_lib.publication import Git, prepare, publish
from scripts.ciclo_entrega_lib import build as builds
from scripts.ciclo_entrega_lib import community

STEPS = ('test', 'build', 'package', 'apply', 'publish')
RETIRED_CSP = 'mods/lights-patch-v0.3.0-preview728-full.zip'


def check_selection(root, paths):
    for p in paths:
        if p == RETIRED_CSP and file_state(root/p) is None:
            continue
        if (p.split('/')[0].casefold() in ('local', 'mods', 'tools', '.aws', '.codex')
                or p.startswith('.env') or '/private/' in p or '/sessions/' in p):
            raise CycleError('Seleção contém dados privados/locais não publicáveis.')


def folder_for(root, cycle):
    if not cycle or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in cycle):
        raise CycleError('Identificador inválido; use letras, números, hífen e sublinhado.')
    path = root/'local/work/ciclos'/cycle
    check_path(path)
    return path


def configuration(root):
    recipe = read_json(root/'scripts/ciclo-entrega.json')
    local_path = root/'local/ciclo-entrega.json'
    local = read_json(local_path) if local_path.exists() else {}
    # Configuração relativa pertence ao checkout, nunca ao cwd do invocador.
    for key in ('payload', 'csp_zip'):
        if local.get(key):
            local[key] = str((root/local[key]).absolute())
    sdk = local.get('sdk', {})
    for key in ('native', 'font', 'licenses'):
        if sdk.get(key):
            sdk[key] = str((root/sdk[key]).absolute())
    for item in sdk.get('path_map', []):
        item['local'] = str((root/item['local']).absolute())
    if recipe.get('schema') != 1 or sys.version_info[:2] < tuple(recipe['minimum_python']):
        raise CycleError('Receita ou versão Python não suportada.')
    return recipe, local


def doctor(root, recipe, local):
    git = Git(root)
    result = dict(python=platform.python_version(), platform=sys.platform, architecture=platform.machine(),
                  checkout=git.text('rev-parse', '--show-toplevel'),
                  branch=git.text('symbolic-ref', '--short', 'HEAD'), head=git.text('rev-parse', 'HEAD'),
                  git=git.text('--version'), target=recipe['target'],
                  sdk_configured=bool(local.get('sdk')), build_ready=False)
    if local.get('sdk'):
        try:
            builds.sdk_inputs(local['sdk'])
            observed = json.loads(subprocess.check_output(local['sdk']['python']+['-c', builds.PROBE],
                                                          env=process_env(), stderr=subprocess.DEVNULL))
            result['build_ready'] = (observed['platform'] == 'linux' and observed['architecture'] == 'x86_64'
                                     and observed['python'] == recipe['sdk']['python']
                                     and observed['packages'] == recipe['sdk']['packages'])
            result['sdk_observed'] = observed
        except (OSError, subprocess.CalledProcessError, ValueError, RuntimeError):
            result['build_issue'] = 'SDK indisponível/incompatível; confira a configuração local.'
    else:
        result['build_issue'] = 'Configure sdk em local/ciclo-entrega.json para compilar; testes/Git disponíveis.'
    return result


def input_files(root, prefixes):
    git = Git(root)
    raw = git.run('ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *prefixes).stdout
    return {name: file_state(root/name) for name in sorted(set(raw.decode('utf-8').split('\0'))- {''})}


def create_plan(root, args, recipe):
    folder = folder_for(root, args.cycle)
    if (folder/'plan.json').exists():
        raise CycleError('Ciclo já existe. Use status/resume ou um identificador novo.')
    allowed = community.STEPS if args.community else STEPS
    steps = (args.steps or (','.join(community.STEPS) if args.community else 'test')).split(',')
    if len(set(steps)) != len(steps) or any(step not in allowed for step in steps):
        raise CycleError('Etapas inválidas.')
    if steps != sorted(steps, key=allowed.index):
        raise CycleError('Use a ordem '+','.join(allowed)+'.')
    if args.community:
        if args.selection_file or args.message_file or args.remote or args.push or args.bundle:
            raise CycleError('Candidato comunitário não aplica nem publica arquivos.')
        _, local = configuration(root)
        inputs = community.inputs(root, recipe, local)
        state = dict(schema=1, id=args.cycle, root=str(root), profile='community',
                     source_commit=inputs['source_base'], created_utc=datetime.now(timezone.utc).isoformat(),
                     steps=steps, inputs=inputs)
        atomic_json(folder/'plan.json', state)
        atomic_json(folder/'state.json', dict(schema=1, steps={}))
        return state
    paths = read_json(args.selection_file) if args.selection_file else []
    if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
        raise CycleError('Seleção deve ser um array JSON de arquivos relativos.')
    paths = sorted(set(relative(p) for p in paths))
    check_selection(root, paths)
    message = Path(args.message_file).read_text(encoding='utf-8') if args.message_file else None
    if 'publish' in steps and (not paths or not message or not args.remote):
        raise CycleError('Publicação exige selection-file, message-file e remote explícitos.')
    groups = args.groups.split(',') if args.groups else []
    if any(g not in recipe['test_groups'] for g in groups):
        raise CycleError('Grupo de testes desconhecido.')
    if 'build' in steps:
        _, local = configuration(root)
        if not local.get('build_number') or not doctor(root, recipe, local)['build_ready']:
            raise CycleError('SDK/build_number indisponível. Configure o ambiente antes do ciclo de build.')
    git = Git(root)
    state = dict(schema=1, id=args.cycle, root=str(root), source_commit=git.text('rev-parse', 'HEAD'),
                 created_utc=datetime.now(timezone.utc).isoformat(), steps=steps, groups=groups,
                 paths=paths, message=message, remote=args.remote, branch=args.branch,
                 push=args.push, exemptions=read_json(args.whitespace_hashes) if args.whitespace_hashes else {},
                 bundle=str(Path(args.bundle).resolve()) if args.bundle else None)
    atomic_json(folder/'plan.json', state)
    atomic_json(folder/'state.json', dict(schema=1, steps={}))
    return state


class Runner:
    def __init__(self, root, folder, state, recipe, local):
        self.root, self.folder, self.state = root, folder, state
        self.recipe, self.local = recipe, local
        self.log = None

    def command(self, args, *, capture=False, test=False):
        started = time.monotonic()
        with self.log.open('ab') as output:
            offset = output.tell()
            try:
                result = subprocess.run(args, cwd=self.root, env=process_env(),
                                        stdout=subprocess.PIPE if capture else output,
                                        stderr=output)
            except FileNotFoundError as exc:
                raise CycleError('Ferramenta ausente. Confira os executáveis locais; log: '+str(self.log)) from exc
        if result.returncode:
            raise CycleError(f'Subprocesso terminou com status {result.returncode}; log: {self.log}. '
                             'Confira falha, skips e permissões; corrija e retome.')
        if capture:
            return result.stdout.decode('utf-8')
        report = dict(seconds=round(time.monotonic()-started, 3))
        if test:
            text = self.log.read_bytes()[offset:].decode('utf-8', errors='replace')
            counts = re.findall(r'Ran (\d+) tests? in', text)
            skipped = re.findall(r'skipped=(\d+)', text)
            report.update(tests=int(counts[-1]) if counts else None,
                          skipped=int(skipped[-1]) if skipped else 0)
        return report

    def inputs(self, step, plan):
        if step == 'test':
            return dict(files=input_files(self.root, ['src', 'scripts', 'tests']),
                        groups={g:self.recipe['test_groups'][g] for g in plan['groups']},
                        python=sys.version, executable=str(Path(sys.executable).resolve()))
        if step == 'build':
            git = Git(self.root)
            sources = builds.source_entries(git, plan['source_commit'])
            if sources != builds.source_entries(git):
                raise CycleError('Fontes Git mudaram desde o plano. Crie novo ciclo para compilar essa revisão.')
            result = dict(sources=sources, sdk=builds.sdk_inputs(self.local.get('sdk', {})),
                          payload=builds.verify_bundle(self.local.get('payload', self.root/'entrega/deck')),
                          recipe=self.recipe, number=self.local.get('build_number'))
            csp_zip = builds.csp_input(self.local)
            if csp_zip is not None:result['csp_zip'] = csp_zip
            return result
        if step == 'package':
            bundle = plan['bundle'] or self.state['steps'].get('build', {}).get('result', {}).get('bundle')
            if not bundle:
                raise CycleError('package exige --bundle no plano ou uma etapa build concluída.')
            info = read_json(Path(bundle)/'build-info.json')
            if info.get('source_commit') != plan['source_commit']:
                raise CycleError('Build não identifica o commit de fontes do plano; confira antes de empacotar.')
            return dict(bundle=bundle, hash=builds.verify_bundle(bundle),
                        tools=input_files(self.root, ['scripts/preparar_entrega_deck.py', 'scripts/deck_bootstrap.sh']))
        if step == 'apply':
            candidate = self.state['steps'].get('package', {}).get('result', {}).get('destination')
            if not candidate:
                raise CycleError('apply exige package concluído.')
            return dict(candidate=candidate, hash=builds.verify_bundle(candidate))
        return dict(paths={p:file_state(self.root/p) for p in plan['paths']}, message=plan['message'])

    def perform(self, step, plan, inputs):
        if step == 'test':
            results = []
            for group in plan['groups']:
                results.append(self.command([sys.executable, '-B', '-X', 'utf8', '-m', 'unittest',
                                             *self.recipe['test_groups'][group], '-v'], test=True))
            return dict(groups=plan['groups'], runs=results)
        if step == 'build':
            if not self.local.get('build_number'):
                raise CycleError('Defina build_number local para gerar metadados novos.')
            return builds.run_build(Git(self.root), self.folder, self.recipe, self.local,
                                    plan['source_commit'], inputs['sources'], self.command)
        if step == 'package':
            from scripts.preparar_entrega_deck import preparar
            candidate = self.folder/'candidates'/digest(inputs)
            candidate.mkdir(parents=True, exist_ok=True)
            result = preparar(inputs['bundle'], projeto=candidate, source_commit=plan['source_commit'])
            # CLI informativa: não abre produto/Steam nem executa sessão.
            if sys.platform == 'linux' and platform.machine() == 'x86_64':
                binary = Path(result['destination'])/'papao.bin'
                self.command([str(binary), '--help'])
                # A entrega fixa comprime a DLL; conferir o mesmo payload verificado
                # na origem evita criar cache/dados privados dentro do candidato.
                self.command([str(binary), 'csp-info', '--kit-csp', str(Path(inputs['bundle'])/'csp')])
            else:
                raise CycleError('Diagnóstico CLI do pacote requer backend Linux x86_64. Execute package nele.')
            return result
        if step == 'apply':
            from scripts.atualizar_entrega_deck import atualizar
            return atualizar(inputs['candidate'], projeto=self.root)
        check_selection(self.root, plan['paths'])
        prepare(Git(self.root), self.folder, plan['paths'], plan['message'],
                branch=plan['branch'], remote=plan['remote'], exemptions=plan['exemptions'])
        return publish(Git(self.root), self.folder, push=plan['push'])

    def reconcile_apply(self, inputs, result):
        from scripts import atualizar_entrega_deck as delivery
        target = self.root/'entrega/deck'
        candidate = Path(inputs['candidate'])
        journal = self.root/'local/work/delivery-update/active.json'
        if result.get('destination') != str(target) or result.get('journal') != str(journal):
            raise CycleError('Resultado de aplicação diverge do destino ou journal; preserve e revise.')
        state = read_json(journal)
        rows, raw = delivery._read_manifest(candidate)
        sha = hashlib.sha256(raw).hexdigest()
        if (state.get('complete') is not True or state.get('target') != str(target)
                or state.get('source') != str(candidate) or state.get('manifest_sha256') != sha
                or result.get('manifest_sha256') != sha or not isinstance(state.get('old'), dict)
                or state.get('new') != {name: file_state(candidate/name) for name in rows}):
            raise CycleError('Journal concluído não corresponde ao candidato; preserve e revise.')
        removed = set(state['old'])-set(rows)
        if sorted(removed) != sorted(result.get('removed', [])):
            raise CycleError('Remoções do journal divergem do resultado; preserve e revise.')
        for name in removed:
            if relative(name) != name or name.split('/')[0].casefold() in delivery.RESERVED:
                raise CycleError('Path inválido no journal de aplicação.')
            if file_state(delivery._target_path(target, name)) is not None:
                raise CycleError('Arquivo removido reapareceu; preserve e revise: '+name)
        artifact = builds.verify_bundle(target, installed=True)
        if artifact != inputs['hash']:
            raise CycleError('Entrega aplicada diverge do candidato; preserve e revise.')
        return artifact

    def execute(self, plan, until=None):
        for step in plan['steps']:
            old = self.state['steps'].get(step, {})
            # Após preparar o commit, a reconciliação Git é a autoridade sobre seus efeitos.
            publication_exists = step == 'publish' and (self.folder/'publication.json').exists()
            inputs = None if publication_exists else self.inputs(step, plan)
            key = digest(inputs)
            if (step == 'apply' and old.get('status') == 'failed' and old.get('input') == key
                    and isinstance(old.get('result'), dict)):
                artifact = self.reconcile_apply(inputs, old['result'])
                old.update(status='done', artifact=artifact)
                old.pop('error', None)
                atomic_json(self.folder/'state.json', self.state)
                print('apply: reconciliado', flush=True)
            elif step != 'publish' and old.get('status') == 'done' and old.get('input') == key:
                result = old['result']
                artifact = result.get('bundle') if step == 'build' else result.get('destination')
                if artifact:
                    if builds.verify_bundle(artifact, installed=step == 'apply') != old['artifact']:
                        raise CycleError('Artefato concluído mudou; preserve e revise: '+str(artifact))
                print(step+': reutilizado', flush=True)
            else:
                self.log = self.folder/(step+'.log')
                check_path(self.log)
                self.log.touch(exist_ok=True)
                current = dict(status='running', input=key, log=str(self.log))
                self.state['steps'][step] = current
                atomic_json(self.folder/'state.json', self.state)
                started = time.monotonic()
                try:
                    result = self.perform(step, plan, inputs)
                    # Não aceitar testes/build se as entradas mudaram durante a etapa.
                    if step != 'publish' and self.inputs(step, plan) != inputs:
                        raise CycleError('Entradas mudaram durante '+step+'; retome após estabilizar o checkout.')
                    current.update(status='done', result=result)
                    artifact = result.get('bundle') if step == 'build' else result.get('destination')
                    if artifact:
                        current['artifact'] = builds.verify_bundle(artifact, installed=step == 'apply')
                except Exception as exc:
                    current.update(status='failed', error=str(exc))
                    raise
                finally:
                    current['seconds'] = round(time.monotonic()-started, 3)
                    atomic_json(self.folder/'state.json', self.state)
                    with self.log.open('a', encoding='utf-8') as output:
                        output.write(json.dumps(dict(step=step, status=current['status'],
                            seconds=current['seconds'], error=current.get('error')),
                            ensure_ascii=False)+'\n')
                print(f"{step}: concluído ({current['seconds']} s)", flush=True)
            if step == until:
                break
        return self.state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=ROOT)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor').add_argument('--community', action='store_true')
    sub.add_parser('sdk-inventory').add_argument('--output', type=Path, required=True)
    plan = sub.add_parser('plan')
    for command in dict.fromkeys(('status', 'resume', *STEPS, *community.STEPS)):
        sub.add_parser(command).add_argument('--cycle', required=True)
    plan.add_argument('--cycle', required=True)
    plan.add_argument('--steps')
    plan.add_argument('--community', action='store_true')
    plan.add_argument('--groups', default='cycle')
    plan.add_argument('--selection-file', type=Path)
    plan.add_argument('--message-file', type=Path)
    plan.add_argument('--whitespace-hashes', type=Path)
    plan.add_argument('--remote')
    plan.add_argument('--branch', default='main')
    plan.add_argument('--push', action='store_true')
    plan.add_argument('--bundle', type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.project.resolve(strict=True)
        recipe, local = configuration(root)
        if args.command == 'sdk-inventory':
            print(json.dumps(community.sdk_inventory(root, local, args.output), indent=2))
            return 0
        if args.command == 'doctor':
            result = community.inputs(root, recipe, local) if args.community else doctor(root, recipe, local)
            if args.community:
                result = dict(build_ready=True, profile='community', input_sha256=digest(result),
                              source_tree=result['source_tree'], source_base=result['source_base'],
                              source_files=len(result['files']), python_entries=len(result['sdk']['python_files']),
                              native_inputs=len(result['sdk']['native']), sdk_notices=len(result['sdk']['licenses']),
                              sdk_observed=result['sdk']['observed'], work=local['community']['work'])
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        folder = folder_for(root, args.cycle)
        with locked(folder/'cycle.lock'):
            if args.command == 'plan':
                result = create_plan(root, args, recipe)
            else:
                plan = read_json(folder/'plan.json')
                state = read_json(folder/'state.json')
                if plan['root'] != str(root):
                    raise CycleError('Ciclo pertence a outro checkout; crie um plano local.')
                if args.command == 'status':
                    result = dict(id=plan['id'], steps=state['steps'], planned=plan['steps'])
                else:
                    if args.command != 'resume' and args.command not in plan['steps']:
                        raise CycleError('Etapa fora do plano; crie um plano com o escopo correto.')
                    runner_type = community.Runner if plan.get('profile') == 'community' else Runner
                    result = runner_type(root, folder, state, recipe, local).execute(
                        plan, until=None if args.command == 'resume' else args.command)
            # Resumo sem mensagem de commit, seleção completa ou logs extensos.
            if 'steps' in result and isinstance(result['steps'], dict):
                result = dict(id=args.cycle, steps={k:{field:row[field] for field in
                    ('status', 'seconds', 'log', 'error') if field in row} for k,row in result['steps'].items()})
            else:
                result = {k:v for k,v in result.items() if k in ('id', 'steps', 'planned')}
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print('Ciclo interrompido: '+str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
