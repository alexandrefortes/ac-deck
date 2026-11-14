"""Contextual help for global Settings."""

HELP = {
    'graphics_profile': 'Choose a balance of quality and performance. Switching profiles replaces custom graphics values.',
    'resolution': 'Set the game output size. More pixels sharpen the image but make each frame harder to render.',
    'hud': 'Show FPS and frame time so you can see how smoothly the game runs.',
    'pp_filter': 'Choose the color and contrast filter used when post-processing is enabled.',
    'frame_limiter': 'Cap the game at 60 FPS or leave the limit to SteamOS or another tool.',
    'smart_shadows': 'Use CSP to distribute shadow detail around the car. This changes shadow coverage and rendering cost.',
    'shadow_distance_m': 'Set how far Smart Shadows reach. A longer range covers more of the track.',
    'msaa': 'Smooth the edges of cars and scenery. More samples improve edges and cost more GPU time.',
    'anisotropic': 'Keep road textures clear at shallow angles. Higher values sharpen distant surfaces.',
    'shadow_resolution': 'Set the size of shadow maps. Higher values give finer shadows at a higher rendering cost.',
    'world_detail': 'Control how much trackside scenery the game draws. Higher detail can cost performance.',
    'reflection_resolution': 'Set the detail of the base game reflection map. Larger maps use more GPU memory.',
    'reflection_distance': 'Set how far objects can appear in reflections. Longer distances add rendering work.',
    'reflection_updates': 'Set how many sides of the reflection map update each frame. More updates reduce lag.',
    'post_processing': 'Enable the color filter and screen effects that change the final image.',
    'post_quality': 'Set the quality of the post-processing effects. Higher settings take more GPU time.',
    'glare': 'Control the glow around bright lights. Higher settings make highlights bloom more.',
    'depth_of_field': 'Blur areas outside the camera focus. Higher settings increase the effect.',
    'heat_shimmer': 'Show the base game heat distortion effect around hot areas.',
    'sun_rays': 'Draw visible shafts of light from the sun when post-processing is enabled.',
    'fxaa': 'Smooth jagged edges in the base game image. This can soften small details.',
    'motion_blur': 'Set how strongly movement blurs the base game image. Zero leaves the image sharp.',
    'smoke': 'Set base game smoke quality. More detailed smoke can cost performance.',
    'smoke_mirrors': 'Include smoke in mirrors when they render. This adds a pass for smoke.',
    'csp_general_optimizations_cache_acs': 'Cache the game memory layout to help CSP load faster next time.',
    'csp_general_optimizations_gpu_optimize_meshes': 'Let CSP reorganize mesh data to reduce GPU work when drawing models.',
    'csp_general_optimizations_gpu_deduplicate_meshes': 'Share identical mesh data so it takes up less GPU memory.',
    'csp_general_optimizations_gpu_deduplicate_textures': 'Share identical textures so duplicates take up less GPU memory.',
    'csp_general_optimizations_gpu_upgrade_textures': 'Convert textures to reduce GPU memory use or loading time. The game can take more disk space.',
    'csp_general_optimizations_gpu_bc7_cache': 'Keep compressed BC7 textures on disk to reuse them on later loads.',
    'csp_general_optimizations_gpu_query_based_mapping': 'Use GPU queries to coordinate buffer access. It changes how CSP waits for the GPU.',
    'csp_graphics_adjustments_basic_force_fxaa': 'Apply FXAA through CSP to smooth edges. The image may look softer.',
    'csp_graphics_adjustments_antialiasing_mode': 'Choose the CSP filter for jagged edges. Modes trade sharpness for smoother edges.',
    'csp_graphics_adjustments_antialiasing_msaa_custom_resolve': 'Let CSP combine MSAA samples when building the final image. This changes edge smoothing.',
    'csp_graphics_adjustments_antialiasing_msaa_custom_kernel': 'Use CSP sample weights for MSAA resolve. This changes edge sharpness and blending.',
    'csp_graphics_adjustments_fsr_active': 'Use FSR to upscale a smaller rendered image. A lower render scale can improve frame rate.',
    'csp_graphics_adjustments_render_scale_scale': 'Set the size of the image before upscaling. Lower values save GPU work but lose detail.',
    'csp_graphics_adjustments_lods_cockpit_lr_fix': 'Keep other cars on simpler cockpit models in first-person views to avoid visible detail changes.',
    'csp_graphics_adjustments_lods_driver_lr_fix': 'Draw simpler driver models for other cars in first-person views to save rendering work.',
    'csp_graphics_adjustments_lods_cars_distance_mult': 'Set how far cars keep detailed models. Higher values keep more detail farther away.',
    'csp_graphics_adjustments_lods_track_distance_mult': 'Set how far track objects keep detailed models. Higher values draw more detail at distance.',
    'csp_graphics_adjustments_lods_trees_distance_mult': 'Set how far trees keep detailed models. Higher values preserve foliage detail farther away.',
    'csp_graphics_adjustments_lods_force_lod_b': 'Use the simpler LOD B car model where available. This reduces model detail and can save GPU work.',
    'csp_graphics_adjustments_lods_treat_track_cameras_the_same': 'Use the same model detail rules in track cameras as in driving views.',
    'csp_graphics_adjustments_lods_fallback_lods': 'Let CSP use fallback models when content lacks its own detail levels.',
    'csp_graphics_adjustments_lods_lodless_limit': 'Set how many cars can lack lower detail models before CSP uses fallback models.',
    'csp_graphics_adjustments_lods_hide_distant_drivers': 'Hide driver models in distant cars to reduce the amount of geometry drawn.',
    'csp_graphics_adjustments_lods_hide_wheels_for_interior_view': 'Skip drawing wheels from interior views. This reduces geometry in the cockpit view.',
    'csp_graphics_adjustments_lods_skip_loading_first_lod_for_other_cars': 'Skip the most detailed model for other cars to save loading time and memory.',
    'csp_graphics_adjustments_lods_limit_visible_cars': 'Let CSP limit the cars it draws to reduce rendering work in dense fields.',
    'csp_smart_shadows_basic_automatic_splits': 'Let Smart Shadows choose where near and far shadow detail changes.',
    'csp_smart_shadows_custom_shadow_matrices_fourth_cascade': 'Add a fourth shadow detail range. This can improve distant coverage at extra cost.',
    'csp_reflections_fx_main_cubemap_resolution2': 'Set the detail of the CSP reflection map. Higher values use more GPU memory.',
    'csp_reflections_fx_main_cubemap_reproject_partial': 'Reuse parts of previous reflection frames to smooth partial updates.',
    'csp_extra_fx_basic_enabled': 'Enable the CSP effects pipeline. Its additional screen effects can increase GPU work.',
    'csp_extra_fx_motion_blur_enabled': 'Blur movement using CSP Extra FX. It needs the Extra FX pipeline.',
    'csp_grass_fx_basic_quality': 'Set Grass FX detail. Higher settings can increase GPU work around grassy tracks.',
    'csp_grass_fx_basic_enabled': 'Draw CSP grass on supported tracks. The extra vegetation takes GPU time.',
    'csp_grass_fx_rendering_cast_shadows': 'Let CSP grass cast shadows. This adds detail and shadow work.',
    'csp_grass_fx_rendering_extrafx_pass': 'Include CSP grass in the Extra FX pass when enabled. This adds rendering work.',
    'csp_grass_fx_rendering_smoother_blending': 'Blend grass into surrounding surfaces more smoothly. It takes more rendering work.',
    'csp_particles_fx_smoke_use_culling': 'Skip smoke particles outside the visible area to save GPU work.',
    'csp_particles_fx_smoke_show_in_mirrors': 'Draw CSP smoke in mirrors when mirrors are active. It adds work to their view.',
    'csp_particles_fx_smoke_cast_shadows': 'Let CSP smoke cast shadows. This adds depth and extra rendering work.',
    'csp_particles_fx_smoke_cast_ambient_shadows': 'Let CSP smoke contribute to ambient shading. Dense smoke gains depth at a cost.',
    'csp_particles_fx_smoke_use_downscaling': 'Render CSP smoke at reduced resolution to save GPU time. Edges may look softer.',
    'csp_particles_fx_smoke_simplified_shading': 'Use simpler lighting for smoke to cut GPU work, with less shading detail.',
    'csp_particles_fx_fireworks_enabled': 'Render CSP fireworks at tracks that use them. The particles add visual effects and GPU work.',
    'csp_particles_fx_ac_particles_reworked_heat_shimmer': 'Use the CSP version of heat distortion instead of the base game effect.',
    'csp_lighting_fx_shadows_enabled': 'Let CSP lights cast shadows. This adds depth at night and can cost performance.',
    'csp_lighting_fx_shadows_high_quality_headlight_shadows': 'Use finer headlight shadows. Night racing can take more GPU time.',
    'csp_lighting_fx_performance_enable_reflection_light': 'Include CSP light sources in reflections. This adds lit detail and rendering work.',
    'csp_lighting_fx_performance_cars_with_lights': 'Limit how many cars CSP renders with lights. Higher values add lighting work.',
    'csp_weather_fx_basic_enabled': 'Use CSP sky and lighting for the selected weather. It changes the look of the session.',
    'csp_weather_fx_performance_additional_effects': 'Render optional Weather FX effects. These add atmosphere and GPU work.',
    'csp_weather_fx_performance_detailed_cloud_shadows': 'Draw more detailed cloud shadows on the track. This adds shading work.',
    'csp_weather_fx_performance_slow_reflections_update': 'Update weather reflections less often to save work. Changes may appear later.',
    'csp_weather_fx_performance_high_quality_stars': 'Draw the night sky stars in higher quality at extra GPU cost.',
    'csp_weather_fx_performance_extra_clouds_fidelity': 'Draw clouds with more detail. It takes more GPU time to render the sky.',
    'csp_weather_fx_pp_tweaks_full_resolution': 'Run weather post effects at full resolution. It keeps detail at a higher GPU cost.',
    'csp_smart_mirror_performance_skip_frames': 'Update Smart Mirrors less often when active. More skips save work but look less smooth.',
    'chase_camera': 'Choose the style for both chase views. Speed Chase widens the view as speed rises.',
    'chase_look': 'Use the right stick to look around in supported chase cameras, or disable that input.',
    'chase_deadzone': 'Ignore small right stick movement when looking around. Higher values reduce accidental movement.',
    'chase_exponent': 'Set how gently chase look responds near the stick center. Higher values soften small inputs.',
    'chase_distance': 'Set how far the chase camera sits behind the car in supported styles.',
    'chase_height': 'Set camera height. Speed Chase measures from the car origin.',
    'chase_pitch': 'Tilt the supported chase camera up or down to change what is visible around the car.',
    'chase_fov': 'Set the width of the adjustable chase view. Speed Chase and BACC adjust it while driving. GT5 uses a fixed angle.',
    'control_mode': 'Choose native gamepad steering or enable CSP assistance through the selected Gamepad FX script.',
    'steer_speed_pct': 'Set how quickly steering reacts to stick input. Higher values allow faster steering movement.',
    'steer_filter_pct': 'Smooth sudden changes in steering input. More filtering can make response feel slower.',
    'speed_sensitivity_pct': 'Reduce steering response at high speed. Higher values make fast corners less twitchy.',
    'steer_deadzone_pct': 'Ignore small steering stick movements. Higher values reduce drift but lose fine input.',
    'rumble_pct': 'Set the strength of the base game vibration. CSP driving haptics has separate gains.',
    'steer_gamma_tenths': 'Set the steering response curve. Higher gamma softens input near the stick center.',
    'hide_driver_arms': 'Hide the driver arms in cockpit views to keep the wheel and instruments clear.',
    'virtual_steer_degrees': 'Limit the cockpit wheel animation angle. It changes the display of steering input.',
    'gear_up_button': 'Choose which controller button shifts up. Selecting a used button swaps bindings.',
    'gear_down_button': 'Choose which controller button shifts down. Selecting a used button swaps bindings.',
    'handbrake_button': 'Choose which controller button applies the handbrake. Selecting a used button swaps bindings.',
    'change_view_button': 'Choose which controller button cycles camera views. Selecting a used button swaps bindings.',
    'car_damage_pct': 'Set how much damage the game applies. Lower values make impacts less costly.',
    'abs_mode': 'Set anti-lock braking. Factory follows the car setup, On enables it, and Off disables it.',
    'traction_control': 'Set wheelspin assistance. Factory follows the car setup, On enables it, and Off disables it.',
    'stability_control': 'Set how strongly the game helps correct a slide. Zero leaves the correction off.',
    'ghost': 'Show and record a reference car in Hotlap when enabled. Turning it off disables ghosts in all modes.',
    'automatic_headlights': 'Let CSP switch the headlights as light levels change.',
    'automatic_wipers': 'Let CSP control the wipers when the session calls for them.',
    'pause_unfocused': 'Pause the game when its window loses focus, such as when switching back to Steam.',
    'simple_ui': 'Use a simpler CSP race interface with fewer elements on screen.',
    'csp_ui_scale': 'Change the size of CSP interface elements. Larger values take more screen space.',
    'race_taskbar': 'Show the app bar in the race so you can open installed CSP apps.',
    'driving_haptics': 'Use driving telemetry for controller vibration. This affects feedback only.',
    'haptics_left_pct': 'Set vibration strength for the left driving haptics channel. Zero mutes it.',
    'haptics_right_pct': 'Set vibration strength for the right driving haptics channel. Zero mutes it.',
    'gamepad_script': 'Choose an installed CSP script for assisted steering. Each script handles the stick differently.',
    'aga_enabled': 'Set the Advanced Gamepad Assist switch at the next session start.',
    'proximity_alert': 'Show a screen edge cue for nearby cars. It helps you see cars outside the current view.',
    'proximity_lateral_range': 'Set how far to either side the proximity cue detects cars. A larger range shows cues sooner.',
    'proximity_rear_range': 'Set how far behind the car the proximity cue detects traffic. A larger range shows cues sooner.',
    'automatic': 'Let the game shift gears for you. Turn it off to shift with your controller buttons.',
    'automatic_clutch': 'Let the game operate the clutch during gear changes.',
    'api-key': 'Set the local OpenAI key used for AI race generation and enabled remote dictation.',
    'effort': 'Set how much reasoning AI generation can use. Higher effort may take longer and cost more.',
    'usage:car': 'Limit confirmed races per car before it rotates out for variety. Pins bypass the limit.',
    'usage:track': 'Limit confirmed races per layout before it rotates out for variety. Pins bypass the limit.',
    'ai-options': 'View the base AI instructions and manage your saved prompt and dictation.',
    'ai-reset-usage': 'Start fresh car and track variety cycles. Your race history and saved settings stay.',
    'haptics_left': 'Play a short sample at the saved left vibration strength.',
    'haptics_right': 'Play a short sample at the saved right vibration strength.',
    'usage-options': 'Set how often a car or layout may repeat before the AI generator rotates it out.',
    'main-prompt': 'Read the base instructions that guide AI race generation.',
    'custom-prompt': 'Save preferences for AI race generation. A temporary prompt takes priority while it has text.',
    'voice-input': 'Choose the microphone for dictation. System default follows the active audio device.',
    'dictate': 'Record spoken preferences. Press Stop to send the recording for transcription.',
    'voice-enable': 'Allow paid OpenAI transcription using the saved key. Audio is sent when you press Stop.',
    'prompt-save': 'Save the prompt and dictation preferences for later AI generation.',
    'prompt-cancel': 'Close the prompt editor and discard its unsaved changes.',
    'key:field': 'Type or paste your OpenAI key. It stays masked and is stored locally when saved.',
    'key:save': 'Save the key for OpenAI requests. Saving an empty field removes the stored key.',
    'key:cancel': 'Close the key editor and keep the previous key.',
    'category:graphics': 'Change display, performance, and visual effects for all modes.',
    'category:controls': 'Adjust steering, button bindings, and controller vibration.',
    'category:gamepad': 'Choose and configure the CSP gamepad steering script.',
    'category:assists': 'Adjust driving aids such as automatic shifting, ABS, and traction control.',
    'category:camera': 'Change cockpit visibility and the chase camera.',
    'category:interface': 'Choose the HUD, app bar, ghost, and proximity cues used during a race.',
    'category:opponents': 'See the active CSP driving behavior for computer-controlled opponents.',
    'category:ai': 'Configure OpenAI generation, prompts, dictation, and variety limits.',
}


def route(menu):
    if (getattr(menu, 'view', None) != 'settings' or menu.quit_confirmation
            or getattr(menu, 'session_running', False) or menu.overlay not in (None, 'ai-settings', 'usage-options')):
        return None
    return (menu.category, getattr(menu, 'settings_page', 0), menu.overlay, menu.key_dialog,
            bool(menu.editing), bool(menu.ai_panel and menu.ai_panel['editing']))


def explanation(menu, item):
    identity = item['id']
    binding = item.get('binding')
    if binding:
        tab, index = binding
        if tab == 4:
            identity = menu.graphics_keys[index].removeprefix('gfx:')
        elif tab == 5:
            identity = menu.control_keys[index]
        elif tab == 3:
            identity = {7: 'automatic', 9: 'automatic_clutch'}.get(index)
    elif identity == 'ai-effort':
        identity = 'effort'
    return HELP.get(identity)


class SettingsHelp:
    def __init__(self):
        self.items = ()
        self.clear()

    def clear(self):
        self.pointer = self.target = None

    def hit(self, point):
        if not point:
            return None
        x, y = point
        return next((item for item in reversed(self.items) if
                     item['x'] <= x < item['x'] + item['w'] and item['y'] <= y < item['y'] + item['h']), None)

    def motion(self, point):
        if self.pointer is None or self.hit(self.pointer) is not self.hit(point):
            self.target = None
        self.pointer = point

    def navigation(self):
        if self.pointer is not None:
            self.clear()

    def update(self, menu, items, now):
        context = route(menu)
        if context is None:
            self.items = ()
            self.clear()
            return None
        self.items = tuple(item for item in items if not item.get('disabled') and explanation(menu, item))
        focus = 'key:' + ('field', 'save', 'cancel')[menu.key_focus] if menu.key_dialog else menu.focus_id
        item = (self.hit(self.pointer) if self.pointer is not None else
                next((item for item in self.items if item['id'] == focus), None))
        target = (context, item['id']) if item is not None else None
        if target != self.target:
            self.target, self.started = target, now
        if target is not None and now - self.started >= 1:
            return item, explanation(menu, item)
        return None
