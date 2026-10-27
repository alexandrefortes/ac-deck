"""Somente nomes e configurações sintéticos. Não são defaults oficiais."""
from src.launcher.practice_session import Car, Track, Catalog, PracticeRequest


CATALOG = Catalog((Car('fixture_car', ('fixture_skin', 'other_skin')),),
                  (Track('fixture_track', ('', 'fixture_layout')),),
                  ('fixture_clear',), 'synthetic', ('own-fixture-practice-01',))
REQUEST = PracticeRequest('fixture_car', 'fixture_skin', 'fixture_track', '',
                          'Piloto de teste', 'Synthetic', 'TST', 0, (1280, 800))


def template(**overrides):
    values = {
        'TEMPERATURE': {'ROAD': '25', 'AMBIENT': '20'},
        'LIGHTING': {'SUN_ANGLE': '0.25', 'TIME_MULT': '1.0', 'CLOUD_SPEED': '0.125'},
        'WEATHER': {'NAME': 'fixture_clear'},
        'WIND': {'SPEED_KMH_MIN': '0', 'SPEED_KMH_MAX': '2.5', 'DIRECTION_DEG': '90'},
        'DYNAMIC_TRACK': {'SESSION_START': '97.5', 'RANDOMNESS': '0', 'LAP_GAIN': '1', 'SESSION_TRANSFER': '100'},
        'RACE': {'AI_LEVEL': '87'},
    }
    values.update(overrides)
    return tuple((name, tuple(section.items())) for name, section in values.items())
