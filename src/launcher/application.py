"""Conteúdo instalado completo e menu por controle, pela entrada Steam do jogo."""
import argparse
from functools import partial
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import threading
import time
import uuid

ROOT=(Path(sys.executable).resolve().parent if getattr(sys,'frozen',False)
      else Path(__file__).resolve().parents[2])
from . import package_setup, steam
from . import file_io as safe
from src.launcher import content, csp, installed, diagnostics, font_support, graphics, chase_camera, hud_cleanup, gt5_camera, bacc_camera, event_synthetizer, player_history, results, campaigns
from src.launcher import driving_haptics, driving_haptics_app, gamepad_fx, current_settings, session_settings, session_process, history_retention, proximity_alert, proximity_preferences
from src.launcher import rogue_goal_hud, rogue_toasty_session, rogue_toasty_install, rogue_victory_music


def _rogue_selection(game, path, selection):
    """Reabre o desafio persistido; o marcador da interface não é uma autorização."""
    from src.launcher import rogue, rogue_generator
    chosen=dict(selection)
    marker=chosen.pop('rogue', None)
    if (not isinstance(marker, dict) or set(marker)!={'run_id','challenge_id'}
            or not all(isinstance(value,str) and value for value in marker.values())
            or event_synthetizer.MARKER in chosen):
        raise ValueError('Invalid Rogue session identity')
    store=rogue.Store(path)
    run=store.state.get('run')
    challenge=run.get('challenge') if isinstance(run,dict) else None
    if (not run or run.get('status')!='active' or not isinstance(challenge,dict)
            or marker['run_id']!=run.get('id')
            or marker['challenge_id']!=challenge.get('challenge_id')):
        raise ValueError('This Rogue challenge is no longer active')
    if not session_settings.same(chosen,challenge['selection']):
        raise ValueError('Rogue race settings differ from the fixed challenge')
    catalog=rogue_generator.validate(game,challenge)
    return store,chosen,catalog


def _finish_rogue_attempt(active, record, *, trace=None, on_win=None):
    """O recibo do núcleo evita reaplicar XP mesmo se a finalização for repetida."""
    if active is None:return ''
    store,attempt=active
    try:
        update=store.finish_attempt(attempt['id'],record)
        if trace:trace('rogue_result',outcome=update['status'])
        if on_win is not None and update['status']=='won':
            on_win(attempt['id'])
        return ' Rogue: '+update['message']
    except (OSError,ValueError,RuntimeError):
        if trace:trace('rogue_result',outcome='unavailable')
        return ' Rogue progress could not be confirmed; the saved run is kept.'


def _recover_rogue_attempt(state, *, trace=None):
    """Recupera só o resultado já vinculado à tentativa interrompida desta run."""
    path=Path(state)/'rogue.json'
    if not path.exists():return
    from src.launcher import rogue
    try:
        store=rogue.Store(path)
        run=store.state.get('run')
        pending=run.get('pending_attempt') if run else None
        if pending is None:return
        attempt=run['attempts'][pending]
        record_path=Path(state)/'sessions'/attempt['session_id']/'result.json'
        record=results._json(results._read(record_path)[0])
        if not isinstance(record,dict):raise ValueError('Invalid pending Rogue result')
        if record.get('status')=='pending':return
        _finish_rogue_attempt((store,attempt),record,trace=trace)
    except FileNotFoundError:
        pass
    except (OSError,ValueError,RuntimeError):
        if trace:trace('rogue_result',outcome='recovery_unavailable')


def environment(original,package,*,hud=True,game=None,frame_limiter=None):
    env=steam.steam_environment(original,package)
    if game is not None:
        env['STEAM_COMPAT_INSTALL_PATH']=str(game)
    # O bootloader inclui suas bibliotecas no ambiente. Proton recebe o valor
    # que a Steam forneceu antes disso, sem herdar o Python/SDL2 do launcher.
    if getattr(sys,'frozen',False):
        if 'LD_LIBRARY_PATH_ORIG' in env:
            env['LD_LIBRARY_PATH']=env['LD_LIBRARY_PATH_ORIG']
        else:
            env.pop('LD_LIBRARY_PATH',None)
    # HUD já fornecido pelo DXVK/Proton. Apenas no processo filho desta sessão.
    env['DXVK_HUD']='fps,frametimes' if hud else '0'
    if frame_limiter=='game_60':
        # O limite do jogo é o principal. Não acumular o limite herdado DXVK.
        env.pop('DXVK_FRAME_RATE',None)
    env['WINEDLLOVERRIDES']=csp.wine_overrides(env.get('WINEDLLOVERRIDES',''),True)
    env.setdefault('WINE_DBGHELP_OLD_PDB','1')
    return env


def prepare(source,batch,*,project_root=ROOT):
    def progress(stage,index,total):
        print(f'{stage}: {index}/{total}',flush=True)
    package=package_setup.prepare(source,batch,project_root=project_root,
                                full_content=True,progress=progress)
    catalog=content.scan(package/'game')
    safe.write_new_json(package/'catalog.json',catalog)
    print(f"Catálogo: {len(catalog['cars'])} carros, {len(catalog['tracks'])} pistas/layouts, "
          f"{len(catalog['events'])} eventos.",flush=True)
    return package


def _initialize_prefix(package,game,source,command,child_env,*,trace=None):
    """Create missing Proton user directories without starting a game."""
    argv=steam.prefix_command(command,source)
    child_env=dict(child_env,WINEDLLOVERRIDES=csp.wine_overrides(child_env.get('WINEDLLOVERRIDES',''),False))
    stopped=False
    def stop(number,frame):
        nonlocal stopped
        stopped=True
    previous={number:signal.signal(number,stop) for number in (signal.SIGTERM,signal.SIGINT)}
    try:
        log_path=package/'launcher'/('prefix-init-'+uuid.uuid4().hex+'.log')
        safe.check_components(log_path)
        if trace:trace('proton_prefix_initializing')
        before=session_process.snapshot()
        with log_path.open('xb') as log:
            process=subprocess.Popen(argv,cwd=game,env=child_env,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            owned=session_process.Session(process,before,trace=trace)
            try:
                while (code:=owned.poll()) is None:
                    if stopped:owned.request_stop()
                    time.sleep(0.05)
            except BaseException:
                owned.request_stop()
                while owned.poll() is None:time.sleep(0.05)
                raise
        if stopped:
            raise InterruptedError('Proton initialization stopped; existing Steam data was preserved')
        if code!=0:
            raise ValueError('Proton could not prepare its user folders. Check the selected Steam compatibility tool and try again.')
        if trace:trace('proton_prefix_initialized')
    finally:
        for number,handler in previous.items():signal.signal(number,handler)


def launch(package,command,*,csp_payload=None,csp_config=None,game_config=None,trace=None,font_payload=None):
    if sys.platform!='linux':
        raise ValueError('Abra esta entrada pela Steam no Linux')
    if csp_payload is None:
        raise ValueError('CSP payload is required for all graphics profiles')
    import fcntl
    from src.launcher.window import run
    from src.launcher.native_menu import NativeMenu
    package=safe.source_root(package)
    record=safe.read_json(package/'prepared.json')
    if record.get('status')!='prepared' or record.get('content_scope')!='installed_content':
        raise ValueError('Use um pacote completo preparado pelo jogo_deck.py')
    game=installed.game_path(package,record)
    direct=record.get('game_mode')=='installed'
    base_cfg=package/'cfg' if direct else None
    argv=steam.steam_command(command,record['source'],package)
    argv[argv.index(str(package/'game/acs.exe'))]=str(game/'acs.exe')
    initial_env=environment(os.environ,package,game=game)
    expected=next(p['sha256'] for p in record['selection'] if p['relative_path']=='acs.exe')
    actual,_=safe.hash_reference_file(game/'acs.exe')
    if actual!=expected:
        raise ValueError('Executável declarado mudou')
    state=package/'launcher'
    state.mkdir(exist_ok=True)
    safe.check_components(state)
    lock=state/'active.lock'
    safe.check_components(lock)
    with lock.open('a+b') as stream, session_process.Owner():
        safe.require_reference(os.fstat(stream.fileno()),lock)
        try:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Este pacote já tem um menu em execução') from error
        if direct:
            try:
                cfg=installed.config_path(game,os.environ,game_config)
            except installed.DocumentsMissing:
                _initialize_prefix(package,game,record['source'],command,initial_env,trace=trace)
                try:
                    cfg=installed.config_path(game,os.environ,game_config)
                except installed.DocumentsMissing as error:
                    raise ValueError('Proton did not create its Documents folder. Check the selected Steam compatibility tool and try again.') from error
        else:
            cfg=game/'state/Assetto Corsa/cfg'
        hud_cleanup.remove_managed(package,game)
        history_policy=history_retention.maintain_locked(package)
        if trace:trace('history_retention',**history_policy)
        roots=csp.config_roots(game,os.environ,csp_config,native_cfg=cfg)
        receipt=csp.install(csp_payload,package)
        font_bundle=font_payload if font_payload is not None else ROOT/'csp-fonts'
        if font_payload is not None or (font_bundle/'manifest.json').is_file():
            fonts=font_support.install(font_bundle,package,os.environ)
            if trace:
                trace('csp_fonts_ready',managed_files=sum(row['owned'] for row in fonts['files']))
        print('CSP '+receipt['version']+' pronto no jogo declarado; controle Gamepad Force disponível.',flush=True)
        catalog=installed.load_catalog(package,game,refresh=True)
        selection={}
        saved=state/'selection.json'
        if saved.is_file():
            selection=safe.read_json(saved)
        else:
            if any(p['id']=='abarth500' for p in catalog['cars']):
                selection['car']='abarth500'
            if any(p['key']=='magione|' for p in catalog['tracks']):
                selection.update(track='magione',layout='')
            if '3_clear' in catalog['weather']:
                selection['weather']='3_clear'
        selection=graphics.normalize(selection,csp_available=True)
        selection.update(proximity_preferences.read_edits(roots, selection.get('proximity_handled_session')))
        _recover_rogue_attempt(state,trace=trace)
        active_result=None
        active_campaign=None
        campaign_unavailable=False
        active_rogue=None
        active_process=None
        active_haptics=None
        active_toasty=None
        active_rogue_hud=None
        victory_music=rogue_victory_music.Playback(ROOT/'assets/rogue-victory')
        active_proximity=None
        pending_proximity={}
        lifecycle_lock=threading.RLock()
        last_selection=dict(selection)
        def remember(chosen):
            nonlocal last_selection
            last_selection=dict(chosen)
        def stop_session():
            # The close worker cannot race config preparation or finalization.
            if not lifecycle_lock.acquire(blocking=False):return
            try:
                if active_process is not None:
                    stop_rogue_hud()
                    active_process.request_stop()
            finally:lifecycle_lock.release()
        def stalled_close():
            if not lifecycle_lock.acquire(blocking=False):return False
            try:
                if active_process is not None:
                    code=active_process.poll()
                    if code is None:return False
                    finish(code)
                save(last_selection)
                if trace:
                    trace('launcher_close_fallback',reason='native_ui_did_not_return')
                    trace('launcher_exited',exit_code=0,fallback=True)
                return True
            finally:lifecycle_lock.release()
        def stop_haptics():
            nonlocal active_haptics
            current,active_haptics=active_haptics,None
            if current is not None:
                if trace:trace('driving_haptics_finished',packets=current.count,status=current.status)
                try:current.close()
                except OSError:pass
        def stop_toasty():
            nonlocal active_toasty
            current,active_toasty=active_toasty,None
            if current is not None:
                try:
                    current.close()
                    if trace:trace('rogue_toasty_finished')
                except (OSError,ValueError,RuntimeError):
                    if trace:trace('rogue_toasty_unavailable',reason='close_failed')
        def stop_rogue_hud():
            nonlocal active_rogue_hud
            current,active_rogue_hud=active_rogue_hud,None
            if current is not None:
                victory_music.stop()
                try:current.close()
                except OSError:
                    if trace:trace('rogue_goal_hud_unavailable',reason='close_failed')
        def rogue_hud_audio(action):
            if action=='win' and active_process is not None:victory_music.play()
            elif action=='restart':victory_music.stop()
        def tick_haptics(window):
            with lifecycle_lock:return tick_session(window)
        def tick_session(window):
            # Toasty is independent from rumble and never mutates sporting results.
            if active_process is None and active_toasty is not None:
                stop_toasty()
            if active_toasty is not None:
                try:active_toasty.tick()
                except (OSError,ValueError,RuntimeError):
                    stop_toasty()
                    if trace:trace('rogue_toasty_unavailable',reason='runtime_error')
            if active_process is not None and active_rogue_hud is not None:
                try:active_rogue_hud.tick()
                except OSError:
                    stop_rogue_hud()
                    if trace:trace('rogue_goal_hud_unavailable',reason='runtime_error')
            if active_process is None and active_haptics is not None:
                stop_haptics()
            if active_haptics is not None:
                try:active_haptics.tick(window)
                except (OSError,ValueError,RuntimeError):
                    window.driving_rumble(0,0)
                    stop_haptics()
                    if trace:trace('driving_haptics_unavailable',reason='runtime_error')
            return active_haptics is not None
        def finish(code):
            with lifecycle_lock:return finish_locked(code)
        def finish_locked(code):
            nonlocal active_result,active_process,active_campaign,campaign_unavailable,active_rogue,active_proximity
            stop_haptics()
            stop_toasty()
            stop_rogue_hud()
            if active_proximity is not None:
                edits=proximity_preferences.read_edits(roots, last_selection.get('proximity_handled_session'))
                if edits.get('proximity_handled_session') == active_proximity:
                    last_selection.update(edits)
                    pending_proximity.update(edits)
                    try:
                        save(last_selection)
                    except (OSError,ValueError,RuntimeError):
                        if trace:trace('proximity_settings_save_failed')
                active_proximity=None
            collector,active_result=active_result,None
            campaign,active_campaign=active_campaign,None
            rogue_attempt,active_rogue=active_rogue,None
            active_process=None
            if collector is None:
                note=_finish_rogue_attempt(rogue_attempt,dict(schema_version=1,
                    session_id=rogue_attempt[1].get('session_id') if rogue_attempt else None,
                    status='unavailable',reason='capture_preparation_failed'),trace=trace)
                return 'Session ended. Result collection unavailable.'+note
            try:
                record=collector.finish(code)
                if trace:
                    trace('session_result',status=record['status'],reason=record['reason'])
                campaign_note=' Native campaign progress unavailable; original file kept.' if campaign_unavailable else ''
                campaign_unavailable=False
                if campaign is not None:
                    try:
                        update=campaign.finish(record)
                        if update and update['status']=='saved':campaign_note=' Campaign saved: '+update['result']+'.'
                        elif update:campaign_note=' '+{
                            'completion_not_confirmed':'Campaign progress kept: completion was not confirmed.',
                            'unsupported_event_numbering':'Campaign progress kept: this campaign uses unsupported event numbering.',
                            'event_not_available':'Campaign progress kept: this event is unavailable.',
                            'unsupported_championship_result':'Campaign progress kept: this championship result is unsupported.',
                            'championship_round_already_recorded':'This championship round was already recorded.',
                            'unsupported_event_conditions':'Campaign progress kept: this event uses an unsupported rule.',
                            'previous_best_preserved':'Previous campaign result kept.',
                            'native_progress_changed_during_session':'Campaign progress changed in another launcher; its changes were kept.',
                        }.get(update['reason'],'Campaign progress kept.')
                    except (OSError,ValueError,RuntimeError):
                        campaign_note=' Native campaign progress could not be saved; original progress kept.'
                rogue_note=_finish_rogue_attempt(rogue_attempt,record,trace=trace,on_win=victory_music.arm_result)
                return results.message(record)+campaign_note+rogue_note
            except (OSError,ValueError,RuntimeError):
                rogue_note=_finish_rogue_attempt(rogue_attempt,dict(schema_version=1,
                    session_id=collector.history.name,status='unavailable',reason='history_write_failed'),trace=trace)
                if trace:
                    trace('session_result',status='unavailable',reason='history_write_failed')
                return 'Session ended. Could not preserve the result; check local storage.'+rogue_note
        def save(chosen):
            chosen=graphics.normalize(chosen,csp_available=True)
            safe.check_components(saved)
            if saved.exists():
                safe.require_reference(saved.lstat(),saved)
            temporary=state/('selection-'+uuid.uuid4().hex+'.json')
            safe.write_new_json(temporary,chosen)
            temporary.replace(saved)
        def start(chosen):
            with lifecycle_lock:
                try:return start_locked(chosen)
                except BaseException:
                    if active_process is None:stop_rogue_hud()
                    raise
        def start_locked(chosen):
            nonlocal catalog,active_result,active_process,active_haptics,active_campaign,campaign_unavailable,active_rogue,active_toasty,active_proximity
            nonlocal active_rogue_hud
            # O loop da janela também bloqueia a ação. Esta guarda preserva a
            # sessão e seu coletor caso outro chamador tente iniciar de novo.
            if active_process is not None:
                raise ValueError('Finish the current session before starting another.')
            victory_music.stop()
            victory_music.arm_result(None)
            chosen=dict(chosen)
            rogue_store=None
            rogue_marker=chosen.get('rogue')
            proposal=chosen.pop(event_synthetizer.MARKER,None)
            if 'rogue' in chosen:
                if proposal is not None:
                    raise ValueError('A session cannot combine Rogue and Race Synthetizer proposals')
                rogue_store,chosen,catalog=_rogue_selection(game,state/'rogue.json',chosen)
            elif proposal is not None:
                catalog=event_synthetizer.validate(game,proposal)
                if not session_settings.same(chosen,proposal['selection']):
                    raise ValueError('Generated event differs from validated proposal')
            else:
                # A geração pode atualizar o catálogo visto no menu. Revalidar
                # também a escolha manual, sem alterar seus valores salvos.
                catalog=content.scan(game)
            chosen=graphics.normalize(chosen,csp_available=True)
            driving_haptics.validate(chosen)
            if proximity_preferences.read_edits(
                    roots, chosen.get('proximity_handled_session'), strict=True):
                raise ValueError('Proximity app settings changed while the launcher was open; restart the launcher to reconcile them')
            history=state/'sessions'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
            style='base'
            proximity_session=uuid.uuid4().hex
            csp_plan=csp.plan_settings(game,chosen,roots,proximity_session=proximity_session)
            if (chosen.get('control_mode', 'assisted') == 'assisted'
                    and chosen.get('gamepad_script') == gamepad_fx.AGA and gamepad_fx.supported(game)):
                gamepad_fx.install(package)
            try:
                proximity_alert.install(package)
            except (OSError, ValueError, RuntimeError):
                if trace:trace('proximity_alert_unavailable',reason='installation_failed')
            camera_receipt=None
            if chosen.get('chase_camera')==chase_camera.SCRIPT:
                camera_receipt=chase_camera.install(package)
            elif chosen.get('chase_camera')==chase_camera.SPEED:
                camera_receipt=chase_camera.install(package, chase_camera.SPEED)
            elif chosen.get('chase_camera')==chase_camera.GT5:
                camera_receipt=gt5_camera.install(ROOT/'mods'/gt5_camera.ARCHIVE_NAME,package)
            elif chosen.get('chase_camera') in chase_camera.BACC:
                mode=chosen['chase_camera']
                camera_receipt=bacc_camera.install(ROOT/'mods'/bacc_camera.SPECS[mode]['archive'],package,mode)
            history_retention.maintain_locked(package,reserve=1)
            if rogue_store is not None:
                try:
                    rogue_goal_hud.install(game)
                    active_rogue_hud=rogue_goal_hud.Session(history.name,on_audio=rogue_hud_audio)
                except (OSError,ValueError,RuntimeError):
                    if trace:trace('rogue_goal_hud_unavailable',reason='preparation_failed')
            hashes=content.write_session(game,catalog,chosen,history,csp=True,
                cfg=cfg,base_cfg=base_cfg,xinput=direct,
                rogue_hud=active_rogue_hud.config if active_rogue_hud is not None else None)
            csp_files=csp.write_settings(csp_plan,history)
            haptics_ready=False
            if chosen.get('driving_haptics',driving_haptics.DEFAULTS['driving_haptics']):
                try:
                    driving_haptics_app.install(package)
                    endpoint=state/'driving-haptics-endpoint.txt'
                    safe.check_components(endpoint)
                    if endpoint.exists():safe.require_reference(endpoint.lstat(),endpoint)
                    active_haptics=driving_haptics.Session(endpoint,chosen)
                    haptics_ready=True
                except (OSError,ValueError,RuntimeError):
                    stop_haptics()
                    if trace:trace('driving_haptics_unavailable',reason='preparation_failed')
            child_env=environment(os.environ,package,hud=chosen['hud'],game=game,
                                  frame_limiter=chosen.get('frame_limiter'))
            pp=content.read_ini(history/'video.ini')
            safe.write_new_json(history/'session.json',dict(selection=chosen,config_sha256=hashes,
                hud_requested=chosen['hud'],benchmark_required=False,csp_enabled=True,
                csp_available=True,csp_version=csp.VERSION,csp_config=csp_files,
                csp_weather_style=style,
                graphics_preset_revision=graphics.PRESET_REVISION,
                frame_limiter=chosen.get('frame_limiter'),dxvk_frame_rate=child_env.get('DXVK_FRAME_RATE'),
                dwrite_override=child_env.get('WINEDLLOVERRIDES'),
                chase_camera=chosen.get('chase_camera','original'),
                chase_camera_receipt=camera_receipt,
                driving_haptics=dict(prepared=haptics_ready,scope='CSP telemetry and Steam Input virtual output',
                    left_pct=chosen.get('haptics_left_pct',50),right_pct=chosen.get('haptics_right_pct',50)),
                event_synthetizer=proposal,
                rogue=rogue_marker,
                player_history_sources=player_history.sources(cfg,package),
                old_pdb_requested=child_env.get('WINE_DBGHELP_OLD_PDB'),
                post_processing=dict(pp['POST_PROCESS']) if 'POST_PROCESS' in pp else {}))
            if proposal is None and rogue_store is None and not chosen.get('event'):
                save(chosen)
            try:
                active_result=results.Collector(cfg,history)
            except (OSError,ValueError,RuntimeError):
                active_result=None
                if trace:trace('session_result',status='unavailable',reason='capture_preparation_failed')
            active_campaign=None
            campaign_unavailable=False
            try:
                selected_event=next((event for event in catalog['events'] if event['id']==chosen.get('event')),None)
                if selected_event and selected_event.get('series'):
                    active_campaign=campaigns.Session(cfg,history,selected_event,catalog)
            except (OSError,ValueError,RuntimeError):
                campaign_unavailable=True
                if trace:trace('campaign_progress',status='unavailable',reason='native_progress_unreadable')
            try:
                if rogue_store is not None:
                    if active_result is None:
                        raise ValueError('Rogue requires result collection before starting the challenge')
                    attempt=rogue_store.begin_attempt(chosen,session_id=history.name)
                    active_rogue=(rogue_store,attempt)
                    safe.write_new_json(history/'rogue-attempt.json',dict(schema_version=1,
                        run_id=attempt['run_id'],challenge_id=attempt['challenge_id'],
                        attempt_id=attempt['id'],session_id=history.name))
                    if active_rogue_hud is not None:
                        try:active_rogue_hud.set_attempt(attempt)
                        except (KeyError,ValueError):
                            stop_rogue_hud()
                            if trace:trace('rogue_goal_hud_unavailable',reason='invalid_objective')
                    metadata=dict(run_id=attempt['run_id'],challenge_id=attempt['challenge_id'],
                                  attempt_id=attempt['id'],session_id=history.name)
                    try:
                        active_result.enable_finish_capture(game)
                    except (OSError, ValueError, RuntimeError):
                        if trace:trace('rogue_finish_capture',status='unavailable')
                    try:
                        toasty_receipt=rogue_toasty_install.install(package,asset_root=ROOT/'assets/rogue-toasty',session_id=history.name)
                        if toasty_receipt.get('toasty_ready') is True:
                            active_toasty=rogue_toasty_session.Session(package,metadata)
                            if trace:trace('rogue_toasty_ready')
                    except (OSError,ValueError,RuntimeError):
                        stop_toasty()
                        if trace:trace('rogue_toasty_unavailable',reason='preparation_failed')
                before=session_process.snapshot()
                with (history/'runtime.log').open('xb') as log:
                    process=subprocess.Popen(argv,cwd=game,
                        env=child_env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            except (OSError,ValueError,RuntimeError):
                stop_haptics()
                stop_toasty()
                failed_record=dict(schema_version=1,session_id=history.name,status='unavailable',reason='process_start_failed')
                if active_result is not None:
                    try:
                        failed_record=active_result.finish(None,start_failed=True)
                    except (OSError,ValueError,RuntimeError):
                        pass
                    active_result=None
                _finish_rogue_attempt(active_rogue,failed_record,trace=trace)
                active_rogue=None
                raise
            active_process=session_process.Session(process,before,trace=trace)
            if active_rogue_hud is not None:
                try:active_rogue_hud.start_native_score(game/'acs.exe',active_process,trace=trace)
                except (OSError,ValueError,RuntimeError):
                    if trace:trace('rogue_native_score_unavailable',reason='preparation_failed')
            active_proximity=proximity_session
            return active_process
        proton=next((v for v in command if Path(v).name=='proton'),None)
        def take_proximity():
            result=dict(pending_proximity)
            pending_proximity.clear()
            return result
        try:
            chosen=run(catalog,selection,start,proton=proton,csp=True,game=game,trace=trace,
                       synthesis_store=state/'event-synthetizer.json',on_exit=finish,menu_class=partial(NativeMenu,campaign_cfg=cfg,
                       current_provider=lambda: current_settings.read(cfg,base_cfg,roots,aga_supported=gamepad_fx.supported(game)),
                       rogue_victory_music=victory_music),on_tick=tick_haptics,
                       on_stop=stop_session,on_stalled=stalled_close,on_selection=remember,
                       on_session_preferences=take_proximity)
        finally:
            stop_haptics()
            stop_rogue_hud()
            victory_music.stop()
            if active_process is not None:
                active_process.request_stop()
                while (code:=active_process.poll()) is None:time.sleep(0.05)
                finish(code)
            stop_toasty()
        chosen.update(take_proximity())
        save(chosen)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('install',help='Prepare a community installation without starting Steam or the game')
    sub.add_parser('restore-steam',help='Restore the recorded Steam launch option with Steam closed')
    build=sub.add_parser('preparar')
    build.add_argument('--jogo',type=Path,required=True)
    build.add_argument('--lote',required=True)
    attach=sub.add_parser('vincular',help='Usa a instalação original da Steam, sem copiar jogo ou conteúdo')
    attach.add_argument('--jogo',type=Path,required=True)
    attach.add_argument('--lote',required=True)
    clean=sub.add_parser('limpar-copia',help='Apaga somente game/ do lote antigo; conserva dados e histórico')
    clean.add_argument('--pacote',type=Path,required=True)
    clean.add_argument('--executar',action='store_true',help='Sem esta opção, apenas mostra o destino')
    steam=sub.add_parser('steam')
    steam.add_argument('--pacote',type=Path,required=True,
        help='No executável empacotado, caminhos relativos partem de sua pasta')
    steam.add_argument('--kit-csp',type=Path,help='Payload CSP preparado; o build CSP já o encontra ao lado do executável')
    steam.add_argument('--fontes-csp',type=Path,help='Fontes livres preparadas; no build ficam em csp-fonts ao lado do executável')
    steam.add_argument('--cfg-csp',type=Path,help='Destino de overrides se Documents foi personalizado no Proton')
    steam.add_argument('--cfg-jogo',type=Path,help='Configuração nativa se Documents foi personalizado no Proton')
    steam.add_argument('command',nargs=argparse.REMAINDER)
    view=sub.add_parser('menu',help='Abre somente o menu; não inicia o simulador')
    view.add_argument('--jogo',type=Path,required=True)
    view.add_argument('--captura',type=Path)
    view.add_argument('--biblioteca-sdl2',type=Path,help='Biblioteca local explícita para a prévia')
    inspect=sub.add_parser('csp-info',help='Confere o payload e suas configurações, sem instalar ou executar o jogo')
    inspect.add_argument('--kit-csp',type=Path)
    restore=sub.add_parser('csp-restore',help='Restaura o CSP anterior gerido, com jogo/menu fechados, antes de voltar a entrega')
    restore.add_argument('--pacote',type=Path,required=True)
    report=sub.add_parser('results',help='Lê resultados locais preservados, sem jogo ou API')
    report.add_argument('--pacote',type=Path,required=True)
    report.add_argument('--limit',type=int,choices=range(1,1001),default=50,metavar='1..1000')
    retention=sub.add_parser('history-maintain',help='Aplica limpeza única autorizada e limite de 50 sessões, sem abrir jogo/menu')
    retention.add_argument('--pacote',type=Path,required=True)
    fonts=sub.add_parser('csp-fonts-restore',help='Reverte somente fontes criadas por este pacote, com jogo/menu fechados')
    fonts.add_argument('--pacote',type=Path,required=True)
    fonts.add_argument('--prefixo',type=Path,required=True,help='Mesmo STEAM_COMPAT_DATA_PATH usado pela entrada Steam')
    camera=sub.add_parser('chase-camera-restore',help='Remove só o script autoral de câmera, com jogo/menu fechados')
    camera.add_argument('--pacote',type=Path,required=True)
    camera.add_argument('--speed',action='store_true',help='Remove a Speed Chase em vez da CSP Adjustable')
    gt5=sub.add_parser('gt5-camera-info',help='Confere o mod GT5 incluído, sem instalar ou executar')
    gt5.add_argument('--zip',dest='archive',type=Path)
    gt5restore=sub.add_parser('gt5-camera-restore',help='Remove só a câmera GT5 gerida, com jogo/menu fechados')
    gt5restore.add_argument('--pacote',type=Path,required=True)
    gt5restore.add_argument('--zip',dest='archive',type=Path)
    sub.add_parser('bacc-camera-info',help='Confere as duas câmeras BACC incluídas, sem instalar ou executar')
    args=parser.parse_args(argv)
    try:
        if args.action=='install':
            from src.launcher import community_install
            community_install.run(ROOT)
        elif args.action=='restore-steam':
            from src.launcher import community_install
            community_install.restore_steam(ROOT)
        elif args.action=='preparar':
            print(prepare(args.jogo,args.lote))
        elif args.action=='vincular':
            print(installed.attach(args.jogo,args.lote,project_root=ROOT))
        elif args.action=='limpar-copia':
            print(json.dumps(installed.remove_copy(args.pacote,execute=args.executar),ensure_ascii=False))
        elif args.action=='steam':
            command=args.command[1:] if args.command[:1]==['--'] else args.command
            package=args.pacote
            if getattr(sys,'frozen',False) and not package.is_absolute():
                package=ROOT/package
            payload=args.kit_csp or (ROOT/'csp' if (ROOT/'csp/manifest.json').is_file() else None)
            with diagnostics.opening(ROOT) as trace:
                launch(package,command,csp_payload=payload,csp_config=args.cfg_csp,game_config=args.cfg_jogo,
                       trace=trace,font_payload=args.fontes_csp)
        elif args.action=='results':
            package=args.pacote
            if getattr(sys,'frozen',False) and not package.is_absolute():
                package=ROOT/package
            print(json.dumps(results.history(package,args.limit),ensure_ascii=False))
        elif args.action=='history-maintain':
            package=args.pacote
            if getattr(sys,'frozen',False) and not package.is_absolute():
                package=ROOT/package
            print(json.dumps(history_retention.maintain(package),ensure_ascii=False))
        elif args.action=='csp-info':
            manifest=csp.verify(args.kit_csp or ROOT/'csp')
            print(json.dumps(dict(version=manifest['version'],code=csp.BUILD_CODE,archive_sha256=manifest['archive_sha256'],
                files=len(manifest['files']),game_started=False),ensure_ascii=False))
        elif args.action=='csp-restore':
            print(json.dumps(csp.restore(args.pacote),ensure_ascii=False))
        elif args.action=='csp-fonts-restore':
            print(json.dumps(font_support.restore(args.pacote,
                {'STEAM_COMPAT_DATA_PATH':str(args.prefixo)}),ensure_ascii=False))
        elif args.action=='chase-camera-restore':
            restored=(chase_camera.restore(args.pacote, chase_camera.SPEED) if args.speed
                      else chase_camera.restore(args.pacote))
            print(json.dumps(restored,ensure_ascii=False))
        elif args.action=='gt5-camera-info':
            print(json.dumps(gt5_camera.inspect(args.archive or ROOT/'mods'/gt5_camera.ARCHIVE_NAME),ensure_ascii=False))
        elif args.action=='bacc-camera-info':
            print(json.dumps([bacc_camera.inspect(ROOT/'mods'/spec['archive'],mode)
                              for mode,spec in bacc_camera.SPECS.items()],ensure_ascii=False))
        elif args.action=='gt5-camera-restore':
            print(json.dumps(gt5_camera.restore(args.archive or ROOT/'mods'/gt5_camera.ARCHIVE_NAME,args.pacote),ensure_ascii=False))
        else:
            from src.launcher.window import run
            from src.launcher.native_menu import NativeMenu
            def preview(_):
                raise ValueError('Para dirigir, abra pela entrada Steam e pelo pacote completo')
            run(content.scan(safe.source_root(args.jogo)),{},preview,capture=args.captura,
                library_path=args.biblioteca_sdl2,preview=True,
                game=args.jogo,menu_class=NativeMenu,
                csp=True)
    except (OSError,ValueError,RuntimeError,safe.SafetyError) as error:
        print(str(error),file=sys.stderr)
        return 1
    return 0
