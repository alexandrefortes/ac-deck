"""First Steam Play with synthetic files and child processes, without Wine or a game."""
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.launcher import application as jogo_deck, installed


class FirstSteamLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.game,self.package=self.root/'game',self.root/'package'
        self.ini=self.game/'system/cfg/inireaderdocuments.ini'
        self.ini.parent.mkdir(parents=True)
        self.ini.write_text('[FOLDER]\nPROGRAM_NAME=Assetto Corsa\nBYPASS_DOCUMENT_FOLDER=0\n')
        (self.game/'acs.exe').write_bytes(b'synthetic game, never executed')
        (self.package/'launcher').mkdir(parents=True)
        self.env=dict(SteamAppId='244210',SteamGameId='244210',
                      STEAM_COMPAT_DATA_PATH=str(self.root/'compatdata'))
        self.docs=self.root/'compatdata/pfx/drive_c/users/steamuser/Documents'
        record=dict(status='prepared',content_scope='installed_content',game_mode='installed',
                    source=str(self.game),selection=[dict(relative_path='acs.exe',
                    sha256=hashlib.sha256((self.game/'acs.exe').read_bytes()).hexdigest())])
        (self.package/'prepared.json').write_text(json.dumps(record))
        self.command=['/runtime/reaper','SteamLaunch','AppId=244210','--',
                      '/runtime/pressure-vessel','--','/tools/Proton/proton',
                      'waitforexitandrun',str(self.game/'AssettoCorsa.exe'),'game-only argument']

    def test_prefix_command_preserves_the_selected_runtime_and_rejects_ambiguous_targets(self):
        for verb in ('run','waitforexitandrun'):
            with self.subTest(verb=verb):
                command=list(self.command)
                command[-3]=verb
                before=list(command)
                self.assertEqual(command[:-2]+[r'C:\windows\system32\cmd.exe','/c','exit'],
                                 jogo_deck.steam.prefix_command(command,self.game))
                self.assertEqual(before,command)
        invalid=([],['%command%'],self.command+[self.command[-2]],
                 self.command[:-3]+['runinprefix',self.command[-2]],
                 self.command[:-4]+['/other/wine','run',self.command[-2]])
        for command in invalid:
            with self.subTest(command=command),self.assertRaises(ValueError):
                jogo_deck.steam.prefix_command(command,self.game)

    def test_missing_documents_is_distinct_from_invalid_existing_documents(self):
        with self.assertRaises(installed.DocumentsMissing):
            installed.config_path(self.game,self.env)
        self.docs.parent.mkdir(parents=True)
        self.docs.write_text('preserve existing file')
        with self.assertRaisesRegex(ValueError,'existing path was preserved'):
            installed.config_path(self.game,self.env)
        self.assertEqual('preserve existing file',self.docs.read_text())

    def test_prefix_command_is_the_only_spawn_and_signal_handlers_are_restored(self):
        handlers={number:signal.getsignal(number) for number in (signal.SIGTERM,signal.SIGINT)}
        self.env['WINEDLLOVERRIDES']='other=n;dwrite=n,b'
        original_env=dict(self.env)
        child=Mock(pid=123)
        owned=Mock(poll=Mock(return_value=0))
        with patch.object(jogo_deck.session_process,'snapshot',return_value={}), \
                patch.object(jogo_deck.session_process,'Session',return_value=owned), \
                patch.object(jogo_deck.subprocess,'Popen',return_value=child) as spawn:
            jogo_deck._initialize_prefix(self.package,self.game,str(self.game),self.command,self.env)
        self.assertEqual(self.command[:-2]+[r'C:\windows\system32\cmd.exe','/c','exit'],spawn.call_args.args[0])
        self.assertEqual(self.game,spawn.call_args.kwargs['cwd'])
        self.assertEqual(dict(self.env,WINEDLLOVERRIDES='other=n;dwrite=b'),spawn.call_args.kwargs['env'])
        self.assertEqual(original_env,self.env)
        self.assertEqual(handlers,{number:signal.getsignal(number) for number in handlers})
        owned.request_stop.assert_not_called()

    def test_prefix_cancellation_stops_only_the_supervised_tree_and_restores_handlers(self):
        previous=signal.getsignal(signal.SIGTERM)
        owned=Mock(poll=Mock(side_effect=[None,None,0]))
        def stop(_):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        with patch.object(jogo_deck.session_process,'snapshot',return_value={}), \
                patch.object(jogo_deck.session_process,'Session',return_value=owned), \
                patch.object(jogo_deck.subprocess,'Popen',return_value=Mock(pid=123)), \
                patch.object(jogo_deck.time,'sleep',side_effect=stop):
            with self.assertRaisesRegex(InterruptedError,'existing Steam data was preserved'):
                jogo_deck._initialize_prefix(self.package,self.game,str(self.game),self.command,self.env)
        owned.request_stop.assert_called_once()
        self.assertEqual(previous,signal.getsignal(signal.SIGTERM))

    def test_nonzero_prefix_helper_exit_is_an_error_without_game_or_result_handling(self):
        with patch.object(jogo_deck.session_process,'snapshot',return_value={}), \
                patch.object(jogo_deck.session_process,'Session',return_value=Mock(poll=Mock(return_value=1))), \
                patch.object(jogo_deck.subprocess,'Popen',return_value=Mock(pid=123)):
            with self.assertRaisesRegex(ValueError,'selected Steam compatibility tool'):
                jogo_deck._initialize_prefix(self.package,self.game,str(self.game),self.command,self.env)
        self.assertFalse((self.package/'launcher/sessions').exists())

    def test_documents_symlink_is_reused_but_a_broken_link_is_preserved(self):
        target=self.root/'player documents'
        target.mkdir()
        self.docs.parent.mkdir(parents=True)
        try:
            self.docs.symlink_to(target,target_is_directory=True)
        except OSError as error:
            self.skipTest(f'Cannot create a symlink fixture: {error}')
        self.assertEqual(target/'Assetto Corsa/cfg',installed.config_path(self.game,self.env))
        target.rmdir()
        with self.assertRaisesRegex(ValueError,'existing path was preserved'):
            installed.config_path(self.game,self.env)
        self.assertTrue(self.docs.is_symlink())

    @unittest.skipUnless(sys.platform=='linux','Linux own subprocess tree')
    def test_prefix_preparation_waits_for_its_adopted_synthetic_child(self):
        marker=self.root/'own-child-complete'
        code='import time,pathlib;time.sleep(0.15);pathlib.Path('+repr(str(marker))+').write_text("done")'
        wrapper='import subprocess,sys;subprocess.Popen([sys.executable,"-c",'+repr(code)+'])'
        with patch.object(jogo_deck.steam,'prefix_command',return_value=[sys.executable,'-c',wrapper]), \
                jogo_deck.session_process.Owner():
            jogo_deck._initialize_prefix(self.package,self.game,str(self.game),self.command,dict(os.environ,**self.env))
        self.assertEqual('done',marker.read_text())

    def before_menu(self,initialize,*,explicit=None):
        with patch.dict(os.environ,self.env,clear=True), \
                patch.object(jogo_deck,'_initialize_prefix',side_effect=initialize) as prepare, \
                patch.object(jogo_deck.hud_cleanup,'remove_managed'), \
                patch.object(jogo_deck.history_retention,'maintain_locked'), \
                patch.object(jogo_deck.csp,'config_roots',side_effect=RuntimeError('fixture stops before the menu')) as roots, \
                patch.object(jogo_deck.subprocess,'Popen',side_effect=AssertionError('No Steam or game in this fixture')):
            with self.assertRaisesRegex(RuntimeError,'fixture stops before the menu'):
                jogo_deck.launch(self.package,self.command,csp_payload=self.root/'kit',game_config=explicit)
        return prepare,roots

    @unittest.skipUnless(sys.platform=='linux','Linux launcher lock')
    def test_first_steam_play_initializes_then_reuses_documents_without_changing_settings(self):
        def initialize(*args,**kwargs):
            self.docs.mkdir(parents=True)
            (self.docs/'existing-player-data').write_bytes(b'keep')
        prepare,roots=self.before_menu(initialize)
        prepare.assert_called_once()
        self.assertEqual(self.docs/'Assetto Corsa/cfg',roots.call_args.kwargs['native_cfg'])
        prepare,_=self.before_menu(None)
        prepare.assert_not_called()
        self.assertEqual(b'keep',(self.docs/'existing-player-data').read_bytes())

    @unittest.skipUnless(sys.platform=='linux','Linux launcher lock')
    def test_custom_bypass_and_explicit_config_do_not_initialize_the_prefix(self):
        cases=(('[FOLDER]\nCUSTOM_PATH=custom/profile\n',None,self.game/'custom/profile/cfg'),
               ('[FOLDER]\nBYPASS_DOCUMENT_FOLDER=1\n',None,self.game/'cfg'),
               ('[FOLDER]\nCUSTOM_PATH=../invalid\n',self.root/'explicit/cfg',self.root/'explicit/cfg'))
        for raw,explicit,expected in cases:
            with self.subTest(raw=raw):
                self.ini.write_text(raw)
                prepare,roots=self.before_menu(None,explicit=explicit)
                prepare.assert_not_called()
                self.assertEqual(expected,roots.call_args.kwargs['native_cfg'])
                self.assertFalse(self.docs.exists())

    @unittest.skipUnless(sys.platform=='linux','Linux launcher lock')
    def test_prefix_success_without_documents_stops_before_configuration_and_menu(self):
        with patch.dict(os.environ,self.env,clear=True), \
                patch.object(jogo_deck,'_initialize_prefix') as initialize, \
                patch.object(jogo_deck.csp,'config_roots') as roots:
            with self.assertRaisesRegex(ValueError,'Proton did not create its Documents folder'):
                jogo_deck.launch(self.package,self.command,csp_payload=self.root/'kit')
        initialize.assert_called_once()
        roots.assert_not_called()

    @unittest.skipUnless(sys.platform=='linux','Linux launcher lock')
    def test_wrong_steam_context_changed_executable_and_invalid_ini_never_initialize(self):
        original=(self.game/'acs.exe').read_bytes()
        for reason in ('context','executable','ini'):
            with self.subTest(reason=reason):
                self.env['SteamAppId']='other' if reason=='context' else '244210'
                (self.game/'acs.exe').write_bytes(b'changed' if reason=='executable' else original)
                self.ini.write_text('[FOLDER]\nPROGRAM_NAME=../invalid\n' if reason=='ini' else '[FOLDER]\n')
                with patch.dict(os.environ,self.env,clear=True), \
                        patch.object(jogo_deck,'_initialize_prefix') as initialize:
                    with self.assertRaises((ValueError,RuntimeError)):
                        jogo_deck.launch(self.package,self.command,csp_payload=self.root/'kit')
                initialize.assert_not_called()


if __name__ == '__main__':
    unittest.main()
