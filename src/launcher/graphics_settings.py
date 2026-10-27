"""Campos gráficos dos presets, com preferências editáveis e domínios explícitos.

Os perfis continuam definidos em graphics.py e csp.py. Este catálogo mapeia
somente renderização; física, controles, câmeras e assistências são separados.
"""
from copy import deepcopy

VERSION = 2
NATIVE = (('msaa', 'MSAA', 'VIDEO', 'AASAMPLES', ('1', '2', '4', '8')),
 ('anisotropic', 'Anisotropic filtering', 'VIDEO', 'ANISOTROPIC', ('0', '2', '4', '8', '16')),
 ('shadow_resolution', 'Shadow resolution', 'VIDEO', 'SHADOW_MAP_SIZE',
  ('-1', '32', '64', '128', '256', '512', '1024', '2048', '3072', '4096', '6144', '8192')),
 ('world_detail', 'World detail', 'ASSETTOCORSA', 'WORLD_DETAIL', ('0', '1', '2', '3', '4', '5')),
 ('reflection_resolution', 'Reflection resolution', 'CUBEMAP', 'SIZE', ('0', '256', '512', '1024', '2048')),
 ('reflection_distance', 'Reflection distance', 'CUBEMAP', 'FARPLANE', tuple(map(str, range(0,10001,100)))),
 ('reflection_updates', 'Reflection updates per frame', 'CUBEMAP', 'FACES_PER_FRAME',
  ('0', '1', '2', '3', '4', '5', '6')),
 ('post_processing', 'Post-processing', 'POST_PROCESS', 'ENABLED', ('0', '1')),
 ('post_quality', 'Post-processing quality', 'POST_PROCESS', 'QUALITY', ('0', '1', '2', '3', '4', '5')),
 ('glare', 'Glare', 'POST_PROCESS', 'GLARE', ('0', '1', '2', '3', '4', '5')),
 ('depth_of_field', 'Depth of field', 'POST_PROCESS', 'DOF', ('0', '1', '2', '3', '4', '5')),
 ('heat_shimmer', 'Heat shimmer', 'POST_PROCESS', 'HEAT_SHIMMER', ('0', '1')),
 ('sun_rays', 'Sun rays', 'POST_PROCESS', 'RAYS_OF_GOD', ('0', '1')),
 ('fxaa', 'Native FXAA', 'POST_PROCESS', 'FXAA', ('0', '1')),
 ('motion_blur', 'Native motion blur', 'EFFECTS', 'MOTION_BLUR',
  ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12')),
 ('smoke', 'Smoke quality', 'EFFECTS', 'SMOKE', ('0', '1', '2', '3', '4', '5')),
 ('smoke_mirrors', 'Smoke in mirrors', 'EFFECTS', 'RENDER_SMOKE_IN_MIRROR', ('0', '1')))
CSP = (('csp_general_optimizations_cache_acs', 'CSP asset cache', 'general.ini', 'OPTIMIZATIONS', 'CACHE_ACS',
  ('0', '1')),
 ('csp_general_optimizations_gpu_optimize_meshes', 'CSP / Optimize meshes', 'general.ini', 'OPTIMIZATIONS_GPU',
  'OPTIMIZE_MESHES', ('0', '1')),
 ('csp_general_optimizations_gpu_deduplicate_meshes', 'CSP / Deduplicate meshes', 'general.ini',
  'OPTIMIZATIONS_GPU', 'DEDUPLICATE_MESHES', ('0', '1')),
 ('csp_general_optimizations_gpu_deduplicate_textures', 'CSP / Deduplicate textures', 'general.ini',
  'OPTIMIZATIONS_GPU', 'DEDUPLICATE_TEXTURES', ('0', '1')),
 ('csp_general_optimizations_gpu_upgrade_textures', 'CSP / Upgrade textures', 'general.ini', 'OPTIMIZATIONS_GPU',
  'UPGRADE_TEXTURES', ('0', '1')),
 ('csp_general_optimizations_gpu_bc7_cache', 'CSP / Bc7 cache', 'general.ini', 'OPTIMIZATIONS_GPU', 'BC7_CACHE2',
  ('0', '1')),
 ('csp_general_optimizations_gpu_query_based_mapping', 'CSP / Query based mapping', 'general.ini',
  'OPTIMIZATIONS_GPU', 'QUERY_BASED_MAPPING2', ('0', '1')),
 ('csp_graphics_adjustments_basic_force_fxaa', 'Graphics / Force fxaa', 'graphics_adjustments.ini', 'BASIC',
  'FORCE_FXAA2', ('0', '1')),
 ('csp_graphics_adjustments_antialiasing_mode', 'CSP post-process AA', 'graphics_adjustments.ini', 'ANTIALIASING',
  'MODE', ('DISABLED', 'DEFAULT', 'YEBIS', 'CMAA', 'FXAA', 'FXAA3', 'SMAA')),
 ('csp_graphics_adjustments_antialiasing_msaa_custom_resolve', 'Graphics / Custom resolve',
  'graphics_adjustments.ini', 'ANTIALIASING_MSAA', 'CUSTOM_RESOLVE', ('0', '1')),
 ('csp_graphics_adjustments_antialiasing_msaa_custom_kernel', 'Graphics / Custom kernel',
  'graphics_adjustments.ini', 'ANTIALIASING_MSAA', 'CUSTOM_KERNEL', ('0', '1')),
 ('csp_graphics_adjustments_fsr_active', 'FSR', 'graphics_adjustments.ini', 'FSR', 'ACTIVE', ('0', '1')),
 ('csp_graphics_adjustments_render_scale_scale', 'Render scale', 'graphics_adjustments.ini', 'RENDER_SCALE',
  'SCALE', ('0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '1')),
 ('csp_graphics_adjustments_lods_cockpit_lr_fix', 'Graphics / Cockpit lr fix', 'graphics_adjustments.ini', 'LODS',
  'COCKPIT_LR_FIX', ('0', '1')),
 ('csp_graphics_adjustments_lods_driver_lr_fix', 'Graphics / Driver lr fix', 'graphics_adjustments.ini', 'LODS',
  'DRIVER_LR_FIX', ('0', '1')),
 ('csp_graphics_adjustments_lods_cars_distance_mult', 'Graphics / Cars distance mult', 'graphics_adjustments.ini',
  'LODS', 'CARS_DISTANCE_MULT',
  ('0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '1', '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7',
   '1.8', '1.9', '2', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8', '2.9', '3', '3.1', '3.2')),
 ('csp_graphics_adjustments_lods_track_distance_mult', 'Graphics / Track distance mult',
  'graphics_adjustments.ini', 'LODS', 'TRACK_DISTANCE_MULT',
  ('0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '1', '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7',
   '1.8', '1.9', '2', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8', '2.9', '3', '3.1', '3.2')),
 ('csp_graphics_adjustments_lods_trees_distance_mult', 'Graphics / Trees distance mult',
  'graphics_adjustments.ini', 'LODS', 'TREES_DISTANCE_MULT',
  ('0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '1', '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7',
   '1.8', '1.9', '2', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8', '2.9', '3', '3.1', '3.2')),
 ('csp_graphics_adjustments_lods_force_lod_b', 'Graphics / Force lod b', 'graphics_adjustments.ini', 'LODS',
  'FORCE_LOD_B', ('0', '1')),
 ('csp_graphics_adjustments_lods_treat_track_cameras_the_same', 'Graphics / Treat track cameras the same',
  'graphics_adjustments.ini', 'LODS', 'TREAT_TRACK_CAMERAS_THE_SAME', ('0', '1')),
 ('csp_graphics_adjustments_lods_fallback_lods', 'Graphics / Fallback lods', 'graphics_adjustments.ini', 'LODS',
  'FALLBACK_LODS', ('0', '1')),
 ('csp_graphics_adjustments_lods_lodless_limit', 'Graphics / Lodless limit', 'graphics_adjustments.ini', 'LODS',
  'LODLESS_LIMIT',
  ('2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21',
   '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39',
   '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '50', '51', '52', '53', '54', '55', '56', '57',
   '58', '59', '60', '61', '62', '63', '64', '65', '66', '67', '68', '69', '70', '71', '72', '73', '74', '75',
   '76', '77', '78', '79', '80', '81', '82', '83', '84', '85', '86', '87', '88', '89', '90', '91', '92', '93',
   '94', '95', '96', '97', '98', '99', '100', '101', '102', '103', '104', '105', '106', '107', '108', '109', '110',
   '111', '112', '113', '114', '115', '116', '117', '118', '119', '120', '121', '122', '123', '124', '125', '126',
   '127', '128', '129', '130', '131', '132', '133', '134', '135', '136', '137', '138', '139', '140', '141', '142',
   '143', '144', '145', '146', '147', '148', '149', '150', '151', '152', '153', '154', '155', '156', '157', '158',
   '159', '160', '161', '162', '163', '164', '165', '166', '167', '168', '169', '170', '171', '172', '173', '174',
   '175', '176', '177', '178', '179', '180', '181', '182', '183', '184', '185', '186', '187', '188', '189', '190',
   '191', '192', '193', '194', '195', '196', '197', '198', '199', '200')),
 ('csp_graphics_adjustments_lods_hide_distant_drivers', 'Graphics / Hide distant drivers',
  'graphics_adjustments.ini', 'LODS', 'HIDE_DISTANT_DRIVERS', ('0', '1')),
 ('csp_graphics_adjustments_lods_hide_wheels_for_interior_view', 'Graphics / Hide wheels for interior view',
  'graphics_adjustments.ini', 'LODS', 'HIDE_WHEELS_FOR_INTERIOR_VIEW', ('0', '1')),
 ('csp_graphics_adjustments_lods_skip_loading_first_lod_for_other_cars',
  'Graphics / Skip loading first lod for other cars', 'graphics_adjustments.ini', 'LODS',
  'SKIP_LOADING_FIRST_LOD_FOR_OTHER_CARS', ('0', '1')),
 ('csp_graphics_adjustments_lods_limit_visible_cars', 'Graphics / Limit visible cars', 'graphics_adjustments.ini',
  'LODS', 'LIMIT_VISIBLE_CARS', ('0', '1')),
 ('csp_smart_shadows_basic_automatic_splits', 'Shadows / Automatic splits', 'smart_shadows.ini', 'BASIC',
  'AUTOMATIC_SPLITS', ('0', '1')),
 ('csp_smart_shadows_custom_shadow_matrices_fourth_cascade', 'Shadows / Fourth cascade', 'smart_shadows.ini',
  'CUSTOM_SHADOW_MATRICES', 'FOURTH_CASCADE', ('0', '1')),
 ('csp_reflections_fx_main_cubemap_resolution2', 'CSP reflection resolution', 'reflections_fx.ini', 'MAIN_CUBEMAP',
  'RESOLUTION2', ('512', '1024', '2048')),
 ('csp_reflections_fx_main_cubemap_reproject_partial', 'Reflections / Reproject partial', 'reflections_fx.ini',
  'MAIN_CUBEMAP', 'REPROJECT_PARTIAL', ('0', '1')),
 ('csp_extra_fx_basic_enabled', 'Extra FX', 'extra_fx.ini', 'BASIC', 'ENABLED', ('0', '1')),
 ('csp_extra_fx_motion_blur_enabled', 'Extra FX motion blur', 'extra_fx.ini', 'MOTION_BLUR', 'ENABLED',
  ('0', '1')),
 ('csp_grass_fx_basic_quality', 'Grass quality', 'grass_fx.ini', 'BASIC', 'QUALITY', ('0', '1', '2', '3', '4')),
 ('csp_grass_fx_basic_enabled', 'Grass FX', 'grass_fx.ini', 'BASIC', 'ENABLED', ('0', '1')),
 ('csp_grass_fx_rendering_cast_shadows', 'Grass / Cast shadows', 'grass_fx.ini', 'RENDERING', 'CAST_SHADOWS',
  ('0', '1')),
 ('csp_grass_fx_rendering_extrafx_pass', 'Grass / Extrafx pass', 'grass_fx.ini', 'RENDERING', 'EXTRAFX_PASS',
  ('0', '1')),
 ('csp_grass_fx_rendering_smoother_blending', 'Grass / Smoother blending', 'grass_fx.ini', 'RENDERING',
  'SMOOTHER_BLENDING', ('0', '1')),
 ('csp_particles_fx_smoke_use_culling', 'Particles / Use culling', 'particles_fx.ini', 'SMOKE', 'USE_CULLING',
  ('0', '1')),
 ('csp_particles_fx_smoke_show_in_mirrors', 'Particles / Show in mirrors', 'particles_fx.ini', 'SMOKE',
  'SHOW_IN_MIRRORS', ('0', '1')),
 ('csp_particles_fx_smoke_cast_shadows', 'Particles / Cast shadows', 'particles_fx.ini', 'SMOKE', 'CAST_SHADOWS',
  ('0', '1')),
 ('csp_particles_fx_smoke_cast_ambient_shadows', 'Particles / Cast ambient shadows', 'particles_fx.ini', 'SMOKE',
  'CAST_AMBIENT_SHADOWS', ('0', '1')),
 ('csp_particles_fx_smoke_use_downscaling', 'Particles / Use downscaling', 'particles_fx.ini', 'SMOKE',
  'USE_DOWNSCALING', ('0', '1')),
 ('csp_particles_fx_smoke_simplified_shading', 'Particles / Simplified shading', 'particles_fx.ini', 'SMOKE',
  'SIMPLIFIED_SHADING', ('0', '1')),
 ('csp_particles_fx_fireworks_enabled', 'Fireworks', 'particles_fx.ini', 'FIREWORKS', 'ENABLED', ('0', '1')),
 ('csp_particles_fx_ac_particles_reworked_heat_shimmer', 'Particles / Reworked heat shimmer', 'particles_fx.ini',
  'AC_PARTICLES', 'REWORKED_HEAT_SHIMMER', ('0', '1')),
 ('csp_lighting_fx_shadows_enabled', 'Lighting shadows', 'lighting_fx.ini', 'SHADOWS', 'ENABLED', ('0', '1')),
 ('csp_lighting_fx_shadows_high_quality_headlight_shadows', 'Lighting / High quality headlight shadows',
  'lighting_fx.ini', 'SHADOWS', 'HIGH_QUALITY_HEADLIGHT_SHADOWS', ('0', '1')),
 ('csp_lighting_fx_performance_enable_reflection_light', 'Lighting / Enable reflection light', 'lighting_fx.ini',
  'PERFORMANCE', 'ENABLE_REFLECTION_LIGHT', ('0', '1')),
 ('csp_lighting_fx_performance_cars_with_lights', 'Lighting / Cars with lights', 'lighting_fx.ini', 'PERFORMANCE',
  'CARS_WITH_LIGHTS',
  ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19',
   '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37',
   '38', '39', '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '50')),
 ('csp_weather_fx_basic_enabled', 'Weather FX', 'weather_fx.ini', 'BASIC', 'ENABLED', ('0', '1')),
 ('csp_weather_fx_performance_additional_effects', 'Weather / Additional effects', 'weather_fx.ini', 'PERFORMANCE',
  'ADDITIONAL_EFFECTS', ('0', '1')),
 ('csp_weather_fx_performance_detailed_cloud_shadows', 'Weather / Detailed cloud shadows', 'weather_fx.ini',
  'PERFORMANCE', 'DETAILED_CLOUD_SHADOWS', ('0', '1')),
 ('csp_weather_fx_performance_slow_reflections_update', 'Weather / Slow reflections update', 'weather_fx.ini',
  'PERFORMANCE', 'SLOW_REFLECTIONS_UPDATE', ('0', '1')),
 ('csp_weather_fx_performance_high_quality_stars', 'Weather / High quality stars', 'weather_fx.ini', 'PERFORMANCE',
  'HIGH_QUALITY_STARS', ('0', '1')),
 ('csp_weather_fx_performance_extra_clouds_fidelity', 'Weather / Extra clouds fidelity', 'weather_fx.ini',
  'PERFORMANCE', 'EXTRA_CLOUDS_FIDELITY', ('0', '1')),
 ('csp_weather_fx_pp_tweaks_full_resolution', 'Weather / Full resolution', 'weather_fx.ini', 'PP_TWEAKS',
  'FULL_RESOLUTION', ('0', '1')),
 ('csp_smart_mirror_performance_skip_frames', 'Mirrors / Skip frames', 'smart_mirror.ini', 'PERFORMANCE',
  'SKIP_FRAMES', ('0', '1', '2', '3')))

FIELDS = {row[0]: row for row in (*NATIVE, *CSP)}
REMOVED_FIELDS = {'csp_general_optimizations_gpu_optimize_meshes_more',
                  'csp_general_fps_limit_tweaks_use_adjusted_frame_time',
                  'csp_general_fps_limit_tweaks_use_sleep',
                  'csp_graphics_adjustments_basic_enabled', 'csp_lighting_fx_basic_enabled'}
PREFERENCE_KEYS = ('graphics_profile', 'graphics_preset_revision', 'graphics_profiles_version',
                   'graphics_options', 'graphics_options_profile', 'graphics_options_version',
                   'smart_shadows', 'shadow_distance_m', 'resolution', 'hud', 'pp_filter',
                   'frame_limiter')


def defaults(profile):
    from . import graphics, csp
    native = {}
    for source in (graphics.COMMON, graphics.PROFILES[graphics.base_profile(profile)],
                   graphics.CSP_PROFILES[graphics.base_profile(profile)] if graphics.uses_csp(profile) else {}):
        for section, values in source.items():
            native.setdefault(section, {}).update(values)
    patched = csp.overrides(profile, 'original', 'original')
    result = {name: native[section][key] for name, label, section, key, choices in NATIVE}
    result.update({name: patched[file][section][key] for name, label, file, section, key, choices in CSP})
    return result


def values(selection):
    profile = selection.get('graphics_profile', 'performance')
    result = defaults(profile)
    custom = selection.get('graphics_options', {})
    if not isinstance(custom, dict):
        raise ValueError('Graphics values must be an object')
    custom = {name: value for name, value in custom.items() if name not in REMOVED_FIELDS}
    if selection.get('graphics_options_profile', profile) != profile:
        return result
    if set(custom)-FIELDS.keys():
        raise ValueError('Unknown graphics option')
    for name, value in custom.items():
        if type(value) is not str or value not in FIELDS[name][-1]:
            raise ValueError('Invalid graphics value: '+FIELDS[name][1])
    result.update(custom)
    if profile == 'csp_performance' and selection.get('graphics_options_version', 1) == 1:
        # Atualiza somente os antigos padrões; conserva os demais ajustes salvos.
        for name, previous, current in (('depth_of_field', '3', '0'),
                ('motion_blur', '12', '0'),
                ('csp_general_optimizations_cache_acs', '0', '1'),
                ('csp_general_optimizations_gpu_deduplicate_textures', '0', '1'),
                ('csp_general_optimizations_gpu_query_based_mapping', '0', '1')):
            if custom.get(name) == previous:
                result[name] = current
    return result


def normalize(selection, profile):
    result = deepcopy(selection)
    if not any(key in result for key in ('graphics_options', 'graphics_options_profile', 'graphics_options_version')):
        return result
    changed = result.get('graphics_options_profile', profile) != profile
    selected = dict(result, graphics_profile=profile)
    result['graphics_options'] = defaults(profile) if changed else values(selected)
    result['graphics_options_profile'] = profile
    result['graphics_options_version'] = VERSION
    if changed:
        from . import graphics
        result.update(smart_shadows=False, shadow_distance_m=graphics.profile_shadow_distance(profile))
    return result


def reset(selection, profile):
    from . import graphics
    selection.update(graphics_options=defaults(profile), graphics_options_profile=profile,
                     graphics_options_version=VERSION, smart_shadows=False,
                     shadow_distance_m=graphics.profile_shadow_distance(profile))


def keys(csp_available):
    return tuple('gfx:'+row[0] for row in (*NATIVE, *(CSP if csp_available else ())))


def labels(csp_available):
    return tuple(row[1] for row in (*NATIVE, *(CSP if csp_available else ())))


def display(name, value):
    choices = FIELDS[name][-1]
    if choices == ('0', '1'):
        return 'On' if value == '1' else 'Off'
    if name in ('msaa', 'anisotropic'):
        return 'Off' if value == ('1' if name == 'msaa' else '0') else value+'x'
    if name in ('shadow_resolution', 'reflection_resolution') or name.endswith('_resolution2'):
        return 'Off' if value == ('-1' if name == 'shadow_resolution' else '0') else value+' px'
    if name == 'reflection_distance':
        return value+' m'
    if name == 'reflection_updates':
        return 'Static' if value == '0' else value+' faces/frame'
    if name in ('world_detail','post_quality'):
        return ('Minimum','Low','Medium','High','Very high','Maximum')[int(value)]
    if name == 'smoke':
        return ('Off','Minimum','Low','Medium','High','Maximum')[int(value)]
    if name in ('glare','depth_of_field'):
        return ('Off','Low','Medium','High','Very high','Maximum')[int(value)]
    if name.endswith('_distance_mult') or name.endswith('_scale_scale'):
        return str(round(float(value)*100))+'%'
    return value


def rows(selection, csp_available):
    current = values(selection)
    return tuple(display(row[0], current[row[0]]) for row in (*NATIVE, *(CSP if csp_available else ())))


def change(selection, name, delta):
    current = values(selection)
    choices = FIELDS[name][-1]
    current[name] = choices[(choices.index(current[name])+delta)%len(choices)]
    selection.update(graphics_options=current, graphics_options_profile=selection['graphics_profile'],
                     graphics_options_version=VERSION)


def apply_native(video, selection):
    current = values(selection)
    for name, label, section, key, choices in NATIVE:
        if section not in video:
            video.add_section(section)
        video[section][key] = current[name]
    if current['reflection_resolution'] == '0':
        video['CUBEMAP'].update(FACES_PER_FRAME='0',FARPLANE='0')


def apply_csp(settings, selection):
    current = values(selection)
    for name, label, file, section, key, choices in CSP:
        settings.setdefault(file, {}).setdefault(section, {})[key] = current[name]


def preferences(selection):
    return {key: deepcopy(selection[key]) for key in PREFERENCE_KEYS if key in selection}


def with_current(selected, current):
    return dict(selected, **preferences(current))
