"""Catálogo Rogue e metas cosméticas puras, separados das vidas da run.

Somente os três marcos secretos herdados concedem vidas no núcleo Rogue. As
figurinhas abaixo apenas leem XP já validado; não gastam XP, não alteram metas,
não inferem resultado esportivo e não dependem da telemetria de observação.
"""
from copy import deepcopy
import hashlib
import os

from . import file_io as safe


MAX_XP = 2**53 - 1
_BADGES = (
    ('smooth_operator', 3, 'Smooth Operator', 'Three challenges. One clean streak.'),
    ('philosopher_on_wheels', 5, 'Philosopher on Wheels', 'Think less. Find the apex.'),
    ('thus_spoke_the_apex', 8, 'Thus Spoke the Apex', 'Eight challenges without a defeat.'),
)
_MASTERY = ((0, 'Rookie'), (100, 'Seat Time'), (300, 'Apprentice'),
            (700, 'Regular'), (1500, 'Specialist'), (3000, 'Master'), (6000, 'Legend'))

_QUOTES = {
    'kant': dict(
        text='Act only on that maxim whereby thou canst at the same time will that it should become a universal law.',
        author='Immanuel Kant', work='Fundamental Principles of the Metaphysic of Morals',
        location='Section II', translator='Thomas Kingsmill Abbott',
        source_url='https://raw.githubusercontent.com/GITenberg/Fundamental-Principles-of-the-Metaphysic-of-Morals_5682/289f5d5a80d14cc005c04c681939c9f571c26878/5682.txt'),
    'marcus': dict(
        text='Such as thy thoughts and ordinary cogitations are, such will thy mind be in time.',
        author='Marcus Aurelius', work='Meditations',
        location='Fifth Book, XV in the Casaubon edition', translator='Meric Casaubon',
        source_url='https://raw.githubusercontent.com/GITenberg/Meditations_2680/f586bf5b5ac4ace02faf101904ad43d11170fdeb/2680.txt'),
    'nietzsche': dict(
        text='one must still have chaos in one, to give birth to a dancing star.',
        author='Friedrich Nietzsche', work='Thus Spake Zarathustra',
        location="Zarathustra's Prologue, section 5", translator='Thomas Common',
        source_url='https://raw.githubusercontent.com/GITenberg/Thus-Spake-Zarathustra--A-Book-for-All-and-None_1998/6863f27d4402774557bfd383a6a3cb3fdd956399/1998.txt'),
}

# IDs de progresso não dependem do nome do arquivo ou da opção visual do álbum.
# ``metric`` e ``threshold`` são públicos: apenas os brasões acima são secretos.
_STICKERS = (
    dict(id='pocket_rocket', name='Pocket Rocket',
         description='First bond with a car. Small sticker, big garage energy.',
         requirement='Reach 100 XP with any car.', metric='car_max', threshold=100,
         asset_relpath='meme-doge.jpg', frame='racing', quote_id=None),
    dict(id='slow_is_smooth', name='Slow Is Smooth',
         description='Build a rhythm. Let the panic take the bus.',
         requirement='Accumulate 300 XP across your cars.', metric='car_total', threshold=300,
         asset_relpath='meme-spongebob.jpg', frame='racing', quote_id=None),
    dict(id='stoic_steering', name='Stoic Steering',
         description='The result can surprise you. The next corner still deserves your attention.',
         requirement='Reach 300 XP on any track/layout.', metric='track_max', threshold=300,
         asset_relpath='meme-harold.jpg', frame='philosophy', quote_id='marcus'),
    dict(id='this_is_fine_tuning', name='This Is Fine Tuning',
         description='Different races. Lasting progress. Even the cup looks calm.',
         requirement='Accumulate 500 XP across your cars.', metric='car_total', threshold=500,
         asset_relpath='meme-fine.png', frame='geek', quote_id=None),
    dict(id='muscle_memory', name='Muscle Memory',
         description='Three garages in your head. Somehow, the brake is still in the same place.',
         requirement='Reach 100 XP with each of 3 different cars.', metric='cars_100', threshold=3,
         asset_relpath='meme-panik-kalm-panik.png', frame='geek', quote_id='nietzsche'),
    dict(id='categorical_apex', name='Categorical Apex',
         description='A universal rule: give the next apex your full attention.',
         requirement='Reach 700 XP on any track/layout.', metric='track_max', threshold=700,
         asset_relpath='meme-astronaut.png', frame='philosophy', quote_id='kant'),
    dict(id='cross_training', name='Cross Training',
         description='Three cars, three habits, one wonderfully stubborn driver.',
         requirement='Reach 300 XP with each of 3 different cars.', metric='cars_300', threshold=3,
         asset_relpath='meme-both.jpg', frame='racing', quote_id=None),
    dict(id='smooth_is_fast', name='Smooth Is Fast',
         description='The same car. More stories. A place of honour in the album.',
         requirement='Reach 1500 XP with any car.', metric='car_max', threshold=1500,
         asset_relpath='meme-fry.png', frame='geek', quote_id=None),
)

# Seleção original e metadados da entrega privada, fixados por tamanho/hash.
EXPECTED_FILES = {
    'MEMEGEN-LICENSE.txt': (1053, 'ea3aa69bd02490bb2f4096907cb16a4f0ae38df8d960285e5a6f4e11bbe7f1e9'),
    'README.md': (987, '7cd64f61769b48a26c45661b2d5b6097a30e8b2a4d1e09aad9190aa6b3cb0719'),
    'asset-manifest.json': (2358, '5d904abd7a83fcbd24cfb378b427525c106ab7c33f854696b15bf988443d26ae'),
    'media-rights.json': (1002, '357c8db808066fe30d8c2af5045595372cccfb6c22f46e4038b6413e22e56981'),
    'meme-astronaut.png': (434315, 'db76c4071c012209655f7f0345b552800b62fcc7c7de5cd95876ecb148c81db5'),
    'meme-both.jpg': (18718, '9ddeadcea42a445290368410a90bd8e20dbf0fe4ab9c49bbcc43080a871bbeb0'),
    'meme-doge.jpg': (27264, '17168539cd19221ef3c506b37eb615bbc47c05bf6ac437c589f1abfef8976b98'),
    'meme-fine.png': (462256, 'afd90312ed4dabbe8223486d51438e26735a8f19cda0dd0bdd834cd2c481bb64'),
    'meme-fry.png': (161767, '2f4e0f4c2fd161a91c08513481ea2b88e9c4ce3ae678f296acd2882386d82426'),
    'meme-harold.jpg': (247278, '349045f2fc28d1450a122e2d797dd34c276a4dc06ef01e6388cd56b3d9b36da4'),
    'meme-panik-kalm-panik.png': (132867, 'f0fd69dfc9936cd1475d0cc8702554dccc217cc845899b2635579218e37acc73'),
    'meme-spongebob.jpg': (24868, '9a5a757b1fbd418caaf27478aba3a835548b251328ab03ce29d8bb557cce5362'),
    'origin.json': (9912, 'c7ca6fcb243c94e4e3aee3f61ae62aa784fc02b64eec046f586c7b51706a4459'),
    'quote-sources.json': (3407, 'efc08e3ea14afc8a521025347a6455233cd47608da2e7b9aaab0937867b71e8a'),
}
ALBUM_DISTRIBUTION_NAMES = tuple(EXPECTED_FILES)


def badge_definitions():
    """Autoridade dos três marcos originais; API interna, nunca payload da IA."""
    return _BADGES


def sticker_ids():
    return tuple(row['id'] for row in _STICKERS)


def _owned(value, known, *, list_only=False):
    if ((type(value) is not list) if list_only else type(value) not in (list, tuple)):
        raise ValueError('Invalid Rogue sticker album.')
    if (any(type(identity) is not str or identity not in known for identity in value)
            or len(set(value)) != len(value)):
        raise ValueError('Invalid Rogue sticker album.')
    return list(value)


def validate_sticker_ids(value):
    """Valida o campo persistente, rejeitando desconhecidos/duplicatas sem editar."""
    return _owned(value, sticker_ids(), list_only=True)


def _xp(value):
    if type(value) is not int or not 0 <= value <= MAX_XP:
        raise ValueError('Invalid Rogue XP.')
    return value


def _axis(profile, key):
    value = profile.get(key, {})
    if type(value) is not dict or any(type(identity) is not str or not identity for identity in value):
        raise ValueError('Invalid Rogue XP.')
    return [_xp(amount) for amount in value.values()]


def _metrics(profile):
    if type(profile) is not dict:
        raise ValueError('Invalid Rogue profile.')
    cars, tracks = _axis(profile, 'car_xp'), _axis(profile, 'track_xp')
    return dict(car_max=max(cars, default=0), track_max=max(tracks, default=0),
                car_total=sum(cars), cars_100=sum(xp >= 100 for xp in cars),
                cars_300=sum(xp >= 300 for xp in cars))


def mastery(xp):
    """Nível cosmético de um carro OU pista; nunca soma os dois eixos."""
    xp = _xp(xp)
    level = max(index for index, (threshold, _) in enumerate(_MASTERY) if xp >= threshold)
    next_xp = _MASTERY[level+1][0] if level+1 < len(_MASTERY) else None
    return dict(level=level, title=_MASTERY[level][1], xp=xp, next_xp=next_xp,
                remaining_xp=max(0, next_xp-xp) if next_xp is not None else 0)


def newly_unlocked(profile, owned=()):
    """Somente IDs cosméticos elegíveis e inéditos; não persiste nem muda a run."""
    acquired = _owned(owned, sticker_ids())
    metrics = _metrics(profile)
    return [row['id'] for row in _STICKERS
            if row['id'] not in acquired and metrics[row['metric']] >= row['threshold']]


def album_entries(profile, owned=(), badges=()):
    """Projeção UI: metas XP públicas, segredos sem identidade/arte/condição."""
    acquired = _owned(owned, sticker_ids())
    known_badges = _owned(badges, tuple(row[0] for row in _BADGES))
    metrics = _metrics(profile)
    entries = []
    for identity, threshold, name, description in _BADGES:
        unlocked = identity in known_badges
        entries.append(dict(
            id=identity if unlocked else None, name=name if unlocked else 'Unknown badge',
            description=description if unlocked else 'Keep driving to discover this badge.',
            unlocked=unlocked, secret=True,
            requirement=(f'Win {threshold} consecutive challenges without a defeat.' if unlocked else None),
            progress=None, asset_relpath=None, frame='badge', quote=None))
    for row in _STICKERS:
        current = min(metrics[row['metric']], row['threshold'])
        unit = 'cars' if row['metric'].startswith('cars_') else 'XP'
        entries.append(dict(
            id=row['id'], name=row['name'], description=row['description'],
            unlocked=row['id'] in acquired, secret=False, requirement=row['requirement'],
            progress=dict(current=current, target=row['threshold'], unit=unit,
                          label=f"{current}/{row['threshold']} {unit}"),
            asset_relpath=row['asset_relpath'], frame=row['frame'],
            quote=deepcopy(_QUOTES[row['quote_id']]) if row['quote_id'] else None))
    return entries


def asset_manifest():
    """Lista dos arquivos fixados; nenhum nome de arquivo é aceito da UI."""
    return [dict(path=name, bytes=size, sha256=digest)
            for name, (size, digest) in EXPECTED_FILES.items()]


def _read_asset(path, expected_size, expected_digest):
    stream, before = safe.open_reference(path)
    with stream:
        if before.st_size != expected_size:
            raise ValueError('Rogue album asset size differs: ' + path.name)
        raw = stream.read(expected_size+1)
        after = os.fstat(stream.fileno())
    safe.check_components(path)
    current = path.lstat()
    safe.require_reference(current, path)
    if (safe.signature(before) != safe.signature(after)
            or safe.signature(after) != safe.signature(current)):
        raise RuntimeError('Rogue album asset changed during reading: ' + path.name)
    if len(raw) != expected_size or hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError('Rogue album asset hash differs: ' + path.name)
    return raw


def load_album_distribution(asset_root):
    """Kit completo verificado de pasta explícita, sem rede, links ou escrita."""
    root = safe.source_root(asset_root)
    return {name: _read_asset(root / name, *EXPECTED_FILES[name])
            for name in ALBUM_DISTRIBUTION_NAMES}


def asset_path(asset_root, identity):
    """Resolve um ID conhecido para a imagem original cujo hash foi conferido."""
    if type(identity) is not str:
        raise ValueError('Unknown Rogue sticker.')
    if identity in {row[0] for row in _BADGES}:
        return None
    row = next((entry for entry in _STICKERS if entry['id'] == identity), None)
    if row is None:
        raise ValueError('Unknown Rogue sticker.')
    root = safe.source_root(asset_root)
    path = root / row['asset_relpath']
    _read_asset(path, *EXPECTED_FILES[row['asset_relpath']])
    return path
