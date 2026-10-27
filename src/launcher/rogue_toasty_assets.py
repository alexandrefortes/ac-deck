"""Mídia Toasty verificada de pasta explícita; sem carregar áudio ou desenhar UI.

O aviso MIT do projeto upstream acompanha sua procedência. Não atribuímos essa
licença independentemente à imagem/voz de referência Mortal Kombat; o registro
``media-rights.json`` preserva essa distinção na distribuição privada autorizada.
"""
import hashlib
import os

from . import file_io as safe


PAYLOAD_NAMES = ('toasty.png', 'toasty.wav')
EXPECTED_FILES = {
    'toasty.png': (49183, 'befcdafff8ab786797ecbaa3770a0b8af8e1ac7469381d179944c1aaac754cfe'),
    'toasty.wav': (62252, '1b015f6728b842f3fb0e0b0d4c5b36954ac863b0d07b52b8d2c5dfb4bb9477a1'),
    'toasty.mp3': (11310, '13b40a7c573f866e502fe9a77f8394f75884fda268ed32de6b2605fea41c4a5a'),
    'README.md': (461, '4ba285bc37c19c158bb4b83e9273b736bf2e4a6efb63d90f34bc449b22920a3b'),
    'LICENSE': (1080, '8bab9584f6730b8dbfc2d4991c7d237dbb0f46158ada957d15b58996324c057b'),
    'origin.json': (1528, '9f1350260ffa8bdbcd71c2d91925e3c09995eca45e377425eb1073ab7a56285c'),
    'derivation.json': (1218, '1c71209d2e9f14a63704615726321ebfa729e30af76a08b594dae74ea29daa7e'),
    'media-rights.json': (739, 'f826c58ad95a26f6433547a949b3ebf56e3f76161ea330174074e95e6a0c8f4d'),
    'asset-manifest.json': (1458, '0628afe56026b9ef47cf74c82e8e3fc36b460494c446b17c22e567a57319f359'),
}
DISTRIBUTION_NAMES = tuple(EXPECTED_FILES)


def _read(path, expected_size, expected_digest):
    stream, before = safe.open_reference(path)
    with stream:
        if before.st_size != expected_size:
            raise ValueError('Toasty asset size differs: ' + path.name)
        data = stream.read(expected_size + 1)
        after = os.fstat(stream.fileno())
    safe.check_components(path)
    current = path.lstat()
    safe.require_reference(current, path)
    if (safe.signature(before) != safe.signature(after)
            or safe.signature(after) != safe.signature(current)):
        raise RuntimeError('Toasty asset changed during reading: ' + path.name)
    if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_digest:
        raise ValueError('Toasty asset hash differs: ' + path.name)
    return data


def load_distribution(asset_root):
    """Lê os nove arquivos geridos, com tamanho/hash fixos e sem seguir links.

    ``asset_root`` é a pasta exata ``assets/rogue-toasty``. Arquivos extras não
    são importados nem alterados. Nenhum caminho padrão, rede ou player é usado.
    """
    root = safe.source_root(asset_root)
    return {name: _read(root / name, *EXPECTED_FILES[name]) for name in DISTRIBUTION_NAMES}


def load_assets(asset_root):
    """Valida mídia/procedência completas e retorna apenas PNG/WAV para o app CSP."""
    verified = load_distribution(asset_root)
    return {name: verified[name] for name in PAYLOAD_NAMES}
