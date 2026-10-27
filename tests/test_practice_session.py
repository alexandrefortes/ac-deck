import configparser
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from src.launcher.practice_session import build_practice_plan, Car, Track
from tests.support.practice_session_fixtures import CATALOG, REQUEST, template


class PracticePlanTests(unittest.TestCase):
    def build(self, request=REQUEST, catalog=CATALOG, ini=None, **paths):
        return build_practice_plan(request, catalog, template() if ini is None else ini,
                                   game_dir=paths.get('game_dir', 'game'), data_dir=paths.get('data_dir', 'data'))

    def read(self, plan):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(plan.ini_text)
        return parser

    def test_single_car_practice_from_pit_and_no_remote_side_modes(self):
        ini = self.read(self.build(ini=template(REMOTE={'ACTIVE': '1'}, REPLAY={'ACTIVE': '1'})))
        self.assertEqual(ini['SESSION_0']['NAME'], 'Practice')
        self.assertEqual(ini['SESSION_0']['TYPE'], '1')
        self.assertEqual(ini['SESSION_0']['SPAWN_SET'], 'PIT')
        self.assertEqual(ini['RACE']['CARS'], '1')
        for name in ('REMOTE', 'REPLAY', 'BENCHMARK', 'RESTART', '__PREVIEW_GENERATION'):
            self.assertEqual(ini[name]['ACTIVE'], '0')

    def test_old_cars_sessions_conditions_and_events_removed(self):
        old = template(CAR_0={'MODEL': 'old', 'SETUP': 'old'}, CAR_1={'MODEL': 'old_ai'},
                       SESSION_0={'TYPE': '3'}, SESSION_1={'TYPE': '2'},
                       CONDITION_0={'TYPE': 'old'}, EVENT={'ID': 'old'}, SPECIAL_EVENT={'ID': 'old'})
        ini = self.read(self.build(ini=old))
        for name in ('CAR_1', 'SESSION_1', 'CONDITION_0', 'EVENT', 'SPECIAL_EVENT'):
            self.assertNotIn(name, ini)
        self.assertEqual(ini['CAR_0']['MODEL'], '-')
        self.assertEqual(ini['CAR_0']['SETUP'], '')
        self.assertEqual(ini['CAR_0']['BALLAST'], '0')
        self.assertEqual(ini['CAR_0']['RESTRICTOR'], '0')

    def test_layout_and_case_normalization_follow_catalog_membership(self):
        request = replace(REQUEST, car='FIXTURE_CAR', skin='OTHER_SKIN', track='FIXTURE_TRACK', layout='FIXTURE_LAYOUT')
        ini = self.read(self.build(request))
        self.assertEqual(ini['RACE']['CONFIG_TRACK'], 'fixture_layout')
        self.assertEqual(ini['CAR_0']['SKIN'], 'other_skin')

    def test_conditions_grip_and_unwritten_template_fields_are_preserved(self):
        raw = template(DYNAMIC_TRACK={'SESSION_START': '97.5', 'RANDOMNESS': '0', 'LAP_GAIN': '1',
                                     'SESSION_TRANSFER': '100', 'PRESET': '3'})
        ini = self.read(self.build(ini=raw))
        self.assertEqual(ini['TEMPERATURE']['ROAD'], '25')
        self.assertEqual(ini['DYNAMIC_TRACK']['SESSION_START'], '97.5')
        self.assertEqual(ini['LIGHTING']['SUN_ANGLE'], '0.25')
        self.assertEqual(ini['DYNAMIC_TRACK']['PRESET'], '3')

    def test_assists_in_race_ini_cannot_substitute_required_separate_configuration(self):
        with self.assertRaises(ValueError):
            self.build(ini=template(ASSISTS={'ABS': '2'}))
        self.assertIn('explicit_assists_video_controls', self.build().blocking_gates)

    def test_missing_condition_has_no_implicit_default(self):
        for section in ('TEMPERATURE', 'LIGHTING', 'WIND', 'DYNAMIC_TRACK'):
            with self.subTest(section=section), self.assertRaises(ValueError):
                self.build(ini=tuple(entry for entry in template() if entry[0] != section))

    def test_nonfinite_locale_and_invalid_numeric_conditions_rejected(self):
        for value in ('NaN', 'Infinity', '-Infinity', '1,5', 'not-a-number', ' 1.5', '1_000', '\u0661.5', '1e99999', '1e-99999'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build(ini=template(TEMPERATURE={'ROAD': value, 'AMBIENT': '20'}))

    def test_unverified_weather_rejected(self):
        with self.assertRaises(ValueError):
            self.build(ini=template(WEATHER={'NAME': 'missing_weather'}))

    def test_disabled_ghost_preserves_unwritten_advantage(self):
        ini = self.read(self.build(ini=template(GHOST_CAR={'SECONDS_ADVANTAGE': '1.25', 'ENABLED': '1'})))
        self.assertEqual(ini['GHOST_CAR']['ENABLED'], '0')
        self.assertEqual(ini['GHOST_CAR']['SECONDS_ADVANTAGE'], '1.25')

    def test_known_cm_extension_fields_removed(self):
        raw = template(REMOTE={'ACTIVE': '1', '__FEATURES': 'old', '__CM_EXTENDED': '1'},
                       RACE={'__CM_CUSTOM_MODE': 'old'}, OPTIONS={'__BACKGROUND_IMAGE': 'old'},
                       LIGHTING={'SUN_ANGLE': '0', 'TIME_MULT': '1', 'CLOUD_SPEED': '1', '__CM_DATE': 'old'})
        ini = self.read(self.build(ini=raw))
        self.assertNotIn('__FEATURES', ini['REMOTE'])
        self.assertNotIn('__CM_EXTENDED', ini['REMOTE'])
        self.assertNotIn('__CM_CUSTOM_MODE', ini['RACE'])
        self.assertNotIn('__CM_DATE', ini['LIGHTING'])
        self.assertNotIn('__BACKGROUND_IMAGE', ini['OPTIONS'])

    def test_existing_ai_level_preserved_and_missing_gets_cm_default(self):
        self.assertEqual(self.read(self.build())['RACE']['AI_LEVEL'], '87')
        self.assertEqual(self.read(self.build(ini=template(RACE={})))['RACE']['AI_LEVEL'], '100')

    def test_both_target_resolutions_are_intents_only(self):
        first = self.build()
        second = self.build(replace(REQUEST, resolution=(1920, 1200)))
        self.assertEqual(first.ini_text, second.ini_text)
        self.assertEqual(second.resolution_intent, (1920, 1200))
        self.assertFalse(second.execution_permitted)
        self.assertIn('real_display_mode', second.blocking_gates)

    def test_invalid_resolutions_types_rejected(self):
        for resolution in ((1920, 1080), (800, 1280), [1280, 800], (1280.0, 800), (True, 800)):
            with self.subTest(resolution=resolution), self.assertRaises(ValueError):
                self.build(replace(REQUEST, resolution=resolution))

    def test_duration_boundaries_and_bool_rejection(self):
        for duration in (0, 1, 1440):
            self.assertEqual(self.read(self.build(replace(REQUEST, duration_minutes=duration)))['SESSION_0']['DURATION_MINUTES'], str(duration))
        for duration in (-1, 1441, True, 1.5, '5'):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                self.build(replace(REQUEST, duration_minutes=duration))

    def test_ids_cannot_escape_or_inject_ini(self):
        for value in ('../car', '/car', 'C:\\car', 'car/skin', 'car\\skin', 'car\n[REMOTE]', 'car;mode', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build(replace(REQUEST, car=value))

    def test_membership_is_checked_per_car_and_track(self):
        for request in (replace(REQUEST, skin='absent'), replace(REQUEST, car='absent'),
                        replace(REQUEST, track='absent'), replace(REQUEST, layout='absent')):
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.build(request)

    def test_driver_and_template_injection_rejected(self):
        for value in ('Name\n[REMOTE]\nACTIVE=1', 'Name\rOther', 'x\x00y', 'x;y', 'x[y]'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build(replace(REQUEST, driver_name=value))
        with self.assertRaises(ValueError):
            self.build(ini=template(OTHER={'KEY': 'value\n[REMOTE]'}))

    def test_root_paths_are_relative_and_disjoint(self):
        for root in ('../game', '/game', 'C:/game', 'game\\dir', 'game//dir', './game', 'game/',
                     'game.', 'game ', 'NUL', 'dir/CON.txt', 'COM1', 'dir/LPT9.ini'):
            with self.subTest(root=root), self.assertRaises(ValueError):
                self.build(game_dir=root)
        for game, data in (('same', 'same'), ('game', 'game/data'), ('data/game', 'data'), ('Game', 'game/data')):
            with self.subTest(game=game, data=data), self.assertRaises(ValueError):
                self.build(game_dir=game, data_dir=data)

    def test_unknown_extension_or_external_path_cannot_survive_template(self):
        for extras in ({'OTHER':{'FILE':'E:/personal/setup.ini'}}, {'__EXTENSION':{'ACTIVE':'1'}},
                       {'RACE':{'FILE':'E:/personal/setup.ini'}}):
            with self.subTest(extras=extras),self.assertRaises(ValueError):
                self.build(ini=template(**extras))

    def test_inverted_wind_range_rejected(self):
        with self.assertRaises(ValueError):
            self.build(ini=template(WIND={'SPEED_KMH_MIN':'50','SPEED_KMH_MAX':'2','DIRECTION_DEG':'90'}))

    def test_preserved_numeric_fields_cannot_carry_unknown_paths(self):
        for extras in ({'RACE':{'AI_LEVEL':'E:/file'}}, {'GHOST_CAR':{'SECONDS_ADVANTAGE':'NaN'}}):
            with self.subTest(extras=extras),self.assertRaises(ValueError):
                self.build(ini=template(**extras))

    def test_spaces_accents_and_relocation_need_no_absolute_path(self):
        plan = self.build(game_dir='Programa do Papão/jogo', data_dir='Dados locais')
        self.assertEqual(plan.executable_relative, 'Programa do Papão/jogo/acs.exe')
        self.assertEqual(plan.race_ini_relative, 'Dados locais/Assetto Corsa/cfg/race.ini')
        self.assertNotIn('C:', plan.ini_text)
        self.assertEqual(plan.arguments, ())

    def test_acs_pro_is_not_chosen_and_runtime_is_unresolved(self):
        plan = self.build()
        self.assertEqual(plan.executable_relative, 'game/acs.exe')
        self.assertEqual(plan.working_directory_relative, 'game')
        self.assertEqual(plan.unset_environment, ('PYTHONHOME', 'PYTHONOPTIMIZE', 'PYTHONPATH'))
        self.assertIn('compatibility_command', plan.blocking_gates)

    def test_synthetic_or_unknown_provenance_never_approves_execution(self):
        for origin in ('synthetic', 'not_verified'):
            plan = self.build(catalog=replace(CATALOG, origin=origin))
            self.assertFalse(plan.execution_permitted)
            self.assertEqual(plan.content_origin, origin)
        with self.assertRaises(ValueError):
            self.build(catalog=replace(CATALOG, origin='official'))
        with self.assertRaises(ValueError):
            self.build(catalog=replace(CATALOG, evidence_refs=()))

    def test_inputs_are_unchanged_outputs_frozen_and_deterministic(self):
        original = template()
        first = self.build(ini=original)
        self.assertEqual(original, template())
        self.assertEqual(first, self.build(ini=original))
        with self.assertRaises(FrozenInstanceError):
            first.ini_text = 'changed'

    def test_gaps_and_alias_indexes_are_own_policy_errors(self):
        for extra in ({'CAR_2': {'MODEL': 'old'}}, {'SESSION_1': {'TYPE': '3'}},
                      {'CONDITION_1': {'TYPE': 'old'}}, {'CAR_00': {'MODEL': 'old'}}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.build(ini=template(**extra))

    def test_duplicate_casefolded_catalog_entries_rejected(self):
        for catalog in (replace(CATALOG, cars=(CATALOG.cars[0], Car('FIXTURE_CAR', ('skin',)))),
                        replace(CATALOG, tracks=(Track('fixture_track', ('', 'FIXTURE_LAYOUT', 'fixture_layout')),)),
                        replace(CATALOG, weather_ids=('fixture_clear', 'FIXTURE_CLEAR'))):
            with self.subTest(catalog=catalog), self.assertRaises(ValueError):
                self.build(catalog=catalog)

    def test_duplicate_sections_keys_and_mutable_template_rejected(self):
        for bad in (template()+template(), template()+(('OTHER', (('KEY', '1'), ('KEY', '2'))),), list(template())):
            with self.subTest(bad=type(bad)), self.assertRaises(ValueError):
                self.build(ini=bad)

    def test_pure_path_has_no_io_process_or_environment_access(self):
        with patch('builtins.open', side_effect=AssertionError('IO forbidden')), \
             patch('subprocess.Popen', side_effect=AssertionError('process forbidden')), \
             patch('os.getenv', side_effect=AssertionError('environment forbidden')):
            self.assertFalse(self.build().execution_permitted)


if __name__ == '__main__':
    unittest.main()
