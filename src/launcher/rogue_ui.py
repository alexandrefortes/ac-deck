"""Menu Rogue independente: desafios persistentes e geração deliberada."""
from concurrent.futures import Future
from copy import deepcopy
import threading

from . import content, rogue, rogue_difficulty, rogue_generator, rogue_duration, session_settings, favorites
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
        self.rogue_settings_draft = None
        self.rogue_setting_edit = None
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

    def rogue_preferences(self):
        return self.rogue_store.settings() if self.rogue_store is not None else rogue_difficulty.preset('normal')

    def rogue_progress_profile(self):
        run = self.rogue_run or {}
        difficulty = (run.get('difficulty', 'normal') if run.get('status') == 'active' else
                      self.rogue_preferences()['difficulty'])
        return rogue.progress_profile(self.rogue_state.get('profile', {}), difficulty)

    def rogue_race_settings_label(self, selection=None):
        run = self.rogue_run or {}
        chosen = selection if selection is not None else (run.get('challenge') or {}).get('selection', {})
        text = rogue_difficulty.label(run.get('difficulty', self.rogue_preferences()['difficulty']))
        if chosen.get('mode') == 2:
            text += f" / AI {chosen['ai']}% / Aggression {chosen.get('ai_aggression', 0)}%"
        return text

    def open_rogue_settings(self):
        if (self.session_running or self.rogue_pending is not None or self.rogue_error
                or self.rogue_store is None):
            return
        self.refresh_rogue(announce=False)
        if self.rogue_error:
            return
        self.rogue_settings_draft = self.rogue_preferences()
        self.rogue_setting_edit = None
        self._open('rogue-settings', 'Rogue settings')
        active = (self.rogue_run or {}).get('status') == 'active'
        self.focus_id = 'rogue-setting:ai' if active else 'rogue-difficulty:'+self.rogue_settings_draft['difficulty']

    def rogue_settings_items(self):
        settings = self.rogue_settings_draft
        active = (self.rogue_run or {}).get('status') == 'active'
        rows = [self._item('rogue-settings-note', 'text', 268, 164, 940, 62,
                           'Difficulty is fixed for this run.' if active else 'Choose the difficulty for your next run.',
                           value='Each difficulty keeps its own XP and records. Achievements are shared.', disabled=True)]
        for index, difficulty in enumerate(rogue_difficulty.DIFFICULTIES):
            rows.append(self._item('rogue-difficulty:'+difficulty, 'button', 268+index*480, 246, 460, 54,
                                   rogue_difficulty.label(difficulty), primary=settings['difficulty'] == difficulty,
                                   disabled=active or self.rogue_setting_edit is not None))
        for index, (key, title, limits) in enumerate((('ai', 'Opponent AI', '50–100%'),
                                                     ('aggression', 'Aggression', '0–100%'))):
            editing = self.rogue_setting_edit is not None and self.rogue_setting_edit['key'] == key
            rows.append(self._item('rogue-setting:'+key, 'setting', 268+index*480, 326, 460, 88,
                                   title, value=str(settings[key])+'%', subtitle=limits,
                                   editable=True, editing=editing))
        rows += [self._item('rogue-settings-scope', 'text', 268, 508, 940, 60,
                            'Opponent settings apply to the next generated challenge.',
                            value='The fixed challenge stays unchanged. Local / AI generation is a separate choice.', disabled=True),
                 self._item('rogue-settings-hint', 'text', 268, 578, 940, 24,
                            'Arrows adjust / L2-R2 ±10 / A confirms value / B cancels value' if self.rogue_setting_edit else
                            'A / Enter edits a value. Apply saves only Rogue settings.', scale=1.3, disabled=True),
                 self._item('rogue-settings-apply', 'button', 268, 618, 460, 48, 'Apply', primary=True,
                            disabled=self.rogue_setting_edit is not None),
                 self._item('rogue-settings-cancel', 'button', 748, 618, 460, 48, 'Cancel')]
        return rows

    def rogue_settings_action(self, action):
        if self.overlay != 'rogue-settings':
            return False
        edit = self.rogue_setting_edit
        if edit is not None:
            if action in ('accept', 'back'):
                if action == 'back':
                    self.rogue_settings_draft[edit['key']] = edit['before']
                self.rogue_setting_edit = None
                return True
            if action in ('left', 'right', 'up', 'down', 'page_up', 'page_down'):
                delta = -1 if action in ('left', 'down', 'page_up') else 1
                if action in ('page_up', 'page_down'):
                    delta *= 10
                key = edit['key']
                low = rogue_difficulty.MIN_AI if key == 'ai' else 0
                self.rogue_settings_draft[key] = max(low, min(100, self.rogue_settings_draft[key]+delta))
                return True
            if isinstance(action, tuple) and action[0] == 'click':
                _, x, y = action
                field = next(row for row in self.rogue_settings_items() if row['id'] == 'rogue-setting:'+edit['key'])
                if field['x'] <= x < field['x']+field['w'] and field['y'] <= y < field['y']+field['h']:
                    left = field['x']+int(field['w']*.56)
                    if left <= x < left+35:
                        return self.rogue_settings_action('left')
                    if x >= field['x']+field['w']-35:
                        return self.rogue_settings_action('right')
                    return self.rogue_settings_action('accept')
                if 1120 <= x < 1230 and 98 <= y < 136:
                    self.rogue_settings_action('back')
                    return True
                cancel = next(row for row in self.rogue_settings_items() if row['id'] == 'rogue-settings-cancel')
                if cancel['x'] <= x < cancel['x']+cancel['w'] and cancel['y'] <= y < cancel['y']+cancel['h']:
                    self.rogue_activate('rogue-settings-cancel')
                return True
            return True
        if action == 'back':
            self.rogue_activate('rogue-settings-cancel')
            return True
        return False

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
        profile = self.rogue_progress_profile()
        album = rogue.album_profile(self.rogue_state.get('profile', {}))
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
                     self._item('rogue-settings', 'button', 248, 112, 180, 40,
                                'Rogue settings', disabled=not available or pending)]
            settings = self.rogue_preferences()
            rows.append(self._item('rogue-difficulty', 'text', 248, 230, 592, 24,
                                   rogue_difficulty.label(settings['difficulty'])+
                                   f" / Starting spare lives: {rogue_difficulty.initial_lives(settings['difficulty'])}",
                                   scale=1.5, disabled=True))
            title = 'Run ended. Your XP and stickers remain.' if run else 'One challenge. One more event.'
            rows += [self._item('rogue-intro', 'text', 248, 316, 990, 110, title,
                                value='Complete races, hotlaps and points challenges to grow your run and discover hidden badges.',
                                disabled=True),
                     self._item('rogue-rules', 'text', 248, 414, 990, 114,
                                'Your car and circuit stay locked for the current event.',
                                value='Daylight events / 08:00–16:00. Local / AI generation is separate from opponent difficulty.',
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
                     self._item('rogue-reset', 'button', 1082, 622, 166, 42, 'Reset run', disabled=not available),
                     self._item('rogue-settings', 'button', 248, 112, 180, 40, 'Rogue settings',
                                disabled=not available or pending),
                     self._item('rogue-difficulty', 'text', 444, 106, 600, 24,
                                rogue_difficulty.label(run.get('difficulty', 'normal')), scale=1.5, disabled=True),
                     self._item('rogue-stage', 'text', 248, 164, 592, 24,
                                f"Challenge {proposal['stage'] if proposal else rogue.stage(run)}   /   Spare lives {run['lives']}",
                                color=(218, 216, 208), scale=1.6, disabled=True)]
            if proposal:
                rows.append(self._item('rogue-skip', 'button', 700, 622, 366, 42, 'Skip event / 1 life',
                                       disabled=not available or pending or run['lives'] == 0))
                mode = proposal['selection']['mode']
                duration = (rogue_duration.label(proposal.get('duration')) if mode == 2 else
                            'Complete a valid lap and exit; your best lap decides.' if mode == 1 else
                            'End the session to record your points.')
                rows.append(self._item('rogue-duration', 'text', 444, 134, 600, 24,
                                       duration, scale=1.2, disabled=True))
                chosen = proposal['selection']
                rows.append(self._item('rogue-objective', 'rogue-objective', 248, 216, 596, 62,
                                       rogue.objective_label(proposal), scale=3.7 if mode == 2 else 2.5,
                                       disabled=True))
                for card in self._cards(chosen):
                    car = card['id'] == 'car'
                    card.update(id='rogue-car' if car else 'rogue-track', x=248 if car else 756,
                                y=296, w=492, h=190, synthesis_card=True, disabled=True)
                    rows.append(card)
                car_row = dict(id=chosen['car'])
                rows.append(self._item('rogue-favorite', 'button', 248, 494, 240, 34,
                                       'Remove from favorites' if chosen['car'] in self.favorite_cars else 'Add to favorites',
                                       disabled=self.session_running))
                rows.append(self._blacklist_button(car_row, rogue=True, kind='cars'))
                track_row = dict(id=chosen['track'], layout=chosen.get('layout', ''))
                rows.append(self._item('rogue-track-favorite', 'button', 756, 494, 240, 34,
                                       'Remove from favorites' if (track_row['id'], track_row['layout']) in self.favorite_tracks else 'Add to favorites',
                                       disabled=self.session_running))
                rows.append(self._blacklist_button(track_row, rogue=True, kind='tracks'))
                minutes = chosen['time_minutes']
                conditions = (f"{chosen['laps']} {'lap' if chosen['laps'] == 1 else 'laps'}   /   {chosen['opponents']} opponents   /   AI {chosen['ai']}%   /   Aggression {chosen.get('ai_aggression', 0)}%"
                              if mode == 2 else content.MODES[mode][0]+'   /   Solo')
                rows.append(self._item('rogue-conditions', 'rogue-conditions', 248, 550, 1000, 30,
                                       f"{conditions}   /   {minutes//60:02}:{minutes%60:02}   /   {chosen['weather'].replace('_', ' ').title()}",
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
        rows.append(self._item('rogue-run-stats', 'text', 248, 188 if active else 266, 592, 24,
                               f"Wins {(run or {}).get('wins', 0)}   /   Win streak {(run or {}).get('streak', 0)}",
                               color=(218, 216, 208), scale=1.6, disabled=True))
        rows += self.rogue_latest_achievement_items(available)
        if not active or not run.get('challenge'):
            rows.append(self._item('rogue-profile', 'text', 248, 572 if active else 610,
                                   990, 40,
                                   f"Total car XP {self._rogue_total(profile.get('car_xp', {}))} / Best run {profile.get('best_wins', 0)} wins",
                                   value=f"Achievements: {len(album.get('badges', []))+len(album.get('stickers', []))} / 11", disabled=True))
        if self.rogue_last_result is not None:
            rows.append(self._item('rogue-last-result', 'button', 1068, 104, 180, 40, 'Last result', disabled=pending))
        rows.append(self._item('rogue-restart-note', 'text', 248, 668, 1000, 16,
                               'Restarts are free / No life, XP or streak penalty.',
                               scale=1.2, disabled=True))
        return rows

    def rogue_overlay_items(self):
        if self.overlay == 'rogue-settings':
            return self.rogue_settings_items()
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
        if self.blacklist_error:
            self.message = 'Blacklist unavailable. Recover it in the catalogue.'
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
        if self.blacklist_error:
            self.message = 'Blacklist unavailable. Recover it in the catalogue.'
            return False
        blocked = tuple(self.blacklist['cars'])
        blocked_tracks = deepcopy(self.blacklist['tracks'])
        snapshot = deepcopy(run)
        profile = deepcopy(self.rogue_state['profile'])
        timings = rogue_duration.load(self.synthesis_store)
        if run['mode'] != 'ai':
            try:
                proposal, catalog = rogue_generator.generate(self.game, snapshot, profile, catalog=self.catalog, timings=timings, blocked=blocked, blocked_tracks=blocked_tracks)
                self.rogue_store.set_challenge(proposal)
                self.replace_catalog(catalog)
                self.message = 'Rogue challenge ready. Finish the target position or better.'
                self.focus_id = 'start'
                return True
            except (OSError, ValueError, RuntimeError, TypeError):
                self.message = 'Could not prepare this Rogue challenge. Run kept; check installed content and blacklist.'
                return False
        if self.ai_pending is not None:
            self.message = 'Wait for the Race Synthetizer request before generating with AI.'
            return False
        future = Future()
        self.rogue_pending = dict(future=future, run_id=run['id'], stage=rogue.stage(run))
        self.rogue_result = None
        key, effort, catalog, game = self.api_key, self.ai_effort, deepcopy(self.catalog), self.game
        def work():
            try:
                future.set_result(rogue_generator.generate(game, snapshot, profile,
                                                          catalog=catalog, api_key=key, effort=effort, timings=timings, blocked=blocked, blocked_tracks=blocked_tracks))
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
        if self.overlay == 'rogue-settings' and identity == 'close':
            identity = 'rogue-settings-cancel'
        if self.rogue_result_activate(identity):
            return True
        if self.rogue_album_activate(identity):
            return True
        if not identity.startswith('rogue-'):
            return False
        if identity == 'rogue-settings':
            self.open_rogue_settings()
        elif self.overlay == 'rogue-settings' and identity.startswith('rogue-difficulty:'):
            difficulty = identity.split(':', 1)[1]
            if ((self.rogue_run or {}).get('status') != 'active' and self.rogue_setting_edit is None
                    and difficulty in rogue_difficulty.DIFFICULTIES
                    and difficulty != self.rogue_settings_draft['difficulty']):
                self.rogue_settings_draft = rogue_difficulty.preset(difficulty)
        elif self.overlay == 'rogue-settings' and identity.startswith('rogue-setting:'):
            key = identity.split(':', 1)[1]
            if key in ('ai', 'aggression') and self.rogue_setting_edit is None:
                self.rogue_setting_edit = dict(key=key, before=self.rogue_settings_draft[key])
        elif self.overlay == 'rogue-settings' and identity in ('rogue-settings-apply', 'rogue-settings-cancel'):
            if identity == 'rogue-settings-apply':
                if self.rogue_setting_edit is not None or self.session_running or self.rogue_pending is not None:
                    return True
                try:
                    self.rogue_store.set_settings(self.rogue_settings_draft)
                except (OSError, ValueError, RuntimeError, TypeError):
                    self.message = 'Could not save Rogue settings. Previous values kept.'
                    return True
                self.message = 'Rogue settings saved. Opponent changes apply to the next generated challenge.'
            self.rogue_settings_draft = self.rogue_setting_edit = None
            self._close_overlay()
        elif identity in ('rogue-favorite', 'rogue-track-favorite'):
            run = self.rogue_run or {}
            proposal = run.get('challenge')
            if proposal and not self.session_running:
                if self.favorites_error:
                    self.message = 'Favorites unavailable. Recover them in the catalogue.'
                else:
                    selected = proposal['selection']
                    kind = 'tracks' if identity == 'rogue-track-favorite' else 'cars'
                    row = dict(id=selected['track'], layout=selected.get('layout', '')) if kind == 'tracks' else dict(id=selected['car'])
                    changed = favorites.toggle(self.favorites, kind, row)
                    try:
                        if self.favorites_path is not None:changed=favorites.save(self.favorites_path, changed)
                    except (OSError, ValueError, RuntimeError, TypeError):
                        self.message='Could not save favorites. Previous favorite kept.'
                        return True
                    self._set_favorites(changed)
                    self.favorites_revision+=1
                    self.message='Favorite saved.' if favorites.contains(changed,kind,row) else 'Favorite removed.'
        elif identity in ('rogue-blacklist', 'rogue-track-blacklist'):
            run = self.rogue_run or {}
            proposal = run.get('challenge')
            if proposal and not self.session_running:
                selected = proposal['selection']
                if identity == 'rogue-track-blacklist':
                    self._toggle_blacklist(dict(id=selected['track'],layout=selected.get('layout','')),kind='tracks')
                else:
                    self._toggle_blacklist(dict(id=selected['car']),kind='cars')
        elif identity == 'rogue-new-local':
            self.new_rogue_run('deterministic')
        elif identity == 'rogue-new-ai':
            self.new_rogue_run('ai')
        elif identity == 'rogue-next':
            self.generate_rogue_challenge()
        elif identity == 'rogue-skip':
            run = self.rogue_run or {}
            proposal = run.get('challenge')
            if (not self.session_running and self.rogue_pending is None and not self.rogue_error
                    and self.rogue_store is not None and run.get('status') == 'active'
                    and proposal and run.get('lives', 0) > 0):
                try:
                    self.rogue_store.skip_challenge(run['id'], proposal['challenge_id'])
                except (OSError, ValueError, RuntimeError, TypeError):
                    self.refresh_rogue(announce=False)
                    self.message = 'Could not skip this event. Check the current Rogue data.'
                    return True
                self.rogue_result = self.rogue_last_result = None
                self.message = 'Event skipped. One spare life used. Choose the next challenge.'
                self.focus_id = 'rogue-next'
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
