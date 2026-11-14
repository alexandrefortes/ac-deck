"""Exercise Rogue challenges with synthetic content and results."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from src.launcher import content, event_synthetizer, results, rogue, rogue_generator
from src.launcher.window import Menu


class RogueVarietyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / 'game'
        for car in ('alpha', 'beta'):
            self.put(f'content/cars/{car}/data.acd', 'synthetic fixture')
            self.put(f'content/cars/{car}/skins/default/skin.ini', '[OWN]\n')
            self.put(f'content/cars/{car}/ui/ui_car.json', json.dumps({'name': car, 'class': 'GT Test'}))
        self.put('content/tracks/track_a/ui/ui_track.json', json.dumps({'name': 'Track A', 'pitboxes': 12}))
        self.put('content/tracks/track_a/ai/fast_lane.ai', 'synthetic fixture')
        self.put('content/weather/clear/weather.ini',
                 '[CLOUDS]\nNUMBER=0\n[FOG]\nDISTANCE=8000\n[LAUNCHER]\nNAME=Clear\n')
        for number, kind, goals in ((1, 4, (90000, 87000, 86000)),
                                    (2, 5, (2000, 3500, 5500)),
                                    (3, 6, (5000, 10000, 25000))):
            rule = 'TIME' if kind == 4 else 'POINTS'
            conditions = ''.join(f'[CONDITION_{i}]\nTYPE={rule}\nOBJECTIVE={value}\n'
                                 for i, value in enumerate(goals))
            self.put(f'content/specialevents/SPECIAL_EVENT_{number}/event.ini',
                     f'[EVENT]\nNAME=Fixture {number}\n[RACE]\nMODEL=alpha\nTRACK=track_a\n'
                     f'CONFIG_TRACK=\nCARS=1\n[SESSION_0]\nTYPE={kind}\n' + conditions)
        self.base = deepcopy(Menu(content.scan(self.game), game=self.game).selection)
        self.run = dict(id='variety-run', seed=123, mode='deterministic', base=self.base,
                        wins=0, streak=0, lives=1, status='active', challenge=None,
                        history=[], created_utc='2026-11-01T00:00:00+00:00')
        self.profile = dict(car_xp={}, track_xp={}, badges=[])
        self.sequence = 0

    def put(self, name, text):
        path = self.game / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def proposal(self, stage):
        return rogue_generator.generate(self.game, dict(self.run, wins=stage - 1), self.profile)[0]

    def attempt(self, mode):
        self.sequence += 1
        store = rogue.Store(self.root / f'state-{self.sequence}' / 'rogue.json')
        store.start_run(self.base, seed=123)
        catalog = event_synthetizer.discover(self.game)
        options = rogue_generator._solo_options(self.game, store.state['run'], catalog, 1, mode,
                                                rogue_generator._solo_templates(catalog, mode))
        proposal = options[0]
        store.set_challenge(proposal)
        return store, proposal, store.begin_attempt(proposal['selection'])

    def record(self, attempt, extras):
        chosen = attempt['selection']
        kind = content.MODES[chosen['mode']][1]
        expected = dict(track=chosen['track'], layout=chosen.get('layout', ''), car=chosen['car'],
                        skin=chosen['skin'], cars=[chosen['car']], sessions=[dict(type=kind, target_laps=0)])
        native = dict(track=chosen['track'], players=[dict(car=chosen['car'], skin=chosen['skin'])],
                      number_of_sessions=1, sessions=[dict(type=kind, lapsCount=0)], extras=extras)
        return dict(schema_version=1, session_id=attempt['session_id'], status='imported',
                    expected=expected, result=results.parse(native, expected))

    def test_legacy_generated_race_accepts_default_ai(self):
        self.base.pop('ai')
        proposal, catalog = event_synthetizer.generate(self.game, self.base, seed=123)
        self.assertEqual(1, proposal['schema_version'])
        self.assertNotIn('ai', proposal['selection'])
        self.assertIs(catalog, event_synthetizer.validate(self.game, proposal, catalog=catalog))

    def test_challenges_rotate_and_use_synthetic_native_goals(self):
        proposals = [self.proposal(stage) for stage in range(1, 13)]
        self.assertEqual([2, 1, 3, 4] * 3, [row['selection']['mode'] for row in proposals])
        self.assertEqual([2000, 3500, 5500], [proposals[i]['objective']['target'] for i in (2, 6, 10)])
        self.assertEqual([5000, 10000, 25000], [proposals[i]['objective']['target'] for i in (3, 7, 11)])
        self.assertTrue(all(row['selection']['event'] == '' for row in proposals))
        self.assertEqual(proposals[3], self.proposal(4))

    def test_solo_thresholds_and_persistence(self):
        for mode, name, key in ((1, 'bestlap', 'time'), (3, 'timeattack', 'points'), (4, 'drift', 'points')):
            for success in (True, False):
                with self.subTest(mode=mode, success=success):
                    store, proposal, attempt = self.attempt(mode)
                    target = proposal['objective']['target']
                    value = target if success else target + 1 if mode == 1 else target - 1
                    record = self.record(attempt, [dict(name=name, **{key: value})])
                    outcome = store.finish_attempt(attempt['id'], record)
                    self.assertEqual(('won', 100) if success else ('lost', 20),
                                     (outcome['status'], outcome['xp_awarded']))
                    self.assertEqual(value, outcome['value'])
                    self.assertEqual(outcome, rogue.Store(store.path).finish_attempt(attempt['id'], record))

    def test_ambiguous_solo_result_keeps_challenge_and_life(self):
        for extras in ([], [dict(name='drift', points=0)], [dict(name='drift', points=True)],
                       [dict(name='drift', points=5000)] * 2, [dict(name='timeattack', points=5000)]):
            with self.subTest(extras=extras):
                store, proposal, attempt = self.attempt(4)
                outcome = store.finish_attempt(attempt['id'], self.record(attempt, extras))
                self.assertEqual(('unconfirmed', 'objective_missing', 1, 0),
                                 (outcome['status'], outcome['reason'], outcome['lives'], outcome['xp_awarded']))
                self.assertEqual(proposal, store.state['run']['challenge'])

    def test_result_from_another_session_does_not_change_state(self):
        store, proposal, attempt = self.attempt(4)
        record = self.record(attempt, [dict(name='drift', points=proposal['objective']['target'])])
        record['session_id'] = 'other'
        before = store.path.read_bytes()
        with self.assertRaises(ValueError):
            store.finish_attempt(attempt['id'], record)
        self.assertEqual(before, store.path.read_bytes())
