"""Aproveita campos válidos, resolve dependências e completa sem novo sorteio."""
from . import conditions, event_synthetizer as events


def compose(game, result, catalog, base, *, fixed=None, previous=None, current=None, bounds, context_catalog=None):
    if not isinstance(result, dict):
        raise ValueError('No readable AI event.')
    groups, tracks = events.candidates(catalog, base, fixed)
    fixed = events.pins(fixed)
    cars = {row['id']: row for row in catalog['cars']
            if any(row['id'] in group['cars'] for group in groups)}
    track_map = {row['key']: row for row in tracks}
    group_map = {row['id']: row for row in groups}
    weather = catalog['synthesis_weather']
    previous_selection = {}
    if previous is not None:
        try:
            events.validate(game, previous, catalog=context_catalog if context_catalog is not None else catalog)
            previous_selection = previous['selection']
        except (ValueError, KeyError, TypeError):
            pass
    current = base if current is None else current
    origins, adjustments = {}, []
    useful = set()

    def supplied(key, options):
        value = result.get(key)
        if isinstance(value, str) and value in options:
            useful.add(key)
            origins[key] = 'ai'
            return value
        return None

    def fallback(key, options, read, pinned=None):
        if pinned is not None:
            origins[key] = 'pin'
            return pinned
        for source, selected in (('current', current), ('previous', previous_selection)):
            value = read(selected)
            if isinstance(value, (str, int)) and type(value) is not bool and value in options:
                origins[key] = source
                return value
        origins[key] = 'local'
        return sorted(options)[0]

    def adjusted(key):
        if origins[key] != 'ai':
            adjustments.append(key)

    car_id = supplied('car_id', cars)
    class_id = supplied('class_id', group_map)
    if fixed['car'] is not None and car_id != fixed['car']:
        useful.discard('car_id')
        car_id = fallback('car_id', cars, lambda row: row.get('car'), fixed['car'])
    if car_id is None:
        options = group_map[class_id]['cars'] if class_id is not None else cars
        car_id = fallback('car_id', options, lambda row: row.get('car'))
    if class_id is None or car_id not in group_map[class_id]['cars']:
        useful.discard('class_id')
        compatible = [g['id'] for g in groups if car_id in g['cars']]
        previous_class = previous.get('class_id') if previous_selection else None
        class_id = previous_class if previous_class in compatible else sorted(compatible)[0]
        origins['class_id'] = 'catalog'
    adjusted('car_id')
    adjusted('class_id')

    track_key = supplied('track_key', track_map)
    pinned_track = next((t['key'] for t in tracks if [t['id'], t['layout']] == fixed['track']), None)
    if pinned_track is not None and track_key != pinned_track:
        useful.discard('track_key')
        track_key = fallback('track_key', track_map, lambda _: None, pinned_track)
    if track_key is None:
        track_key = fallback('track_key', track_map,
                             lambda row: str(row.get('track', ''))+'|'+str(row.get('layout', '')))
    adjusted('track_key')

    chosen_weather = supplied('weather', weather)
    if chosen_weather is None:
        chosen_weather = fallback('weather', weather, lambda row: row.get('weather'))
    adjusted('weather')
    allowed_minutes = range(conditions.MINUTES_MIN, conditions.MINUTES_MAX+1)
    # Horário pertence à interface. Nunca aproveitar uma sugestão da resposta,
    # nem contar esse campo como conteúdo útil ou correção da escolha da IA.
    minutes = fallback('time_minutes', allowed_minutes, lambda row: row.get('time_minutes'))

    level = result.get('ai_level')
    if type(level) is int and bounds['minimum'] <= level <= bounds['maximum']:
        origins['ai_level'] = 'ai'
        if bounds['minimum'] != bounds['maximum']:
            useful.add('ai_level')
    else:
        level = base['ai']
        origins['ai_level'] = 'current'
    adjusted('ai_level')
    if not useful:
        raise ValueError('No usable AI fields. Previous event kept.')
    # Extras são ignorados, nunca copiados para a seleção ou para o histórico.
    if any(key not in ('class_id', 'car_id', 'track_key', 'weather',
                       'ai_level', 'rationale', 'references', 'preference_status') for key in result):
        adjustments.append('extra_fields')
    return dict(car=cars[car_id], group=group_map[class_id], track=track_map[track_key],
                weather=chosen_weather, time_minutes=minutes, ai_level=level,
                field_sources=origins, adjustments=adjustments)


def explanation(result, catalog, *, allow_unreferenced=False):
    """Só exibe justificativa limitada com referências existentes na ficha enviada."""
    references = result.get('references', [])
    rationale = result.get('rationale', '')
    if not isinstance(rationale, str) or len(rationale) > (220 if allow_unreferenced else 600) or not isinstance(references, list):
        return '', []
    valid = []
    for item in references[:12]:
        if not isinstance(item, dict) or item.get('kind') not in ('car', 'track'):
            return '', []
        rows = catalog['cars' if item['kind'] == 'car' else 'tracks']
        key = 'id' if item['kind'] == 'car' else 'key'
        row = next((row for row in rows if row[key] == item.get('id')), None)
        field = item.get('field')
        if (row is None or not isinstance(field,str)
                or field not in row.get('semantic', {}) and field not in row):
            return '', []
        valid.append({k: item[k] for k in ('kind', 'id', 'field')})
    # Sem fonte válida, não apresentar uma alegação histórica como sustentada.
    return (' '.join(rationale.split()), valid) if valid or allow_unreferenced else ('', [])
