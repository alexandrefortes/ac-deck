"""Configurações nativas de direção, botões XInput e visão do piloto."""

MODES = {'original': 'Original', 'assisted': 'Assisted (CSP)'}
FIELDS = {
    'steer_speed_pct': ('STEER_SPEED', 'Steering speed'),
    'steer_filter_pct': ('STEER_FILTER', 'Steering filter'),
    'speed_sensitivity_pct': ('SPEED_SENSITIVITY', 'Speed sensitivity'),
    'steer_deadzone_pct': ('STEER_DEADZONE', 'Deadzone'),
    'rumble_pct': ('RUMBLE_INTENSITY', 'Rumble'),
}
BINDINGS = {
    'gear_up_button': ('GEARUP', 'Gear up', 'B'),
    'gear_down_button': ('GEARDN', 'Gear down', 'X'),
    'handbrake_button': ('HANDBRAKE', 'Handbrake', 'A'),
    'change_view_button': ('ACTION_CHANGE_CAMERA', 'Change view', 'Y'),
}
BUTTONS = {'A':'A', 'B':'B', 'X':'X', 'Y':'Y', 'LSHOULDER':'LB',
           'RSHOULDER':'RB', 'BACK':'View', '-1':'Unbound'}
DEFAULTS = dict(hide_driver_arms=True, virtual_steer_degrees=160,
                steer_deadzone_pct=0, steer_gamma_tenths=None, controls_version=1,
                **{key:row[2] for key,row in BINDINGS.items()})


def set_binding(selection, key, value):
    """Troca os dois comandos ao escolher um botão já usado entre os quatro."""
    previous = selection[key]
    if value != '-1':
        for other in BINDINGS:
            if other != key and selection.get(other) == value:
                selection[other] = previous
    selection[key] = value


def validate(selection):
    if selection.get('control_mode', 'original') not in MODES:
        raise ValueError('Modo de controle desconhecido')
    for key in FIELDS:
        value = selection.get(key)
        if value is not None and (type(value) is not int or not 0 <= value <= 100):
            raise ValueError('Ajuste de controle deve ser percentual entre 0 e 100: '+key)
    value = selection.get('steer_gamma_tenths')
    if value is not None and (type(value) is not int or not 1 <= value <= 50):
        raise ValueError('Gamma da direção deve estar entre 0,1 e 5,0')
    value = selection.get('virtual_steer_degrees')
    if 'virtual_steer_degrees' in selection and (type(value) is not int or not 0 <= value <= 1080):
        raise ValueError('Ângulo do volante virtual deve estar entre 0 e 1080 graus')
    if 'hide_driver_arms' in selection and type(selection['hide_driver_arms']) is not bool:
        raise ValueError('Ocultar braços deve ser Sim ou Não')
    assigned = []
    for key in BINDINGS:
        if key not in selection:
            continue
        value = selection[key]
        if not isinstance(value, str) or value not in BUTTONS:
            raise ValueError('Botão de gamepad inválido: '+key)
        if value != '-1':
            if value in assigned:
                raise ValueError('Botão repetido entre os comandos de corrida')
            assigned.append(value)


def apply(ini, selection):
    """Manter/None conserva o valor existente; só altera escolhas explícitas."""
    validate(selection)
    if ini.get('HEADER', 'INPUT_METHOD', fallback='') != 'X360':
        raise ValueError('Os ajustes de analógico exigem o preset X360 já preparado')
    if 'X360' not in ini:
        ini.add_section('X360')
    for key, (field, _) in FIELDS.items():
        if selection.get(key) is not None:
            ini['X360'][field] = format(selection[key]/100, '.2f')
    if selection.get('steer_gamma_tenths') is not None:
        ini['X360']['STEER_GAMMA'] = format(selection['steer_gamma_tenths']/10, '.1f')
    targets = {row[0]:selection[key] for key,row in BINDINGS.items() if key in selection}
    # Um botão de corrida não deve disparar faróis/buzina ou outro comando.
    # Retira apenas XBOXBUTTON; teclado, eixos e parâmetros físicos permanecem.
    used = set(targets.values())-{'-1'}
    for section in ini.sections():
        if section not in targets and ini.get(section, 'XBOXBUTTON', fallback='') in used:
            ini[section]['XBOXBUTTON'] = '-1'
    for section, button in targets.items():
        if section not in ini:
            ini.add_section(section)
        ini[section]['XBOXBUTTON'] = button
