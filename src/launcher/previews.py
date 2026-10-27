"""Previews locais do conteúdo AC; sem downloads ou escrita de imagens.

``paths`` retorna candidatos regulares existentes, em ordem de preferência.
``thumbnail`` retorna (largura, altura, bytes RGBA), ou None se indisponível.
Os limites abaixo são política do launcher, não limites do formato do jogo.
"""
import io
import os
from pathlib import Path
import re
import warnings

from . import file_io as safe


MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_PIXELS = 16 * 1024 * 1024
MAX_THUMBNAIL_SIDE = 2048
_IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')


def _identifier(value, *, empty=False):
    if empty and value == '':
        return value
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError('Identificador de preview inválido')
    return value


def paths(game, item, kind='car', skin=None):
    """Localiza imagens do carro/skin ou da pista/layout do catálogo.

    Carro: skin selecionada primeiro, depois outras skins declaradas no item.
    Pista: UI do layout primeiro, depois UI comum. ``outline`` usa seu PNG.
    Ausência, links ou metadados inválidos omitem a imagem, sem abrir o alvo.
    """
    try:
        game = safe.absolute(game)
        safe.check_components(game)
        identity = _identifier(item['id'])
        candidates = []
        if kind == 'car':
            declared = item.get('skins', ())
            if not isinstance(declared, (tuple, list)):
                return ()
            names = ([skin] if skin is not None else []) + list(declared[:64])
            for name in dict.fromkeys(names):
                name = _identifier(name)
                root = game/'content/cars'/identity/'skins'/name
                candidates.extend(root/filename for filename in ('preview.jpg', 'preview.png', 'preview.jpeg'))
        elif kind in ('track', 'outline'):
            layout = _identifier(item.get('layout', ''), empty=True)
            root = game/'content/tracks'/identity/'ui'
            roots = (root/layout, root) if layout else (root,)
            filenames = ('outline.png',) if kind == 'outline' else ('preview.png', 'preview.jpg', 'preview.jpeg')
            candidates = [folder/name for folder in roots for name in filenames]
        else:
            return ()
        found = []
        for path in candidates:
            try:
                safe.check_components(path)
                info = path.lstat()
                safe.require_reference(info, path)
                if 0 < info.st_size <= MAX_FILE_BYTES:
                    found.append(path)
            except (OSError, safe.SafetyError):
                continue
        return tuple(found)
    except (OSError, ValueError, TypeError, KeyError, safe.SafetyError):
        return ()


def thumbnail(path, size=(320, 180)):
    """Lê JPEG/PNG limitado e devolve miniatura RGBA sem ampliar a origem.

    Mantém proporção e transparência. Pillow ausente ou imagem inválida retorna
    None. Não segue links, não cria cache e não altera a imagem da instalação.
    """
    if not isinstance(size, (tuple, list)) or len(size) != 2 or any(
            type(value) is not int or not 1 <= value <= MAX_THUMBNAIL_SIDE for value in size):
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        path = safe.absolute(path)
        safe.check_components(path)
        safe.require_reference(path.lstat(), path)
        stream, before = safe.open_reference(path)
        with stream:
            if not 0 < before.st_size <= MAX_FILE_BYTES:
                return None
            data = stream.read(MAX_FILE_BYTES + 1)
            after = os.fstat(stream.fileno())
        safe.check_components(path)
        current = path.lstat()
        safe.require_reference(after, path)
        safe.require_reference(current, path)
        if len(data) != before.st_size or safe.signature(before) != safe.signature(after) or safe.signature(before) != safe.signature(current):
            return None
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=('PNG', 'JPEG')) as source:
                if source.width * source.height > MAX_SOURCE_PIXELS:
                    return None
                source.thumbnail(tuple(size), Image.Resampling.LANCZOS)
                rgba = source.convert('RGBA')
                return rgba.width, rgba.height, rgba.tobytes()
    except (OSError, ValueError, TypeError, SyntaxError, OverflowError, safe.SafetyError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None
