"""Duração aproximada para novos desafios, usando só resultados locais existentes."""
from collections import Counter
from pathlib import Path
import math
import re
from statistics import median, quantiles

from . import history_records


LONG_TRACK_KM = 8.0
MIN_LAPS = 3
TARGET_SECONDS = 270
SOFT_MAX_SECONDS = 480


def length_km(track):
    semantic = track.get('semantic')
    fact = semantic.get('length') if isinstance(semantic, dict) else None
    value = fact.get('value') if isinstance(fact, dict) else None
    match = re.fullmatch(r'\s*([0-9]+(?:[.,][0-9]+)?)\s*(km|m)\s*', value, re.I) if isinstance(value, str) else None
    if not match:
        return None
    amount, unit = match[1], match[2].lower()
    if unit == 'm' and re.search(r'[.,][0-9]{3}$', amount):
        return None
    length = float(amount.replace(',', '.')) / (1000 if unit == 'm' else 1)
    return length if math.isfinite(length) and length > 0 else None


def distance_laps(track):
    length = length_km(track)
    if length is None or length >= LONG_TRACK_KM:
        return 1
    return 3 if length <= 4 else max(1, math.floor(12 / length))


def load(synthesis_store):
    """Lê até 50 tentativas; nada novo é coletado ou gravado em disco."""
    if synthesis_store is None:
        return {}
    synthesis_store = Path(synthesis_store)
    samples, seen_sources = {}, set()
    for row in history_records.load(synthesis_store, limit=50):
        if row['status'] != 'imported' or row['completion'] != 'confirmed':
            continue
        try:
            path = synthesis_store.parent/'sessions'/row['id']/'result.json'
            record, _ = history_records.read_record(path)
            checked = history_records.validate_result(record, row['id'], row['selection'])
            if checked['status'] != 'imported' or checked['completion'] != 'confirmed':
                continue
            result = record['result']
            key = (result['car'], result['track'], result['layout'])
            if key[2] and result.get('layout_evidence') != 'track_layout_reported_by_result':
                continue  # Um layout somente configurado não prova qual variante foi cronometrada.
            source = record.get('source')
            digest = source.get('sha256') if isinstance(source, dict) else None
            if isinstance(digest, str):
                if digest in seen_sources:
                    continue
                seen_sources.add(digest)
            times = []
            for session in result['sessions']:
                if (session.get('type') != 3 or session.get('race_completed') is not True
                        or session.get('completion_evidence') != 'player_lap_target_reached'):
                    continue
                laps = session.get('recorded_laps')
                if not isinstance(laps, list):
                    continue
                indices = Counter(lap.get('lap') for lap in laps if isinstance(lap, dict) and type(lap.get('lap')) is int)
                for lap in laps:
                    if not isinstance(lap, dict):
                        continue
                    index, duration = lap.get('lap'), lap.get('time_ms')
                    if (type(index) is int and index >= 0 and indices[index] == 1
                            and type(duration) is int and 1000 <= duration <= 3600000
                            and type(lap.get('cuts')) is int and lap['cuts'] == 0):
                        times.append(duration)
            if times:
                samples.setdefault(key, []).append((median(times), len(times)))
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, AttributeError):
            continue
    models = {}
    for key, sessions in samples.items():
        count = sum(count for _, count in sessions)
        if count < MIN_LAPS:
            continue
        values = [value for value, _ in sessions]
        typical = median(values)
        low, _, high = quantiles(values, n=4, method='inclusive') if len(values) > 1 else (typical, typical, typical)
        models[key] = dict(median_ms=round(typical), low_ms=round(min(low*.95, typical*.9)),
                           high_ms=round(max(high*1.1, typical*1.25)),
                           sample_laps=count, sample_sessions=len(sessions))
    return models


def choose(track, car_id, models):
    """A meta de 3–6 min orienta voltas; oito minutos é referência, sem eliminação."""
    key = (car_id, track['id'], track.get('layout', ''))
    model = (models or {}).get(key)
    if not model:
        return distance_laps(track), dict(version=1, source='distance_only')
    length = length_km(track)
    cap = 3 if length is not None and length < LONG_TRACK_KM else 2
    choices = []
    for laps in range(1, cap+1):
        low = math.floor(model['low_ms']*laps/1000+10)
        high = math.ceil(model['high_ms']*laps/1000+20)
        expected = model['median_ms']*laps/1000*1.15+15
        choices.append((laps, low, high, expected))
    eligible = [choice for choice in choices if choice[2] <= SOFT_MAX_SECONDS] or choices[:1]
    laps, low, high, _ = min(eligible, key=lambda choice: abs(choice[3]-TARGET_SECONDS))
    return laps, dict(version=1, source='recorded_laps', low_seconds=low, high_seconds=high,
                      sample_laps=model['sample_laps'], sample_sessions=model['sample_sessions'])


def label(duration):
    if (not isinstance(duration, dict) or duration.get('version') != 1
            or duration.get('source') != 'recorded_laps'):
        return 'Duration: not enough timed laps for this car/circuit.'
    low, high = duration.get('low_seconds'), duration.get('high_seconds')
    if type(low) is not int or type(high) is not int or not 1 <= low <= high <= 11000:
        return 'Duration: estimate unavailable.'
    minimum, maximum = max(1, low//60), math.ceil(high/60)
    return f'Approx. {minimum}–{maximum} min / based on recorded laps'
