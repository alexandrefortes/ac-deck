"""Perfis gráficos autorais para o jogo nativo; não ativa ou configura CSP.

Campos interoperáveis conferidos na referência VideoSettings.cs, revisão
e5e5c94b8dee7511def0b670bfd5dbb233831c11. Ver o estudo em docs/.
Valores propostos para o portátil, ainda sem medição de desempenho no Deck.
"""

from . import graphics_settings

LABELS = {'performance': 'Performance', 'quality': 'Quality',
          'csp_performance': 'CSP Performance', 'csp_quality': 'CSP Quality'}
PRESET_REVISION = 2
SHADOW_DISTANCE_DEFAULT = 100
SHADOW_DISTANCE_MIN = 50
SHADOW_DISTANCE_MAX = 400


def profile_shadow_distance(profile):
    return 50 if profile == 'csp_performance' else SHADOW_DISTANCE_DEFAULT


def shadow_distance(selection):
    value = selection.get('shadow_distance_m', profile_shadow_distance(selection.get('graphics_profile')))
    if type(value) is not int or not SHADOW_DISTANCE_MIN <= value <= SHADOW_DISTANCE_MAX:
        raise ValueError('Shadow distance must be an integer from 50 to 400 m')
    return value


def base_profile(profile):
    if not isinstance(profile, str) or profile not in LABELS:
        raise ValueError('Perfil gráfico desconhecido')
    return profile.removeprefix('csp_')


def uses_csp(profile):
    base_profile(profile)
    return profile.startswith('csp_')


def normalize(selection, *, csp_available):
    """O Quality CSP revisado exige escolha nova; preferências válidas persistem."""
    result = dict(selection)
    profile = result.get('graphics_profile')
    if profile == 'csp_quality' and result.get('graphics_preset_revision') != PRESET_REVISION:
        profile = 'csp_performance' if csp_available else 'performance'
        result['graphics_profile'] = profile
    if not csp_available and profile in LABELS:
        result['graphics_profile'] = base_profile(profile)
    result['graphics_preset_revision'] = PRESET_REVISION
    result.pop('csp_linear', None)
    effective_profile = result.get('graphics_profile') or ('csp_performance' if csp_available else 'performance')
    result['shadow_distance_m'] = shadow_distance(dict(result, graphics_profile=effective_profile))
    result.setdefault('smart_shadows', False)
    if type(result['smart_shadows']) is not bool:
        raise ValueError('Smart Shadows must be On or Off')
    return graphics_settings.normalize(result, result.get('graphics_profile') or ('csp_performance' if csp_available else 'performance'))


def migrate(selection, *, csp_available):
    """A seleção antiga do kit CSP continua CSP; não muda controles/conteúdo."""
    result = dict(selection)
    if result.get('graphics_profiles_version') != 2:
        old = result.get('graphics_profile', 'performance')
        if csp_available and old in ('performance', 'quality'):
            result['graphics_profile'] = 'csp_'+old
        result['graphics_profiles_version'] = 2
    return normalize(result, csp_available=csp_available)
COMMON = {
    'CUBEMAP': {'SIZE': '512', 'FARPLANE': '500'},
    'POST_PROCESS': {'ENABLED': '1', 'DOF': '0', 'HEAT_SHIMMER': '0',
                     'RAYS_OF_GOD': '0', 'FXAA': '0'},
    'EFFECTS': {'RENDER_SMOKE_IN_MIRROR': '0'},
}
PROFILES = {
    'performance': {
        'VIDEO': {'AASAMPLES': '2', 'ANISOTROPIC': '8', 'SHADOW_MAP_SIZE': '1024'},
        'ASSETTOCORSA': {'WORLD_DETAIL': '3'},
        'CUBEMAP': {'FACES_PER_FRAME': '0'},
        'POST_PROCESS': {'QUALITY': '2', 'GLARE': '1'},
        'EFFECTS': {'MOTION_BLUR': '0', 'SMOKE': '2'},
    },
    'quality': {
        'VIDEO': {'AASAMPLES': '4', 'ANISOTROPIC': '16', 'SHADOW_MAP_SIZE': '2048'},
        'ASSETTOCORSA': {'WORLD_DETAIL': '4'},
        'CUBEMAP': {'FACES_PER_FRAME': '1'},
        'POST_PROCESS': {'QUALITY': '3', 'GLARE': '2'},
        'EFFECTS': {'MOTION_BLUR': '2', 'SMOKE': '3'},
    },
}


# Os perfis nativos permanecem intactos. O CSP acrescenta só estes campos.
CSP_PROFILES = {
    'performance': {'VIDEO': {'AASAMPLES': '2', 'SHADOW_MAP_SIZE': '512'},
                    'ASSETTOCORSA': {'WORLD_DETAIL': '2'},
                    'CUBEMAP': {'FACES_PER_FRAME': '0', 'FARPLANE': '100'},
                    'POST_PROCESS': {'FXAA': '1', 'DOF': '0'},
                    'EFFECTS': {'MOTION_BLUR': '0'}},
    'quality': {'VIDEO': {'SHADOW_MAP_SIZE': '1024'},
                'CUBEMAP': {'FACES_PER_FRAME': '1'},
                'POST_PROCESS': {'FXAA': '1'},
                'EFFECTS': {'SMOKE': '2'}},
}


def apply(video, profile, *, csp=None, selection=None):
    """Altera somente campos de renderização; preserva resolução e preferências."""
    active_csp = uses_csp(profile) if csp is None else csp
    profile = base_profile(profile)
    for settings in (COMMON, PROFILES[profile], CSP_PROFILES[profile] if active_csp else {}):
        for section, values in settings.items():
            if section not in video:
                video.add_section(section)
            video[section].update(values)

    if selection is not None:
        effective_profile = ('csp_' if active_csp else '')+profile
        current = selection if 'graphics_options' in selection else dict(selection, graphics_profile=effective_profile)
        graphics_settings.apply_native(video, current)
