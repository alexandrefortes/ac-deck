"""Ficha semântica do catálogo comum, sem limites de apresentação da UI.

Somente campos pertinentes declarados pelo conteúdo. Ausência não vira fato;
URLs, versão técnica, arquivos brutos e caminhos do aparelho não entram aqui.
"""
from html.parser import HTMLParser
import math
import re

AI_FIELDS = {
    'car': frozenset(('class', 'year', 'parent', 'tags', 'description', 'drivetrain',
                      'specs.bhp', 'specs.topspeed', 'specs.acceleration')),
    'track': frozenset(('city', 'year', 'length', 'width', 'run', 'tags', 'description'))}


def for_ai(values, *, kind):
    """Projeta o template aprovado sem alterar a ficha local ou caches antigos."""
    def clean(value):
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()
                    if key not in ('source', 'quality', 'origin_source', 'provenance')
                    and not (key in ('unit', 'normalized') and item is None)}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    result={key:clean(value) for key,value in values.items()
            if key in AI_FIELDS[kind]}
    if 'specs.bhp' in result:
        power=result['specs.bhp']
        if isinstance(power,dict) and 'value' not in power:
            del result['specs.bhp']
        else:
            result['specs.bhp']=dict(value=power['value'] if isinstance(power,dict) else power)
    return result


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif not self.hidden:
            if tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'tr'):
                self.parts.append('\n' + ('• ' if tag == 'li' else ''))

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden-1)
        elif not self.hidden and tag in ('p', 'div', 'li', 'tr'):
            self.parts.append('\n')

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def text(value):
    parser = _Text()
    parser.feed(value)
    return '\n'.join(re.sub(r'[^\S\n]+', ' ', line).strip()
                     for line in ''.join(parser.parts).splitlines() if line.strip())


def declared(value):
    """Conserva valores, séries e campos ausentes sem inventar unidades."""
    if isinstance(value, str):
        return text(value)
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    if isinstance(value, list):
        return [declared(item) for item in value]
    if isinstance(value, dict):
        return {key: declared(item) for key, item in value.items() if isinstance(key, str)}
    return None


def fact(value, source, quality='declared'):
    return dict(value=declared(value), source=source, quality=quality)


def measurement(value, source, kind):
    if kind=='bhp':
        return dict(value=declared(value))
    result=fact(value,source)
    result.update(unit=None,normalized=None)
    match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(km/h|kmh|mph)\s*',
                       str(value),re.I)
    if not match:return result
    amount=float(match[1]);unit=match[2].casefold()
    allowed={
        'topspeed': {'km/h':(1,'km/h'),'kmh':(1,'km/h'),'mph':(1.609344,'km/h')}}
    conversion=allowed.get(kind,{}).get(unit)
    if conversion:
        result['unit']=match[2]
        result['normalized']=dict(value=round(amount*conversion[0],6),unit=conversion[1],
                                  quality='derived_unit_conversion')
    return result


def common(info, kind):
    fields = ('name', 'brand', 'class', 'country', 'year', 'parent', 'tags',
              'description') if kind == 'car' else (
                  'name', 'country', 'city', 'year', 'length',
                  'width', 'run', 'tags', 'description')
    filename = 'ui_car.json' if kind == 'car' else 'ui_track.json'
    result = {key: fact(info[key], filename+':'+key) for key in fields
              if key in info and info[key] not in (None, '', [])}
    if kind == 'car':
        specs = info.get('specs')
        if isinstance(specs, dict):
            for key in ('bhp', 'topspeed', 'acceleration'):
                if key in specs and specs[key] not in (None, ''):
                    # Valor original e unidade, quando declarada, permanecem juntos.
                    result['specs.'+key] = measurement(specs[key], filename+':specs.'+key,key)
        for key in ('drivetrain',):
            if key in info and info[key] not in (None, '', []):
                result[key] = fact(info[key], filename+':'+key)
    return result


def car(info):
    return common(info, 'car')


def track(info):
    return common(info, 'track')
