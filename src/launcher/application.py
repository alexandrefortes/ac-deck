"""Conteúdo instalado completo e menu por controle, pela entrada Steam do jogo."""
import argparse
from functools import partial
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

ROOT=(Path(sys.executable).resolve().parent if getattr(sys,'frozen',False)
      else Path(__file__).resolve().parents[2])
from . import package_setup, steam
from . import file_io as safe
from src.launcher import content, csp, installed, diagnostics, font_support, linear_gamma, graphics, chase_camera, hud_cleanup, gt5_camera, bacc_camera, event_synthetizer, player_history, results, campaigns
from src.launcher import driving_haptics, driving_haptics_app, session_settings, session_process, history_retention
from src.launcher import rogue_toasty_session, rogue_toasty_install


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


def _finish_rogue_attempt(active, record, *, trace=None):
    """O recibo do núcleo evita reaplicar XP mesmo se a finalização for repetida."""
    if active is None:return ''
    store,attempt=active
    try:
        update=store.finish_attempt(attempt['id'],record)
        if trace:trace('rogue_result',outcome=update['status'])
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


def environment(original,package,*,hud=True,csp_enabled=None,game=None,frame_limiter=None):
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
    if csp_enabled is not None:
        env['WINEDLLOVERRIDES']=csp.wine_overrides(env.get('WINEDLLOVERRIDES',''),csp_enabled)
    if csp_enabled:
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


def launch(package,command,*,csp_payload=None,csp_config=None,game_config=None,trace=None,font_payload=None,
           inline_gamma=False):
    if sys.platform!='linux':
        raise ValueError('Abra esta entrada pela Steam no Linux')
    import fcntl
    from src.launcher.window import run
    from src.launcher.native_menu import NativeMenu
    package=safe.source_root(package)
    record=safe.read_json(package/'prepared.json')
    if record.get('status')!='prepared' or record.get('content_scope')!='installed_content':
        raise ValueError('Use um pacote completo preparado pelo jogo_deck.py')
    game=installed.game_path(package,record)
    direct=record.get('game_mode')=='installed'
    cfg=installed.config_path(game,os.environ,game_config) if direct else game/'state/Assetto Corsa/cfg'
    base_cfg=package/'cfg' if direct else None
    argv=steam.steam_command(command,record['source'],package)
    argv[argv.index(str(package/'game/acs.exe'))]=str(game/'acs.exe')
    environment(os.environ,package,game=game)
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
        hud_cleanup.remove_managed(package,game)
        history_policy=history_retention.maintain_locked(package)
        if trace:trace('history_retention',**history_policy)
        csp_enabled=csp_payload is not None
        if inline_gamma and trace:
            trace('csp_inline_gamma_ignored',reason='Linear color is always Off')
        roots=[]
        if csp_enabled:
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
        selection=graphics.migrate(selection,csp_available=csp_enabled)
        _recover_rogue_attempt(state,trace=trace)
        active_result=None
        active_campaign=None
        campaign_unavailable=False
        active_rogue=None
        active_process=None
        active_haptics=None
        active_toasty=None
        lifecycle_lock=threading.RLock()
        last_selection=dict(selection)
        def remember(chosen):
            nonlocal last_selection
            last_selection=dict(chosen)
        def stop_session():
            # The close worker cannot race config preparation or finalization.
            if not lifecycle_lock.acquire(blocking=False):return
            try:
                if active_process is not None:active_process.request_stop()
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
            nonlocal active_result,active_process,active_campaign,campaign_unavailable,active_rogue
            stop_haptics()
            stop_toasty()
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
                rogue_note=_finish_rogue_attempt(rogue_attempt,record,trace=trace)
                return results.message(record)+campaign_note+rogue_note
            except (OSError,ValueError,RuntimeError):
                rogue_note=_finish_rogue_attempt(rogue_attempt,dict(schema_version=1,
                    session_id=collector.history.name,status='unavailable',reason='history_write_failed'),trace=trace)
                if trace:
                    trace('session_result',status='unavailable',reason='history_write_failed')
                return 'Session ended. Could not preserve the result; check local storage.'+rogue_note
        def save(chosen):
            chosen=graphics.normalize(chosen,csp_available=csp_enabled)
            safe.check_components(saved)
            if saved.exists():
                safe.require_reference(saved.lstat(),saved)
            temporary=state/('selection-'+uuid.uuid4().hex+'.json')
            safe.write_new_json(temporary,chosen)
            temporary.replace(saved)
        def start(chosen):
            with lifecycle_lock:return start_locked(chosen)
        def start_locked(chosen):
            nonlocal catalog,active_result,active_process,active_haptics,active_campaign,campaign_unavailable,active_rogue,active_toasty
            # O loop da janela também bloqueia a ação. Esta guarda preserva a
            # sessão e seu coletor caso outro chamador tente iniciar de novo.
            if active_process is not None:
                raise ValueError('Finish the current session before starting another.')
            chosen=dict(chosen)
            rogue_store=None
            rogue_marker=chosen.get('rogue')
            proposal=chosen.pop(event_synthetizer.MARKER,None)
            if 'rogue' in chosen:
                if proposal is not None:
                    raise ValueError('A session cannot combine Rogue and Event Synthetizer proposals')
                rogue_store,chosen,catalog=_rogue_selection(game,state/'rogue.json',chosen)
            elif proposal is not None:
                catalog=event_synthetizer.validate(game,proposal)
                if not session_settings.same(chosen,proposal['selection']):
                    raise ValueError('Generated event differs from validated proposal')
            else:
                # A geração pode atualizar o catálogo visto no menu. Revalidar
                # também a escolha manual, sem alterar seus valores salvos.
                catalog=content.scan(game)
            chosen=graphics.normalize(chosen,csp_available=csp_enabled)
            driving_haptics.validate(chosen)
            active_csp=graphics.uses_csp(chosen['graphics_profile'])
            if active_csp and not csp_enabled:
                raise ValueError('This profile requires the included CSP payload')
            history=state/'sessions'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
            style='base'
            csp_plan=csp.plan_settings(game,chosen,roots,weather_style=style) if active_csp else []
            camera_receipt=None
            if active_csp and chosen.get('chase_camera')==chase_camera.SCRIPT:
                camera_receipt=chase_camera.install(package)
            elif active_csp and chosen.get('chase_camera')==chase_camera.GT5:
                camera_receipt=gt5_camera.install(ROOT/'mods'/gt5_camera.ARCHIVE_NAME,package)
            elif active_csp and chosen.get('chase_camera') in chase_camera.BACC:
                mode=chosen['chase_camera']
                camera_receipt=bacc_camera.install(ROOT/'mods'/bacc_camera.SPECS[mode]['archive'],package,mode)
            history_retention.maintain_locked(package,reserve=1)
            hashes=content.write_session(game,catalog,chosen,history,csp=active_csp,
                cfg=cfg,base_cfg=base_cfg,xinput=direct)
            csp_files=csp.write_settings(csp_plan,history) if active_csp else []
            haptics_ready=False
            if active_csp and chosen.get('driving_haptics',driving_haptics.DEFAULTS['driving_haptics']):
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
            child_env=environment(os.environ,package,hud=chosen['hud'],csp_enabled=active_csp,game=game,
                                  frame_limiter=chosen.get('frame_limiter'))
            pp=content.read_ini(history/'video.ini')
            safe.write_new_json(history/'session.json',dict(selection=chosen,config_sha256=hashes,
                hud_requested=chosen['hud'],benchmark_required=False,csp_enabled=active_csp,
                csp_available=csp_enabled,csp_version=csp.VERSION if active_csp else None,csp_config=csp_files,
                csp_weather_style=style if active_csp else None,csp_inline_gamma=False,
                graphics_preset_revision=graphics.PRESET_REVISION,
                frame_limiter=chosen.get('frame_limiter'),dxvk_frame_rate=child_env.get('DXVK_FRAME_RATE'),
                dwrite_override=child_env.get('WINEDLLOVERRIDES'),
                chase_camera=chosen.get('chase_camera','original') if active_csp else 'original',
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
                    metadata=dict(run_id=attempt['run_id'],challenge_id=attempt['challenge_id'],
                                  attempt_id=attempt['id'],session_id=history.name)
                    if active_csp:
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
            return active_process
        proton=next((v for v in command if Path(v).name=='proton'),None)
        try:
            chosen=run(catalog,selection,start,proton=proton,csp=csp_enabled,game=game,trace=trace,
                       synthesis_store=state/'event-synthetizer.json',on_exit=finish,menu_class=partial(NativeMenu,campaign_cfg=cfg),on_tick=tick_haptics,
                       on_stop=stop_session,on_stalled=stalled_close,on_selection=remember)
        finally:
            stop_haptics()
            if active_process is not None:
                active_process.request_stop()
                while (code:=active_process.poll()) is None:time.sleep(0.05)
                finish(code)
            stop_toasty()
        save(chosen)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
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
    steam.add_argument('--sem-csp',action='store_true',help='Usa dwrite do Wine e os perfis nativos, sem remover o patch da cópia')
    steam.add_argument('--csp-inline-gamma',action='store_true',help=argparse.SUPPRESS)
    steam.add_argument('--cfg-csp',type=Path,help='Destino de overrides se Documents foi personalizado no Proton')
    steam.add_argument('--cfg-jogo',type=Path,help='Configuração nativa se Documents foi personalizado no Proton')
    steam.add_argument('command',nargs=argparse.REMAINDER)
    view=sub.add_parser('menu',help='Abre somente o menu; não inicia o simulador')
    view.add_argument('--jogo',type=Path,required=True)
    view.add_argument('--captura',type=Path)
    view.add_argument('--biblioteca-sdl2',type=Path,help='Biblioteca local explícita para a prévia')
    view.add_argument('--kit-csp',type=Path)
    view.add_argument('--sem-csp',action='store_true')
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
    gamma=sub.add_parser('csp-inline-gamma-restore',help='Remove só a cópia de teste do gamma, com jogo/menu fechados')
    gamma.add_argument('--pacote',type=Path,required=True)
    gamma.add_argument('--kit-csp',type=Path)
    camera=sub.add_parser('chase-camera-restore',help='Remove só o script autoral de câmera, com jogo/menu fechados')
    camera.add_argument('--pacote',type=Path,required=True)
    gt5=sub.add_parser('gt5-camera-info',help='Confere o mod GT5 incluído, sem instalar ou executar')
    gt5.add_argument('--zip',dest='archive',type=Path)
    gt5restore=sub.add_parser('gt5-camera-restore',help='Remove só a câmera GT5 gerida, com jogo/menu fechados')
    gt5restore.add_argument('--pacote',type=Path,required=True)
    gt5restore.add_argument('--zip',dest='archive',type=Path)
    sub.add_parser('bacc-camera-info',help='Confere as duas câmeras BACC incluídas, sem instalar ou executar')
    args=parser.parse_args(argv)
    try:
        if args.action=='preparar':
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
            payload=None if args.sem_csp else (args.kit_csp or (ROOT/'csp' if (ROOT/'csp/manifest.json').is_file() else None))
            with diagnostics.opening(ROOT) as trace:
                launch(package,command,csp_payload=payload,csp_config=args.cfg_csp,game_config=args.cfg_jogo,
                       trace=trace,font_payload=args.fontes_csp,inline_gamma=args.csp_inline_gamma)
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
        elif args.action=='csp-inline-gamma-restore':
            print(json.dumps(linear_gamma.restore(args.kit_csp or ROOT/'csp',args.pacote),ensure_ascii=False))
        elif args.action=='chase-camera-restore':
            print(json.dumps(chase_camera.restore(args.pacote),ensure_ascii=False))
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
                csp=not args.sem_csp and (args.kit_csp is not None or (ROOT/'csp/manifest.json').is_file()))
    except (OSError,ValueError,RuntimeError,safe.SafetyError) as error:
        print(str(error),file=sys.stderr)
        return 1
    return 0
