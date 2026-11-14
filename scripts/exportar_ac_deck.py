#!/usr/bin/env python3
"""Exporta fontes públicas revisadas, sem histórico Git ou payloads privados.

Simula por padrão. --apply exige a revisão base; o manifesto registra os hashes
do checkout efetivamente copiado, sem alegar que ele coincide com esse commit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_launcher_linux as builder
from src.launcher import file_io


MANIFEST = 'public-source-manifest.json'
TEST_SOURCES = ('tests/__init__.py', 'tests/support/__init__.py',
                'tests/test_assists_config.py', 'tests/test_command_entrypoints.py',
                'tests/test_community_build.py', 'tests/test_community_download.py',
                'tests/test_community_install.py', 'tests/test_csp_community_install.py',
                'tests/test_file_io.py', 'tests/test_install_bootstrap.py',
                'tests/test_install_discovery.py', 'tests/test_practice_session.py',
                'tests/test_first_launch.py',
                'tests/test_community_cycle.py',
                'tests/test_community_update.py',
                'tests/test_preparar_fontes_dependencias.py',
                'tests/test_rogue_variety.py', 'tests/test_rogue_victory_music.py',
                'tests/test_steam_install_options.py',
                'tests/support/assists_fixtures.py',
                'tests/support/practice_session_fixtures.py')
SOURCE_ALIASES = {'tests/test_rogue_variety.py': 'tests/public_rogue_variety.py',
                  'tests/support/__init__.py': 'tests/public_support_init.py'}
EXTRA_SOURCES = ('scripts/launcher-linux-requirements.txt',
                 'scripts/ciclo_entrega.py', 'scripts/ciclo-entrega.json',
                 'scripts/ciclo_entrega_lib/__init__.py',
                 'scripts/ciclo_entrega_lib/common.py',
                 'scripts/ciclo_entrega_lib/build.py',
                 'scripts/ciclo_entrega_lib/publication.py',
                 'scripts/ciclo_entrega_lib/community.py',
                 'scripts/ciclo_entrega_lib/community_verify.py',
                 'scripts/ciclo_entrega_lib/community_probe.py',
                 'scripts/exportar_ac_deck.py',
                 'scripts/render_readme_screenshots.py',
                 'scripts/install_ac_deck.py',
                 'scripts/update_ac_deck.py',
                 'scripts/preparar_fontes_dependencias.py',
                 'scripts/preparar_sdk_linux_sem_bdb.sh',
                 'licenses/ACC-DualSense-Feedback.txt', *TEST_SOURCES)
COMMAND_SOURCES = frozenset(('scripts/jogo_deck.py', 'scripts/pratica_deck.py',
                            'scripts/build_launcher_linux.py', *EXTRA_SOURCES))


def public_path(value):
    name = file_io.relative_file(value)
    if name != value:
        raise file_io.SafetyError('Caminho público deve ser relativo e canônico')
    parts = Path(name).parts
    if not (name in COMMAND_SOURCES or
            (len(parts) == 3 and parts[:2] == ('src', 'launcher') and
             parts[-1].endswith('.py'))):
        raise file_io.SafetyError('Arquivo fora da seleção pública: '+name)
    return name


def selected_sources():
    names = tuple(builder.COMMUNITY_SOURCES)
    names += tuple(name for name in EXTRA_SOURCES if name not in names)
    selected = [public_path(name) for name in names]
    if not selected or len({name.casefold() for name in selected}) != len(selected):
        raise file_io.SafetyError('Seleção pública vazia, duplicada ou ambígua')
    return sorted(selected)


def fingerprint(path):
    digest, info = file_io.hash_reference_file(path)
    return dict(sha256=digest, size_bytes=info.st_size,
                mode=0o755 if info.st_mode & 0o111 else 0o644)


def previous_manifest(target):
    path = target/MANIFEST
    file_io.check_components(path)
    if not path.exists():
        return {}, None
    before = fingerprint(path)
    payload, digest = file_io.read_document(path)
    if digest != before['sha256'] or fingerprint(path) != before:
        raise file_io.SafetyError('Manifesto público mudou durante a leitura')
    if payload.get('schema_version') != 1 or not isinstance(payload.get('files'), list):
        raise file_io.SafetyError('Manifesto público anterior inválido')
    rows = {}
    for row in payload['files']:
        if not isinstance(row, dict):
            raise file_io.SafetyError('Entrada inválida no manifesto público')
        name = public_path(row.get('path'))
        if (name.casefold() in {key.casefold() for key in rows} or
                not isinstance(row.get('sha256'), str) or
                not re.fullmatch(r'[0-9a-f]{64}', row['sha256']) or
                type(row.get('size_bytes')) is not int or row['size_bytes'] < 0 or
                row.get('mode') not in (0o644, 0o755)):
            raise file_io.SafetyError('Entrada inválida no manifesto público: '+name)
        rows[name] = {key: row[key] for key in ('sha256', 'size_bytes', 'mode')}
    return rows, before


def check_destination(path):
    file_io.check_components(path)
    for parent in path.parents:
        if parent.exists() and not parent.is_dir():
            raise file_io.SafetyError('Destino tem ancestral que não é diretório: '+str(parent))


def reconciliation_history(target, manifest_before):
    path = target/MANIFEST
    if manifest_before is None and not path.exists():
        return []
    payload, digest = file_io.read_document(path)
    if (manifest_before is None or digest != manifest_before['sha256']
            or fingerprint(path) != manifest_before):
        raise file_io.SafetyError('Manifesto público mudou ao ler a proveniência')
    history = payload.get('reconciliation_history', [])
    latest = payload.get('reconciliation_sha256')
    if not isinstance(history, list) or any(not isinstance(value, str)
            or not re.fullmatch(r'[0-9a-f]{64}', value) for value in history):
        raise file_io.SafetyError('Histórico de reconciliação inválido')
    if latest is not None:
        if not isinstance(latest, str) or not re.fullmatch(r'[0-9a-f]{64}', latest):
            raise file_io.SafetyError('Referência de reconciliação inválida')
        if latest not in history:
            history.append(latest)
    return history


def reviewed_changes(path, target, manifest_before, current):
    """Bind an explicit review to this destination, manifest and source bytes."""
    if path is None:
        return {}, None
    before = fingerprint(path)
    payload, digest = file_io.read_document(path)
    if digest != before['sha256'] or fingerprint(path) != before:
        raise file_io.SafetyError('Plano de reconciliação mudou durante a leitura')
    if (payload.get('schema_version') != 1 or payload.get('target') != str(target)
            or payload.get('manifest_sha256') != (manifest_before or {}).get('sha256')
            or not isinstance(payload.get('files'), list)):
        raise file_io.SafetyError('Plano de reconciliação não corresponde ao destino/manifesto')
    rows = {}
    for row in payload['files']:
        if not isinstance(row, dict):
            raise file_io.SafetyError('Entrada inválida no plano de reconciliação')
        name = public_path(row.get('path'))
        if (name in rows or name not in current or row.get('after') != current[name]
                or not isinstance(row.get('before'), dict)):
            raise file_io.SafetyError('Plano de reconciliação diverge das fontes: '+name)
        rows[name] = row['before']
    return rows, before


def export(target, *, source_root=ROOT, source_commit=None, apply=False, reconciliation=None):
    if source_commit is not None and not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', source_commit):
        raise ValueError('Revisão base deve ser um hash Git completo')
    if apply and source_commit is None:
        raise ValueError('--apply exige --source-commit')
    source = file_io.source_root(source_root)
    target = file_io.absolute(target)
    check_destination(target)
    if target.exists() and not target.is_dir():
        raise file_io.SafetyError('Destino deve ser um diretório')
    if source == target or file_io.inside(source, target) or file_io.inside(target, source):
        raise file_io.SafetyError('Origem e destino devem ser diretórios separados')
    names = selected_sources()
    current = {name: fingerprint(source/SOURCE_ALIASES.get(name, name)) for name in names}
    previous, manifest_before = previous_manifest(target)
    history = reconciliation_history(target, manifest_before)
    reviewed, review_before = reviewed_changes(reconciliation, target, manifest_before, current)
    observed = {}
    reconciled = []
    actions = dict(create=[], update=[], remove=[], unchanged=[])
    for name in sorted(set(current) | set(previous)):
        path = target/name
        check_destination(path)
        actual = fingerprint(path) if path.exists() else None
        observed[name] = actual
        identical = actual is not None and actual == current.get(name)
        approved = name in reviewed and actual == reviewed[name]
        if name in reviewed and not (approved or identical):
            raise file_io.SafetyError('Destino diverge do plano de reconciliação: '+name)
        if actual is not None and name not in previous and not (identical or approved):
            raise file_io.SafetyError('Colisão com arquivo público não gerenciado: '+name)
        if (actual is not None and actual != previous.get(name)
                and not (identical or approved)):
            raise file_io.SafetyError('Arquivo público modificado; preservado: '+name)
        if actual is not None and actual != previous.get(name):
            reconciled.append(name)
        if name not in current:
            if actual is not None:
                actions['remove'].append(name)
        elif actual is None:
            actions['create'].append(name)
        elif actual != current[name]:
            actions['update'].append(name)
        else:
            actions['unchanged'].append(name)
    if review_before is not None and review_before['sha256'] not in history:
        history.append(review_before['sha256'])
    report = dict(applied=False, source_commit=source_commit, actions=actions,
                  manifest=MANIFEST, files=len(current), reconciled=reconciled,
                  reconciliation_sha256=history[-1] if history else None,
                  reconciliation_history=history)
    if not apply:
        return report

    # Stage independent copies first. Publish the success manifest only after
    # every source and destination has passed the second hash comparison.
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ac-deck-export-', dir=target.parent) as temporary:
        stage = Path(temporary)
        for name in actions['create'] + actions['update']:
            file_io.copy_verified(source/SOURCE_ALIASES.get(name, name), stage/name, current[name]['sha256'])
            (stage/name).chmod(current[name]['mode'])
        for name, expected in current.items():
            if fingerprint(source/SOURCE_ALIASES.get(name, name)) != expected:
                raise file_io.SafetyError('Fonte mudou durante a exportação: '+name)
        for name, expected in observed.items():
            path = target/name
            check_destination(path)
            actual = fingerprint(path) if path.exists() else None
            if actual != expected:
                raise file_io.SafetyError('Destino mudou durante a exportação: '+name)
        manifest_path = target/MANIFEST
        file_io.check_components(manifest_path)
        actual_manifest = fingerprint(manifest_path) if manifest_path.exists() else None
        if actual_manifest != manifest_before:
            raise file_io.SafetyError('Manifesto público mudou durante a exportação')
        if reconciliation is not None and fingerprint(reconciliation) != review_before:
            raise file_io.SafetyError('Plano de reconciliação mudou durante a exportação')
        payload = dict(schema_version=1, source_commit=source_commit,
                       source_tree='working-tree',
                       scope='Reviewed source files only; no Git history or private payloads',
                       first_party_license='not managed by export; see destination LICENSE',
                       reconciliation_sha256=report['reconciliation_sha256'],
                       reconciliation_history=history,
                       files=[dict(path=name, source_path=SOURCE_ALIASES.get(name, name),
                                   **current[name]) for name in names])
        file_io.write_json(stage/MANIFEST, payload)
        target.mkdir(parents=True, exist_ok=True)
        for name in actions['create'] + actions['update']:
            path = target/name
            check_destination(path)
            actual = fingerprint(path) if path.exists() else None
            if actual != observed[name]:
                raise file_io.SafetyError('Destino mudou antes da publicação: '+name)
            path.parent.mkdir(parents=True, exist_ok=True)
            (stage/name).replace(path)
        for name in actions['remove']:
            path = target/name
            if fingerprint(path) != observed[name]:
                raise file_io.SafetyError('Arquivo antigo mudou; preservado: '+name)
            path.unlink()
        for name, expected in current.items():
            if fingerprint(target/name) != expected:
                raise file_io.SafetyError('Cópia pública diverge: '+name)
            if fingerprint(source/SOURCE_ALIASES.get(name, name)) != expected:
                raise file_io.SafetyError('Fonte mudou antes do manifesto final: '+name)
        if reconciliation is not None and fingerprint(reconciliation) != review_before:
            raise file_io.SafetyError('Plano de reconciliação mudou antes do manifesto final')
        if (fingerprint(manifest_path) if manifest_path.exists() else None) != manifest_before:
            raise file_io.SafetyError('Manifesto público mudou antes da publicação')
        (stage/MANIFEST).replace(manifest_path)
    report['applied'] = True
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--source-commit', help='Revisão base; hashes do checkout ficam no manifesto')
    parser.add_argument('--apply', action='store_true', help='Aplicar a seleção; padrão é somente simular')
    parser.add_argument('--reconciliation', type=Path,
                        help='Plano revisado com hashes exatos de fonte, destino e manifesto anterior')
    args = parser.parse_args(argv)
    try:
        result = export(args.target, source_commit=args.source_commit, apply=args.apply,
                        reconciliation=args.reconciliation)
    except (OSError, ValueError, file_io.SafetyError) as error:
        parser.exit(1, str(error)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
