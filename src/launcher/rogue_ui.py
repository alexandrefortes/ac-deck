"""Menu Rogue independente: desafios persistentes e geração deliberada."""
from concurrent.futures import Future
from copy import deepcopy
import threading

from . import rogue, rogue_generator, rogue_duration, session_settings
from .rogue_rewards_ui import RogueRewardsUI
from .rogue_result_ui import RogueResultUI


class RogueUI(RogueResultUI, RogueRewardsUI):
    def init_rogue(self):
        self.init_rogue_rewards()
        self.init_rogue_result()
        self.rogue_store = None
        self.rogue_pending = None
        self.rogue_error = False
        self._rogue_announced = None
        if self.synthesis_store is not None:
            try:
                self.rogue_store = rogue.Store(rogue.path_for(self.synthesis_store))
            except (OSError, ValueError, RuntimeError, TypeError):
                self.rogue_error = True

    @property
    def rogue_state(self):
        store = getattr(self, 'rogue_store', None)
        return store.state if store is not None else dict(profile={}, run=None)

    @property
    def rogue_run(self):
        return self.rogue_state.get('run')

    def refresh_rogue(self, announce=True):
        if self.rogue_store is None:
            return
        try:
            self.rogue_store.reload()
            self.rogue_error = False
            run = self.rogue_run or {}
            outcome = run.get('last_outcome')
            if announce and outcome and outcome != self._rogue_announced and self.view == 'rogue':
                self._rogue_announced = deepcopy(outcome)
                self.present_rogue_result(outcome)
        except (OSError, ValueError, RuntimeError, TypeError):
            self.rogue_error = True
            if self.view == 'rogue':
                self.message = 'Rogue data unavailable. Original file kept.'

    def rogue_block(self):
        if self.rogue_error:
            return 'Rogue data unavailable. Original file kept.'
        if self.rogue_store is None:
            return 'Rogue needs a persistent game package.'
        if self.rogue_pending is not None:
            return 'Wait for the Rogue challenge or cancel generation.'
        run = self.rogue_run
        if run is None or run.get('status') != 'active':
            return 'Start a new Rogue run first.'
        if run.get('challenge') is None:
            return 'Generate the next Rogue challenge first.'
        return None

    def rogue_effective_selection(self):
        run = self.rogue_run
        if (self.rogue_error or not run or run.get('status') != 'active'
                or not isinstance(run.get('challenge'), dict)):
            return {}
        return session_settings.restore(run['challenge']['selection'], self.selection)

    def rogue_launch_selection(self):
        self.refresh_rogue(announce=False)
        error = self.rogue_block()
        if error:
            raise ValueError(error)
        run = self.rogue_run
        proposal = run['challenge']
        # Starting is the boundary that rechecks installed content, not a draw.
        self.replace_catalog(rogue_generator.validate(self.game, proposal))
        chosen = session_settings.restore(proposal['selection'], self.selection)
        chosen['rogue'] = dict(run_id=run['id'], challenge_id=proposal['challenge_id'])
        return chosen

    @staticmethod
    def _rogue_total(values):
        return sum(value for value in values.values() if type(value) is int and value >= 0)

    def rogue_items(self):
        if self.rogue_result_visible():
            return self.rogue_result_items()
        run = self.rogue_run
        profile = self.rogue_state.get('profile', {})
        active = bool(run and run.get('status') == 'active')
        available = self.rogue_store is not None and not self.rogue_error and not self.session_running
        pending = self.rogue_pending is not None
        rows = []
        if not active:
            rows += [self._item('rogue-new-local', 'button', 248, 166, 300, 48,
                                'New run / deterministic', primary=True,
                                disabled=not available or pending),
                     self._item('rogue-new-ai', 'button', 564, 166, 200, 48,
                                'New run / AI', disabled=not available or pending),
                     self._item('rogue-album', 'button', 780, 166, 220, 48,
                                'Achievements', disabled=not available)]
            title = 'Run ended. Your XP and stickers remain.' if run else 'One challenge. One more race.'
            rows += [self._item('rogue-intro', 'text', 248, 266, 990, 110, title,
                                value='Win the finish-position challenge, grow your run and discover hidden badges.',
                                disabled=True),
                     self._item('rogue-rules', 'text', 248, 414, 990, 114,
                                'Your car and circuit stay locked for the current event.',
                                value='One spare life to start. Daylight races / 08:00–16:00. AI generation uses your saved key only when you choose it.',
                                disabled=True)]
            if not available:
                rows.append(self._item('rogue-unavailable', 'text', 248, 550, 990, 40,
                                       'Rogue data unavailable. Original file kept.' if self.rogue_error else
                                       'Open Rogue from your linked game package to save a run.', disabled=True))
        else:
            proposal = run.get('challenge')
            label = ('Generating...' if pending else 'Challenge locked' if proposal else
                     'Generate next with AI' if run['mode'] == 'ai' else 'Next challenge')
            rows += [self._item('rogue-next', 'button', 248, 622, 246, 42, label,
                                primary=not proposal, disabled=not available or pending or bool(proposal)),
                     self._item('rogue-album', 'button', 510, 622, 174, 42, 'Achievements', disabled=not available),
                     self._item('rogue-reset', 'button', 1082, 622, 166, 42, 'Reset run', disabled=not available),
                     self._item('rogue-run-stats', 'text', 248, 164, 1000, 34,
                                f"Challenge {proposal['stage'] if proposal else rogue.stage(run)}   /   Wins {run['wins']}   /   Perfect streak {run['streak']}   /   Spare lives {run['lives']}",
                                color=(218, 216, 208), scale=1.6, disabled=True)]
            if proposal:
                rows.append(self._item('rogue-duration', 'text', 248, 119, 800, 24,
                                       rogue_duration.label(proposal.get('duration')), scale=1.25, disabled=True))
                chosen = proposal['selection']
                rows.append(self._item('rogue-objective', 'rogue-objective', 248, 208, 1000, 70,
                                       f"Finish P{proposal['target_position']} or better", disabled=True))
                for card in self._cards(chosen):
                    car = card['id'] == 'car'
                    card.update(id='rogue-car' if car else 'rogue-track', x=248 if car else 756,
                                y=296, w=492, h=236, synthesis_card=True, disabled=True)
                    rows.append(card)
                minutes = chosen['time_minutes']
                rows.append(self._item('rogue-conditions', 'rogue-conditions', 248, 550, 1000, 30,
                                       f"{chosen['laps']} {'lap' if chosen['laps'] == 1 else 'laps'}   /   {chosen['opponents']} opponents   /   AI {chosen['ai']}%   /   {minutes//60:02}:{minutes%60:02}   /   {chosen['weather'].replace('_', ' ').title()}",
                                       scale=1.65, color=(228, 226, 217), disabled=True))
                rows += self.rogue_mastery_items(chosen, profile)
            else:
                rows.append(self._item('rogue-waiting', 'text', 248, 340, 990, 110,
                                       'Your next challenge is waiting.',
                                       value='Choose Generate next with AI for one request.' if run['mode'] == 'ai' else
                                       'Choose Next challenge to reveal the next fixed event.', disabled=True))
                outcome = run.get('last_outcome') or {}
                if outcome:
                    rows.append(self._item('rogue-last-result-note', 'text', 248, 450, 990, 66,
                                           'Last challenge / '+outcome.get('status', 'recorded').replace('_', ' ').title(),
                                           value=outcome.get('message', ''), disabled=True))
            if pending:
                rows.append(self._item('rogue-cancel', 'button', 248, 524, 364, 40, 'Cancel generation'))
        if not active or not run.get('challenge'):
            rows.append(self._item('rogue-profile', 'text', 248, 572 if active else 610,
                                   990, 40,
                                   f"Total car XP {self._rogue_total(profile.get('car_xp', {}))} / Best run {profile.get('best_wins', 0)} wins",
                                   value=f"Achievements: {len(profile.get('badges', []))+len(profile.get('stickers', []))} / 11", disabled=True))
        if self.rogue_last_result is not None:
            rows.append(self._item('rogue-last-result', 'button', 1068, 104, 180, 40, 'Last result', disabled=pending))
        rows.append(self._item('rogue-restart-note', 'text', 248, 668, 1000, 16,
                               'Restarts are free / No life, XP or streak penalty.',
                               scale=1.2, disabled=True))
        return rows

    def rogue_overlay_items(self):
        if self.overlay == 'rogue-result-details':
            return self.rogue_result_detail_items()
        if self.overlay == 'rogue-reset':
            return [self._item('rogue-reset-warning', 'text', 268, 204, 940, 132,
                               'Reset this run?', value='The fixed challenge, wins and spare lives will be cleared. Your permanent XP, achievements and best run stay saved.', disabled=True),
                    self._item('rogue-reset-confirm', 'button', 268, 386, 420, 54, 'Reset run', primary=True),
                    self._item('rogue-reset-cancel', 'button', 708, 386, 420, 54, 'Keep this run')]
        if self.overlay == 'rogue-album':
            return self.rogue_album_items()
        if self.overlay == 'rogue-reward-detail':
            return self.rogue_reward_detail_items()
        if self.overlay == 'rogue-profile-reset':
            return self.rogue_profile_reset_items()
        return None

    def new_rogue_run(self, mode):
        if self.session_running or self.rogue_pending is not None or self.rogue_error or self.rogue_store is None:
            return
        self.refresh_rogue(announce=False)
        if self.rogue_error:
            return
        run = self.rogue_run
        if run and run.get('status') == 'active':
            self.message = 'Reset the active run before choosing a new one.'
            return
        if mode == 'ai' and not self.api_key:
            self.open_key()
            self.message = 'Save your API key, then choose New run / AI again.'
            return
        if self.game is None:
            self.message = 'The installed game is required to create a Rogue challenge.'
            return
        self.rogue_store.start_run(deepcopy(self.selection), mode=mode)
        self._rogue_announced = None
        self.rogue_result = self.rogue_last_result = None
        self.select_source('rogue')
        self.generate_rogue_challenge()

    def generate_rogue_challenge(self):
        if self.session_running or self.rogue_pending is not None or self.rogue_store is None:
            return False
        self.refresh_rogue(announce=False)
        run = self.rogue_run
        if self.rogue_error or not run or run.get('status') != 'active':
            return False
        if run.get('challenge'):
            self.message = 'Finish this challenge or reset the run before generating another event.'
            return False
        if self.game is None:
            self.message = 'The installed game is required to generate a Rogue challenge.'
            return False
        if run['mode'] == 'ai' and not self.api_key:
            self.open_key()
            self.message = 'Save your API key, then generate the next challenge explicitly.'
            return False
        snapshot = deepcopy(run)
        profile = deepcopy(self.rogue_state['profile'])
        timings = rogue_duration.load(self.synthesis_store)
        if run['mode'] != 'ai':
            try:
                proposal, catalog = rogue_generator.generate(self.game, snapshot, profile, catalog=self.catalog, timings=timings)
                self.rogue_store.set_challenge(proposal)
                self.replace_catalog(catalog)
                self.message = 'Rogue challenge ready. Finish the target position or better.'
                self.focus_id = 'start'
                return True
            except (OSError, ValueError, RuntimeError, TypeError):
                self.message = 'Could not prepare this Rogue challenge. Run kept; check installed content.'
                return False
        if self.ai_pending is not None:
            self.message = 'Wait for the Event Synthetizer request before generating with AI.'
            return False
        future = Future()
        self.rogue_pending = dict(future=future, run_id=run['id'], stage=rogue.stage(run))
        self.rogue_result = None
        key, effort, catalog, game = self.api_key, self.ai_effort, deepcopy(self.catalog), self.game
        def work():
            try:
                future.set_result(rogue_generator.generate(game, snapshot, profile,
                                                          catalog=catalog, api_key=key, effort=effort, timings=timings))
            except Exception:
                future.set_exception(ValueError('Rogue generation failed. Run kept; try again explicitly.'))
        try:
            threading.Thread(target=work, daemon=True, name='rogue-ai').start()
        except RuntimeError:
            self.rogue_pending = None
            self.message = 'Rogue worker could not start. Try again explicitly.'
            return False
        self.message = 'Generating your Rogue challenge. Cancel keeps this run.'
        self.focus_id = 'rogue-cancel'
        return True

    def cancel_rogue_generation(self):
        if self.rogue_pending is not None:
            self.rogue_pending = None
            self.message = 'Rogue generation cancelled. An already sent request may be charged.'
            self.focus_id = 'rogue-next'

    def poll_rogue(self):
        pending = self.rogue_pending
        if pending is None or not pending['future'].done() or self.session_running:
            return
        self.rogue_pending = None
        try:
            proposal, catalog = pending['future'].result()
            self.refresh_rogue(announce=False)
            run = self.rogue_run
            if (self.rogue_error or not run or run.get('status') != 'active'
                    or run['id'] != pending['run_id'] or rogue.stage(run) != pending['stage']
                    or run.get('challenge') is not None):
                return
            rogue_generator.validate(self.game, proposal, catalog=catalog)
            self.rogue_store.set_challenge(proposal)
            self.replace_catalog(catalog)
            self.message = 'Rogue challenge ready.' if self.view == 'rogue' else 'Your Rogue challenge is ready in Rogue.'
            if self.view == 'rogue':
                self.focus_id = 'start'
        except (OSError, ValueError, RuntimeError, TypeError, KeyError):
            self.message = 'Rogue generation failed. Run kept; try again explicitly.'

    def rogue_activate(self, identity):
        if self.rogue_result_activate(identity):
            return True
        if self.rogue_album_activate(identity):
            return True
        if not identity.startswith('rogue-'):
            return False
        if identity == 'rogue-new-local':
            self.new_rogue_run('deterministic')
        elif identity == 'rogue-new-ai':
            self.new_rogue_run('ai')
        elif identity == 'rogue-next':
            self.generate_rogue_challenge()
        elif identity == 'rogue-cancel':
            self.cancel_rogue_generation()
        elif identity == 'rogue-album':
            if self.rogue_store is not None and not self.rogue_error:
                self.open_rogue_album()
        elif identity == 'rogue-reset':
            if not self.session_running and self.rogue_store is not None and not self.rogue_error:
                self._open('rogue-reset', 'Reset Rogue run')
                self.focus_id = 'rogue-reset-cancel'
        elif identity == 'rogue-reset-cancel':
            self._close_overlay()
        elif identity == 'rogue-reset-confirm':
            if self.overlay == 'rogue-reset' and not self.session_running and self.rogue_store is not None:
                self.cancel_rogue_generation()
                self.rogue_store.reset_run()
                self.rogue_result = self.rogue_last_result = None
                self._close_overlay()
                self.message = 'Run reset. Your XP and achievements stay saved.'
                self.focus_id = 'rogue-new-local'
        return True

    def close(self):
        self.rogue_pending = None
        super().close()
