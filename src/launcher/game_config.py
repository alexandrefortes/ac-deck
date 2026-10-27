"""Perfis INI iniciais e serialização de configuração do jogo.

Preserva os valores explícitos da preparação anterior; não lê o perfil pessoal.
"""
import configparser
import io

from .assists_config import AssistState, AssistsSettings, build_assists_ini
from .practice_session import Car, Track, Catalog, PracticeRequest, build_practice_plan


def parse_ini(path):
    result = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(';',))
    result.optionxform = str
    result.read_string(path.read_text('utf-8-sig'))
    return result


def ini_bytes(ini):
    stream = io.StringIO()
    ini.write(stream, space_around_delimiters=False)
    return stream.getvalue().encode('utf-8')


def profile_texts(game):
    """Valores de teste explícitos; não importa o perfil pessoal do jogador."""
    catalog = Catalog((Car('abarth500', ('0_white_scorpion',)),), (Track('magione', ('',)),),
                      ('3_clear',), 'not_verified', ('authored-deck-practice-profile-v1',))
    request = PracticeRequest('abarth500', '0_white_scorpion', 'magione', '',
                              'Teste Papao', 'Brazil', 'BRA', 10, (1280, 800))
    values = {'TEMPERATURE': {'ROAD': '32', 'AMBIENT': '26'},
              'LIGHTING': {'SUN_ANGLE': '-48', 'TIME_MULT': '1', 'CLOUD_SPEED': '0.2'},
              'WEATHER': {'NAME': '3_clear'},
              'WIND': {'SPEED_KMH_MIN': '0', 'SPEED_KMH_MAX': '0', 'DIRECTION_DEG': '0'},
              'DYNAMIC_TRACK': {'SESSION_START': '100', 'RANDOMNESS': '0', 'LAP_GAIN': '1', 'SESSION_TRANSFER': '50'}}
    # Reutiliza somente o texto do gerador; o destino real é definido abaixo.
    race = build_practice_plan(request, catalog,
        tuple((s, tuple(v.items())) for s,v in values.items()), game_dir='game', data_dir='state')
    assists = AssistsSettings(ideal_line=False, auto_blip=True, stability_control=22,
        auto_brake=False, auto_shifter=True, abs_state=AssistState.FACTORY,
        traction_control=AssistState.FACTORY, auto_clutch=True, visual_damage=True,
        damage='100', fuel_consumption='1', tyre_wear_multiplier='1',
        tyre_blankets=True, slipstream_multiplier='1')
    video = parse_ini(game/'cfg/video.ini')
    video['VIDEO'].update(WIDTH='1280', HEIGHT='800', FULLSCREEN='0', VSYNC='0', FPS_CAP_MS='0')
    if 'CAMERA' not in video:
        video.add_section('CAMERA')
    video['CAMERA']['MODE'] = 'DEFAULT'
    controls = parse_ini(game/'cfg/controls.ini')
    controls['HEADER']['INPUT_METHOD'] = 'X360'
    for section, button in [('GEARUP','RSHOULDER'),('GEARDN','LSHOULDER'),('HANDBRAKE','B'),('ACTION_HEADLIGHTS','X')]:
        if section not in controls:
            controls.add_section(section)
        controls[section]['XBOXBUTTON'] = button
    return {'race.ini': race.ini_text.encode('utf-8'), 'assists.ini': build_assists_ini(assists).encode('utf-8'),
            'video.ini': ini_bytes(video), 'controls.ini': ini_bytes(controls)}
