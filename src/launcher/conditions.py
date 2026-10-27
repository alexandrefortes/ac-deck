"""Hora nativa e calendário civil do Weather FX, sem depender do fuso do PC."""
from datetime import date, datetime, time
import math

MINUTES_MIN, MINUTES_MAX = 8*60, 18*60

# Preset Optimum do Assetto Corsa/CM. A condicao nao e uma escolha do launcher ou da IA.
OPTIMUM_TRACK = dict(PRESET='5', SESSION_START='100', RANDOMNESS='0',
                     LAP_GAIN='1', SESSION_TRANSFER='100')


def apply_track(race):
    """Fixa a aderencia inicial em 100%, sem aleatoriedade ou perda entre sessoes."""
    if 'DYNAMIC_TRACK' not in race:
        race.add_section('DYNAMIC_TRACK')
    race['DYNAMIC_TRACK'].update(OPTIMUM_TRACK)


def validate(selection):
    value = selection.get('time_minutes')
    if value is not None and (type(value) is not int or not MINUTES_MIN <= value <= MINUTES_MAX):
        raise ValueError('Time of day must be between 08:00 and 18:00')
    if 'session_date' in selection:
        value = selection['session_date']
        if not isinstance(value, str):
            raise ValueError('Session date must use YYYY-MM-DD')
        date.fromisoformat(value)


def apply(race, selection, *, csp=False, today=None):
    """Preserva condições do evento, salvo escolha explícita de horário.

    __CM_DATE usa segundos de calendário, sem conversão UTC. O consumidor de
    __CM_DATE_USE_TIME é fechado: sua aceitação será conferida no log do Deck.
    """
    validate(selection)
    if 'LIGHTING' not in race:
        race.add_section('LIGHTING')
    lighting = race['LIGHTING']
    minutes = selection.get('time_minutes')
    if minutes is not None:
        # Contrato nativo CM: 08:00=-80, 13:00=0, 18:00=80 graus.
        lighting['SUN_ANGLE'] = format((minutes-13*60)/3.75, '.8g')
    if not csp:
        return
    if minutes is None and lighting.get('__CM_DATE'):
        return  # Evento já contém data/hora própria; conservar sua configuração.
    if minutes is None:
        angle = float(lighting.get('SUN_ANGLE', '-48'))
        if not math.isfinite(angle):
            raise ValueError('Invalid native sun angle')
        minutes = round(13*60+angle*3.75)
        if not MINUTES_MIN <= minutes <= MINUTES_MAX:
            raise ValueError('Native sun angle is outside the supported daytime range')
    chosen = date.fromisoformat(selection['session_date']) if 'session_date' in selection else (today or date.today())
    wall_clock = datetime.combine(chosen, time(minutes//60, minutes%60))
    lighting['__CM_DATE'] = str(int((wall_clock-datetime(1970,1,1)).total_seconds()))
    lighting['__CM_DATE_USE_TIME'] = '1'
