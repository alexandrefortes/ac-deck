"""Preferências do piloto, independentes do perfil gráfico."""

DEFAULTS = dict(automatic_clutch=True, automatic_headlights=True, automatic_wipers=True,
                pause_unfocused=True, simple_ui=True, csp_ui_scale=1.15,
                frame_limiter='game_60', mirrors='off', race_taskbar=True,
                stability_control=22, auto_blip=True, tyre_blankets=True,
                abs_mode='factory', traction_control='factory', car_damage_pct=None)
SETTINGS = {'automatic_headlights': 'Automatic headlights (CSP)',
            'automatic_wipers': 'Automatic wipers (CSP)',
            'pause_unfocused': 'Pause when unfocused (CSP)',
            'simple_ui': 'Simple race UI (CSP)', 'csp_ui_scale': 'Race UI scale (CSP)',
            'race_taskbar': 'Race app bar (CSP)'}
LIMITERS = {'game_60':'Game 60 FPS', 'external':'External / unlimited'}
MIRRORS = {'off':'Off', 'simple':'Simple', 'high':'High', 'keep':'Keep current'}
SCALES = (1, 1.15, 1.25, 1.5)
ASSIST_MODES = {'off': '0', 'factory': '1', 'on': '2'}
ASSIST_LABELS = {'off': 'Off', 'factory': 'Factory', 'on': 'On'}


def validate(selection):
    for key, default in DEFAULTS.items():
        if key not in selection:
            continue
        value = selection[key]
        if type(default) is bool and type(value) is not bool:
            raise ValueError('Setting must be On or Off: '+key)
    for key, choices in (('frame_limiter', LIMITERS), ('mirrors', MIRRORS),
                         ('abs_mode', ASSIST_MODES), ('traction_control', ASSIST_MODES)):
        if key in selection and (not isinstance(selection[key], str) or selection[key] not in choices):
            raise ValueError('Unknown setting: '+key)
    if 'stability_control' in selection:
        value = selection['stability_control']
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError('Stability control must be an integer from 0 to 100')
    damage = selection.get('car_damage_pct')
    if damage is not None and (type(damage) is not int or not 0 <= damage <= 100):
        raise ValueError('Car damage must be an integer from 0 to 100 or Keep current')
    if 'csp_ui_scale' in selection:
        value = selection['csp_ui_scale']
        if type(value) not in (int, float) or value not in SCALES:
            raise ValueError('Unsupported race UI scale')


def apply_native(video, assists, selection):
    validate(selection)
    # Aplicar também aos pacotes existentes, sem depender de preparar o vínculo
    # novamente. Factory usa somente a assistência disponível no carro.
    values = {key: selection.get(key, DEFAULTS[key]) for key in
              ('stability_control', 'auto_blip', 'tyre_blankets', 'abs_mode', 'traction_control')}
    assists['ASSISTS'].update(
        # Configuração fixa: valores herdados ou seleções antigas não reativam.
        IDEAL_LINE='0',
        STABILITY_CONTROL=str(values['stability_control']),
        AUTO_BLIP='1' if values['auto_blip'] else '0',
        TYRE_BLANKETS='1' if values['tyre_blankets'] else '0',
        ABS=ASSIST_MODES[values['abs_mode']],
        TRACTION_CONTROL=ASSIST_MODES[values['traction_control']])
    if selection.get('car_damage_pct') is not None:
        assists['ASSISTS']['DAMAGE'] = str(selection['car_damage_pct'])
    if 'automatic_clutch' in selection:
        assists['ASSISTS']['AUTO_CLUTCH'] = '1' if selection['automatic_clutch'] else '0'
    if 'frame_limiter' in selection:
        video['VIDEO']['FPS_CAP_MS'] = '16.666667' if selection['frame_limiter']=='game_60' else '0'
        video['VIDEO']['VSYNC'] = '0'
    # Pedido do piloto: desligados em todos os perfis. Preferências antigas
    # continuam legíveis, mas não podem reativar a renderização dos espelhos.
    if 'MIRROR' not in video:
        video.add_section('MIRROR')
    video['MIRROR'].update(SIZE='0', HQ='0')


def apply_csp(settings, selection):
    validate(selection)
    def put(name, section, **values):
        settings.setdefault(name, {}).setdefault(section, {}).update(values)
    for key, field in (('automatic_headlights','SWITCH_HEADLIGHTS_WITH_AI'),
                       ('automatic_wipers','SWITCH_WIPERS_WITH_AI')):
        if key in selection:
            put('weather_fx.ini', 'MISCELLANEOUS', **{field:'1' if selection[key] else '0'})
    if 'pause_unfocused' in selection:
        put('small_tweaks.ini','BASIC',ENABLED='1')
        put('small_tweaks.ini','MISCELLANEOUS',PAUSE_IN_BACKGROUND='1' if selection['pause_unfocused'] else '0')
    if 'simple_ui' in selection:
        put('gui.ini','BASIC',ENABLED='1',CONTROLLER_INTEGRATION='1',CONTROLLER_INTEGRATION_PITS='1')
        put('gui.ini','NEW_UI',SIMPLIFIED_RENDER='1' if selection['simple_ui'] else '0',
            REDUCED_ANIMATIONS='1' if selection['simple_ui'] else '0',REPLACE_MAIN_MENU='0')
    if 'csp_ui_scale' in selection:
        put('gui.ini','NEW_UI',UI_SCALE=format(selection['csp_ui_scale'],'.2f'))
    if 'race_taskbar' in selection:
        put('gui.ini','NEW_UI',REPLACE_TASKBAR='1')
        put('gui.ini','HIDE',HIDE_TASKBAR='0' if selection['race_taskbar'] else '1')
