"""Gerador puro de assists.ini, recuperado do CIL de AcTools.

Todos os valores são explícitos. Não seleciona defaults de física ou de usuário.
Não consulta arquivos, ambiente, processos ou serviços. Este contrato puro é
reutilizado pelo launcher Python; as evidências de origem mantêm seu escopo
estático e não comprovam equivalência de execução com o simulador.

Contrato observado: bool -> 0/1; StabilityControl -> Int32; ABS/TC -> valores
de AssistState boxed como Int32; multiplicadores -> Double invariável. O escritor
não aplica clamp. A faixa aceita pelo simulador permanece não comprovada.

Políticas próprias: enum fechado; somente números finitos, escritos como strings
ASCII de até 128 caracteres; zero canônico; decimal sem expoente e LF. O decimal
mantém o valor decimal solicitado, após verificar conversão Double finita e sem
underflow a zero. Não reproduz o arredondamento Double.ToString do CLR.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import IntEnum
import math
import re


SOURCE_METHODS = ('0x06000cd0', '0x06000cd1', '0x0600086d',
                  '0x06000872', '0x06000873', '0x06000877')
SOURCE_ARTIFACT_SHA256 = '2e82bc3e697556d28f595c73a30e7bfe39259ea43239223c0e60996412be2dee'
CONTRACT_EVIDENCE_REFS = (
    'local-assists-cil-4c59121d4e56d00ff2fd',
    'local-assists-cil-dfb849c21f3514abb4f3',
    'local-assists-cil-a5bbd7db3146f513e4e3',
    'local-assists-cil-1f71594f57a27af27349',
    'local-assists-cil-f86970c33008b0826ef8',
)
_NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
_SCHEMA = (
    ('ideal_line', 'IDEAL_LINE', 'bool'),
    ('auto_blip', 'AUTO_BLIP', 'bool'),
    ('stability_control', 'STABILITY_CONTROL', 'int32'),
    ('auto_brake', 'AUTO_BRAKE', 'bool'),
    ('auto_shifter', 'AUTO_SHIFTER', 'bool'),
    ('abs_state', 'ABS', 'state'),
    ('traction_control', 'TRACTION_CONTROL', 'state'),
    ('auto_clutch', 'AUTO_CLUTCH', 'bool'),
    ('visual_damage', 'VISUALDAMAGE', 'bool'),
    ('damage', 'DAMAGE', 'double_text'),
    ('fuel_consumption', 'FUEL_RATE', 'double_text'),
    ('tyre_wear_multiplier', 'TYRE_WEAR', 'double_text'),
    ('tyre_blankets', 'TYRE_BLANKETS', 'bool'),
    ('slipstream_multiplier', 'SLIPSTREAM', 'double_text'),
)


class AssistState(IntEnum):
    """Valores declarados no enum AcTools.Processes.AssistState."""

    OFF = 0
    FACTORY = 1
    ON = 2


@dataclass(frozen=True, kw_only=True)
class AssistsSettings:
    ideal_line: bool
    auto_blip: bool
    stability_control: int
    auto_brake: bool
    auto_shifter: bool
    abs_state: AssistState
    traction_control: AssistState
    auto_clutch: bool
    visual_damage: bool
    damage: str
    fuel_consumption: str
    tyre_wear_multiplier: str
    tyre_blankets: bool
    slipstream_multiplier: str


def double_text(value, label):
    """Serializa um número decimal explícito sob o contrato Double investigado."""
    if type(value) is not str or len(value) > 128 or not _NUMBER.fullmatch(value):
        raise ValueError('Número ASCII invariável explícito necessário: ' + label)
    try:
        number = Decimal(value)
        native = float(number)
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise ValueError('Número inválido: ' + label) from error
    if not number.is_finite() or not math.isfinite(native) or (number != 0 and native == 0):
        raise ValueError('Número fora da representação Double finita: ' + label)
    # Evita expandir zero com expoente arbitrário. Nenhum contexto Decimal de
    # arredondamento ou cultura global participa da formatação abaixo.
    if number == 0:
        return '0'
    text = format(number, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def build_assists_ini(settings):
    """Retorna as 14 chaves em uma seção. Não grava nem autoriza execução.

    Não limita StabilityControl a 0..100 nem multiplicadores a valores positivos:
    essas faixas não foram demonstradas pelo escritor. Aceitar um número aqui
    não demonstra que o simulador o aceita ou preserva sua física.
    """
    if type(settings) is not AssistsSettings:
        raise ValueError('Assistências completas e explícitas necessárias')
    lines = ['[ASSISTS]']
    for attribute, key, kind in _SCHEMA:
        value = getattr(settings, attribute)
        if kind == 'bool':
            if type(value) is not bool:
                raise ValueError('Booleano explícito necessário: ' + key)
            text = '1' if value else '0'
        elif kind == 'int32':
            if type(value) is not int or not -(2**31) <= value < 2**31:
                raise ValueError('Int32 explícito necessário: ' + key)
            text = str(value)
        elif kind == 'state':
            # O CLR pode representar enums indefinidos; nosso protótipo exige
            # membro declarado. Não é evidência de validação no simulador.
            if type(value) is not AssistState:
                raise ValueError('AssistState declarado necessário: ' + key)
            text = str(int(value))
        else:
            text = double_text(value, key)
        lines.append(key + '=' + text)
    return '\n'.join(lines) + '\n'
