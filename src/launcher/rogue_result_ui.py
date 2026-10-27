"""Apresentação dos resultados Rogue; não julga corridas nem concede recompensas."""
from copy import deepcopy
import time

from . import rogue_rewards


_UNCONFIRMED = {
    'result_missing': 'The game did not save a race result.',
    'unchanged_result': 'The available result is unchanged from the previous race.',
    'not_written_during_session': 'The result was not saved during this attempt.',
    'process_start_failed': 'The race process could not start.',
    'baseline_unreadable': 'The previous result could not be read safely.',
    'result_unreadable_or_unsupported': 'The result could not be read or uses an unsupported format.',
    'invalid_number': 'The saved race result contains an invalid number.',
    'invalid_json': 'The game saved an unreadable race result.',
    'duplicate_json_key': 'The saved result contains conflicting fields.',
    'invalid_structure': 'The saved result is missing required race data.',
    'too_large': 'The saved race result exceeds the supported size.',
    'source_changed_while_reading': 'The race result changed while it was being collected.',
    'track_mismatch': 'The saved circuit or layout does not match this challenge.',
    'grid_mismatch': 'The saved grid does not match this challenge.',
    'car_mismatch': 'A saved car does not match the configured grid.',
    'skin_mismatch': 'The saved player livery does not match this challenge.',
    'session_count_mismatch': 'The saved session count does not match this challenge.',
    'session_type_mismatch': 'The saved session type does not match this challenge.',
    'lap_target_mismatch': 'The saved lap target does not match this challenge.',
    'invalid_lap_totals': 'The saved lap totals could not be verified.',
    'invalid_lap': 'The saved result contains invalid lap data.',
    'invalid_best_lap': 'The saved result contains invalid best-lap data.',
    'invalid_extras': 'The saved result contains invalid additional race data.',
    'missing_session_configuration': 'The race configuration could not be verified.',
    'capture_preparation_failed': 'Race result collection could not be prepared.',
    'session_not_collected': 'The race result has not been collected.',
    'history_write_failed': 'The collected result could not be saved locally.',
    'attempt_interrupted': 'The launcher closed before this attempt was confirmed.',
    'finish_not_confirmed': 'The result does not confirm that the race was finished.',
    'finish_evidence_missing': 'The result does not prove that the required laps were completed.',
    'final_position_missing': 'The race was finished, but the final position is missing.',
    'fresh_file_and_matching_configuration': 'The saved result lacks a confirmed finish or final position.',
}


class RogueResultUI:
    def init_rogue_result(self):
        self.rogue_result = None
        self.rogue_last_result = None
        self.rogue_result_started = 0

    def present_rogue_result(self, outcome):
        run = self.rogue_run or {}
        attempt = run.get('attempts', {}).get(outcome.get('attempt_id'))
        if not attempt:
            return
        selection = attempt['selection']
        profile = self.rogue_state['profile']
        status = outcome['status']
        returned_reason = outcome.get('reason')
        reason_code = returned_reason if isinstance(returned_reason, str) and returned_reason in _UNCONFIRMED else None
        ended = status == 'lost' and run.get('status') == 'ended'
        title = ('VICTORY' if outcome.get('position') == 1 else 'CHALLENGE COMPLETE') if status == 'won' else (
            'RUN OVER' if ended else 'CHALLENGE FAILED' if status == 'lost' else 'RESULT UNCONFIRMED')
        if status == 'start_failed':
            title = 'RACE COULD NOT START'
        if status == 'won':
            reason = 'Race finished. Position target achieved.'
        elif status == 'lost':
            reason = ('Race cancelled before the finish.' if outcome.get('position') is None else
                      f"Finished P{outcome['position']}. The challenge required P{outcome['target_position']} or better.")
            if not ended and run.get('challenge') is None:
                reason += ' One spare life used. Continue to the next event.'
        else:
            reason = _UNCONFIRMED.get(reason_code, 'The result could not be verified against this challenge.')
            reason += ' No life lost; your challenge is kept.'
        xp = outcome.get('xp_awarded', 0)
        mastery = []
        for label, total in (('Car', profile.get('car_xp', {}).get(selection['car'], 0)),
                             ('Circuit', profile.get('track_xp', {}).get(selection['track']+'|'+selection.get('layout', ''), 0))):
            before = rogue_rewards.mastery(max(0, total-xp))
            after = rogue_rewards.mastery(total)
            mastery.append(dict(label=label, before=before, after=after, awarded=xp))
        unlocked = set(outcome.get('new_badges', ())) | set(outcome.get('new_stickers', ()))
        rewards = [dict(name=entry['name'], image=self.rogue_album_image(entry))
                   for entry in self.rogue_album_entries() if entry['unlocked'] and entry['id'] in unlocked]
        cards = self._cards(selection)
        attempts = [row.get('outcome') or {} for row in run.get('attempts', {}).values()]
        run_xp = run.get('archived_xp', 0) + sum(row.get('xp_awarded', 0) for row in attempts)
        run_rewards = set(run.get('archived_rewards', ())) | {identity for row in attempts for key in ('new_badges', 'new_stickers') for identity in row.get(key, ())}
        milestone = status == 'won' and any(outcome['streak'] == threshold and identity in run.get('rewarded_badges', ())
                                            for identity, threshold, *_ in rogue_rewards.badge_definitions())
        self.rogue_result = dict(outcome=deepcopy(outcome), title=title, reason=reason, reason_code=reason_code,
                                car_name=cards[0]['label'], track_name=cards[1]['label'],
                                milestone=milestone, run_xp=run_xp, run_rewards=len(run_rewards),
                                tone='victory' if status == 'won' else 'over' if ended else
                                'retry' if status == 'lost' else 'unconfirmed',
                                mode=run.get('mode', 'deterministic'), selection=deepcopy(selection),
                                stage=outcome.get('stage', (run.get('last_challenge') or {}).get('stage', run.get('wins', 0)+1)),
                                advance=status == 'lost' and not ended and run.get('challenge') is None,
                                mastery=mastery, rewards=rewards)
        self.rogue_last_result = deepcopy(self.rogue_result)
        self.rogue_result_started = time.monotonic()
        self.focus_id = 'rogue-result-next'
        self.message = ''

    def rogue_result_visible(self):
        return self.view == 'rogue' and self.rogue_result is not None

    def rogue_result_footer(self):
        data = self.rogue_result
        label = ('View Challenge' if data['tone'] == 'victory' and (self.rogue_run or {}).get('challenge') else
                 'Next Challenge / AI' if (data['tone'] == 'victory' or data.get('advance')) and data['mode'] == 'ai' else
                 'Next Challenge' if data['tone'] == 'victory' or data.get('advance') else
                 'New Run / AI' if data['tone'] == 'over' and data['mode'] == 'ai' else
                 'New Run' if data['tone'] == 'over' else 'Retry Challenge')
        return [self._item('rogue-result-details', 'button', 864, 708, 148, 52, 'Race details'),
                self._item('rogue-result-next', 'button', 1032, 708, 216, 52, label,
                           primary=True, disabled=self.session_running)]

    def rogue_result_items(self):
        return [self._item('rogue-result', 'rogue-result', 248, 166, 1000, 438, '',
                           data=self.rogue_result, started=self.rogue_result_started,
                           disabled=True),
                self._item('rogue-album', 'button', 248, 624, 200, 40, 'Achievements'),
                self._item('rogue-result-back', 'button', 968, 624, 280, 40, 'Back to Rogue')]

    def rogue_result_detail_items(self):
        data = self.rogue_result
        if data is None:
            return []
        outcome, selected = data['outcome'], data['selection']
        diagnostic = (('Reason: '+data['reason_code'] if data.get('reason_code') else 'Reason unavailable')+' / '
                      if data['tone'] == 'unconfirmed' else '')
        cards = self._cards(selected)
        minutes = selected['time_minutes']
        values = [('Car', cards[0]['label']), ('Circuit', cards[1]['label']),
                  ('Race conditions', f"{selected['laps']} {'lap' if selected['laps'] == 1 else 'laps'} / {selected['opponents']} opponents / AI {selected['ai']}% / {minutes//60:02}:{minutes%60:02} / {selected['weather'].replace('_', ' ').title()}"),
                  ('Result', diagnostic+('P'+str(outcome['position']) if outcome.get('position') is not None else 'Position unconfirmed')
                   +f" / Target P{outcome['target_position']} or better / "+data['reason']),
                  ('Run progress', f"{outcome['wins']} wins / Perfect streak {outcome['streak']} / Spare lives {outcome['lives']}"),
                  ('Rewards saved', f"Car +{outcome['xp_awarded']} XP / Circuit +{outcome['xp_awarded']} XP / Spare lives {outcome['lives']} / Achievements kept")]
        return [self._item('rogue-result-detail:'+str(index), 'info', 268, 164+index*81, 940, 70,
                           label, value=value, value_scale=1.65, value_lines=1,
                           value_scroll='rogue-result-detail:'+str(index), disabled=True)
                for index, (label, value) in enumerate(values)]

    def rogue_result_continue(self):
        data = self.rogue_result
        if data is None or self.session_running or self.overlay:
            return
        if data['tone'] == 'victory' or data.get('advance'):
            if (self.rogue_run or {}).get('challenge'):
                self.rogue_result = None
                self.focus_id = 'start'
            elif self.generate_rogue_challenge():
                self.rogue_result = None
        elif data['tone'] == 'over':
            self.rogue_result = None
            self.new_rogue_run(data['mode'])
        else:
            self.rogue_result = None
            self.message = 'Same challenge. Your progress is saved. Press Start race when ready.'
            self.focus_id = 'start'

    def rogue_result_activate(self, identity):
        if identity == 'rogue-result-next':
            self.rogue_result_continue()
            return True
        if identity == 'rogue-result-details' and self.rogue_result is not None:
            self._open('rogue-result-details', 'Race result details')
            return True
        if identity == 'rogue-result-back':
            self.rogue_result = None
            self.focus_id = 'start' if not self.rogue_block() else 'rogue-next' if self.rogue_run and self.rogue_run['status'] == 'active' else 'rogue-new-local'
            return True
        if identity == 'rogue-last-result' and self.rogue_last_result is not None:
            self.rogue_result = deepcopy(self.rogue_last_result)
            self.rogue_result_started = time.monotonic()
            self.focus_id = 'rogue-result-next'
            return True
        return False

    def rogue_result_action(self, action):
        if not self.rogue_result_visible() or self.overlay or self.key_dialog:
            return False
        if action == 'back':
            self.rogue_result_activate('rogue-result-back')
            return True
        if action == 'launch':
            return True  # Starting a race stays separate from generating the next event.
        return False
