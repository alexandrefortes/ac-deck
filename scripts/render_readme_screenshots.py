"""Capture the real SDL interface with an authored demo catalog, without a window.

Development tool only. No installed game, player data, network, microphone,
controller enumeration or session launch is needed. Demo illustrations are
schematics, not simulator screenshots or distributed game assets.
"""
from collections import OrderedDict
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
from src.launcher import event_synthetizer
from src.launcher.native_menu import NativeMenu
from src.launcher.window import Window, library


def put(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')
    return path


def demo_preview(path, *, track=False, accent=(243, 205, 85)):
    """Original schematic content; no external photographs or game textures."""
    image = Image.new('RGB', (640, 360), (8, 10, 12))
    draw = ImageDraw.Draw(image)
    if track:
        points = [(125, 234), (135, 140), (223, 92), (350, 102), (397, 157),
                  (504, 146), (535, 209), (475, 271), (378, 265), (330, 210),
                  (267, 254), (190, 275), (125, 234)]
        points = [(int(320 + (x-320)*.82), y) for x, y in points]
        draw.line(points, fill=(43, 52, 60), width=24, joint='curve')
        draw.line(points, fill=accent, width=4, joint='curve')
        draw.line([(125, 208), (143, 208)], fill=(242, 240, 233), width=5)
    else:
        draw.ellipse((112, 246, 557, 275), fill=(17, 22, 26))
        draw.polygon([(104, 223), (135, 201), (231, 186), (280, 145),
                      (390, 145), (446, 188), (526, 204), (559, 229),
                      (548, 246), (116, 246)], fill=(107, 124, 136))
        draw.polygon([(254, 186), (290, 153), (382, 153), (424, 186)], fill=(24, 36, 44))
        draw.line([(343, 152), (349, 187)], fill=(107, 124, 136), width=5)
        draw.line([(137, 209), (519, 209)], fill=accent, width=5)
        draw.line([(355, 194), (355, 236)], fill=(58, 76, 86), width=2)
        for center in (196, 478):
            draw.ellipse((center-33, 216, center+33, 282), fill=(12, 15, 19), outline=(72, 84, 92), width=3)
            draw.ellipse((center-20, 229, center+20, 269), fill=(56, 68, 78), outline=(151, 163, 173), width=3)
            draw.ellipse((center-5, 244, center+5, 254), fill=accent)
        draw.rectangle((115, 216, 138, 222), fill=(240, 226, 176))
        draw.rectangle((532, 219, 549, 225), fill=(163, 69, 68))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def demo_game(root):
    for identity, name, color in [('club_gt', 'Club GT', (243, 205, 85)),
                                   ('roadster_1600', 'Roadster 1600', (105, 181, 199))]:
        base = 'content/cars/' + identity
        put(root, base + '/data.acd', 'Authored demonstration marker; not playable content.\n')
        put(root, base + '/skins/demo/skin.ini', '[DEMO]\n')
        put(root, base + '/ui/ui_car.json', json.dumps(dict(name=name, brand='ac-deck demo',
            country='Demo', tags=['#Club Racing'], **{'class': 'Club Racing'})))
        demo_preview(root / base / 'skins/demo/preview.png', accent=color)
    for identity, name, distance in [('harbor_circuit', 'Harbor Circuit', '3.8 km'),
                                      ('hillcrest_park', 'Hillcrest Park', '4.2 km')]:
        base = 'content/tracks/' + identity
        put(root, base + '/ui/ui_track.json', json.dumps(dict(name=name, country='Demo',
            pitboxes=16, length=distance, tags=['circuit'])))
        put(root, base + '/ai/fast_lane.ai', 'Authored demonstration marker; not a racing line.\n')
        demo_preview(root / base / 'ui/preview.png', track=True)
    put(root, 'content/weather/clear/weather.ini',
        '[CLOUDS]\nNUMBER=0\n[FOG]\nDISTANCE=8000\n[LAUNCHER]\nNAME=Clear\n')
    for identity, name in [('club_sprint', 'Club Sprint'), ('harbor_challenge', 'Harbor Challenge'),
                           ('roadster_cup', 'Roadster Cup'), ('weekend_sprint', 'Weekend Sprint')]:
        put(root, 'content/specialevents/' + identity + '/event.ini',
            '[EVENT]\nNAME=' + name + '\nDESCRIPTION=An authored demonstration event.\n'
            '[RACE]\nMODEL=club_gt\nTRACK=harbor_circuit\nCONFIG_TRACK=\nCARS=6\nAI_LEVEL=90\n'
            '[CAR_0]\nSKIN=demo\n[SESSION_0]\nTYPE=3\nLAPS=3\n')


def capture(menu, destination, width, height):
    window = Window.__new__(Window)
    window.sdl = library()
    window.trace = lambda *args, **kwargs: None
    window.window = window.renderer = None
    window.controllers, window.textures, window.images, window.fonts = [], {}, OrderedDict(), {}
    window._rumble_controller = None
    window._bind()
    sdl = window.sdl
    sdl.SDL_CreateRGBSurfaceWithFormat.argtypes = [C.c_uint32, C.c_int, C.c_int, C.c_int, C.c_uint32]
    sdl.SDL_CreateRGBSurfaceWithFormat.restype = C.c_void_p
    sdl.SDL_CreateSoftwareRenderer.argtypes = [C.c_void_p]
    sdl.SDL_CreateSoftwareRenderer.restype = C.c_void_p
    if sdl.SDL_Init(0):
        raise RuntimeError(window.error())
    surface = sdl.SDL_CreateRGBSurfaceWithFormat(0, width, height, 32, 0x16762004)
    if not surface:
        sdl.SDL_Quit()
        raise RuntimeError(window.error())
    try:
        window.renderer = sdl.SDL_CreateSoftwareRenderer(surface)
        if not window.renderer or sdl.SDL_RenderSetLogicalSize(window.renderer, 1280, 800):
            raise RuntimeError(window.error())
        menu.draw(window)
        pixels = (C.c_ubyte * (width * height * 4))()
        if sdl.SDL_RenderReadPixels(window.renderer, None, 0x16762004, pixels, width * 4):
            raise RuntimeError(window.error())
        Image.frombytes('RGBA', (width, height), bytes(pixels)).save(destination)
    finally:
        window.close()
        sdl.SDL_FreeSurface(surface)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/screenshots')
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(prefix='ac-deck-demo-') as temporary:
        root = Path(temporary)
        game = root / 'demo-game'
        demo_game(game)
        catalog = event_synthetizer.discover(game)
        menu = NativeMenu(catalog, dict(mode=2, laps=3, ai=90, opponents=5, time_minutes=660),
            game=game, csp=True, synthesis_store=root / 'package/launcher/event-synthetizer.json')
        try:
            for view in ('drive', 'events', 'synth', 'rogue', 'settings'):
                if view == 'settings':
                    menu._navigate('drive')
                menu._navigate(view)
                if view == 'synth':
                    proposal, generated_catalog = event_synthetizer.generate(game,
                        menu.event_base(), fixed=menu.event_options['pins'], catalog=menu.catalog, seed=17)
                    menu.replace_catalog(generated_catalog)
                    menu.synthesis = proposal
                    menu.source = 'generated'
                    menu.focus_id = 'start'
                elif view == 'rogue':
                    menu.rogue_store.start_run(dict(menu.selection), seed=17)
                    if not menu.generate_rogue_challenge():
                        raise RuntimeError(menu.message)
                    menu.focus_id = 'start'
                for width, height in ((1280, 800), (1920, 1200)):
                    name = 'ac-deck-' + view + '-' + str(width) + 'x' + str(height) + '.png'
                    destination = args.output / name
                    capture(menu, destination, width, height)
                    rows.append(dict(file=name, view=view, width=width, height=height,
                        sha256=hashlib.sha256(destination.read_bytes()).hexdigest()))
                    print(name)
        finally:
            menu.close()
    sources = ['src/launcher/ui_render.py', 'src/launcher/window.py', 'src/launcher/native_menu.py',
               'src/launcher/rogue_ui.py', 'src/launcher/campaign_ui.py', 'scripts/render_readme_screenshots.py']
    manifest = dict(schema=1, product='ac-deck', method='SDL2 software surface / actual UI renderer',
        demo_catalog=True, game_started=False, network_used=False,
        artwork='Original schematic car and circuit illustrations; fictional demo names.',
        source_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
        images=rows)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
