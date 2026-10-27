"""Mapa somente de leitura das fontes de histórico; não importa dados pessoais."""
from pathlib import Path
from . import file_io as safe


def sources(cfg, package):
    root = safe.absolute(cfg).parent
    package = safe.source_root(package)
    definitions = (
        ('last_result', root/'out/race_out.json', 'verified_format',
         'Resultado mais recente; pode ser substituído. Não é arquivo cumulativo.'),
        ('career_progress', root/'launcherdata/filestore/career.ini', 'verified_path',
         'Progressão do launcher original; abrir acs.exe diretamente não garante atualização.'),
        ('personal_best', root/'personalbest.ini', 'candidate_path',
         'Recordes candidatos; confirmar presença/formato no aparelho antes de importar.'),
        ('launcher_sessions', package/'launcher/sessions', 'implemented',
         'Nosso histórico persistente: seleção, proposta gerada, INIs e runtime.log.'),
        ('generated_event', package/'launcher/event-synthetizer.json', 'implemented',
         'Proposta atual e base fixa separadas das escolhas manuais.'),
        ('session_results', package/'launcher/sessions', 'implemented',
         'Cada nova sessão tem result.json; resultado novo preservado em result-source.json local, sem envio à IA.'),
    )
    rows = []
    for key, path, evidence, note in definitions:
        try:
            safe.check_components(path)
            exists, error = path.exists(), None
        except (ValueError, safe.SafetyError):
            exists, error = None, 'unsafe_path_not_read'
        rows.append(dict(id=key, path=str(path), exists=exists, evidence=evidence, note=note, error=error))
    return dict(schema_version=1, documents_root=str(root), sources=rows,
                read_only=True, native_results_imported=False, per_session_result_collection=True,
                correlation='Não associar race_out antigo à sessão por exit code. Validar frescor, pista/carro e campos antes de importar.')
