"""Contrato da corrida, separado das preferências atuais do aparelho."""
from copy import deepcopy


# Lista positiva: uma preferência nova não muda a identidade de corridas salvas.
# Controles, assistências e comportamento da IA são preferências atuais do
# piloto em todos os modos, assim como vídeo, câmera, interface e hápticos.
RACE_FIELDS = (
    'car', 'skin', 'track', 'layout', 'event', 'mode', 'laps', 'minutes',
    'opponents', 'ai', 'weather', 'time_minutes', 'session_date',
)


def race(selection):
    """Extrai conteúdo e regras da corrida, sem preferências do piloto."""
    return {key: deepcopy(selection[key]) for key in RACE_FIELDS if key in selection}


def same(left, right):
    return race(left) == race(right)


def restore(recorded, current):
    """Restaura a corrida e conserva as preferências atuais, sem alterar entradas."""
    preferences = {key: deepcopy(value) for key, value in current.items()
                   if key not in RACE_FIELDS}
    for key in ('event_mode_name', 'event_time_label'):
        preferences.pop(key, None)
        if recorded.get('event') and key in recorded:
            preferences[key] = deepcopy(recorded[key])
    return dict(preferences, **race(recorded))
