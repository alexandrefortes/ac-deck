"""Álbum paginado e domínio cosmético Rogue; nenhuma ação esportiva."""
from pathlib import Path
import sys

from . import rogue_rewards


PAGE_SIZE = 6


def album_asset_root():
    root = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
            else Path(__file__).resolve().parents[2])
    return root/'assets/rogue-album'


class RogueRewardsUI:
    def init_rogue_rewards(self):
        self.rogue_album_page = 0
        self.rogue_album_detail = None
        self._rogue_album_images = {}
        self.rogue_profile_reset_error = False

    def can_reset_rogue_profile(self):
        return (self.rogue_store is not None and not self.rogue_error
                and not self.session_running and self.rogue_pending is None)

    def rogue_album_entries(self):
        profile = self.rogue_state.get('profile', {})
        return rogue_rewards.album_entries(profile, owned=profile.get('stickers', ()),
                                            badges=profile.get('badges', ()))

    def rogue_album_image(self, entry):
        # Unknown badges never resolve an identity, image or hidden condition.
        if entry['secret'] or not entry['unlocked']:
            return None
        root = album_asset_root()
        key = (str(root), entry['id'])
        if key not in self._rogue_album_images:
            try:
                self._rogue_album_images[key] = rogue_rewards.asset_path(root, entry['id'])
            except (OSError, ValueError, RuntimeError, KeyError):
                self._rogue_album_images[key] = None
        return self._rogue_album_images[key]

    def open_rogue_album(self):
        self.refresh_rogue(announce=False)
        self.rogue_album_page = 0
        self.rogue_album_detail = None
        self._rogue_album_images.clear()
        self._open('rogue-album', 'Achievements')
        if self.rogue_album_entries():
            self.focus_id = 'rogue-reward:0'

    def rogue_album_items(self):
        entries = self.rogue_album_entries()
        pages = max(1, (len(entries)+PAGE_SIZE-1)//PAGE_SIZE)
        self.rogue_album_page = max(0, min(self.rogue_album_page, pages-1))
        page = self.rogue_album_page
        discovered = sum(entry['unlocked'] for entry in entries)
        rows = [self._item('rogue-album-note', 'text', 268, 166, 340, 38,
                           f'{discovered} / {len(entries)} discoveries / permanent rewards', disabled=True),
                self._item('rogue-profile-reset', 'button', 624, 162, 200, 42,
                           'Reset profile', disabled=not self.can_reset_rogue_profile()),
                self._item('rogue-album-prev', 'button', 852, 162, 164, 42, 'Previous', disabled=page == 0),
                self._item('rogue-album-next', 'button', 1032, 162, 176, 42, 'Next', disabled=page+1 >= pages)]
        for offset, entry in enumerate(entries[page*PAGE_SIZE:(page+1)*PAGE_SIZE]):
            index = page*PAGE_SIZE+offset
            progress = entry.get('progress')
            value = entry['description'] if entry['secret'] else entry['requirement']
            rows.append(self._item('rogue-reward:'+str(index),
                                   'rogue-badge' if entry['secret'] else 'rogue-sticker',
                                   268+(offset % 3)*322, 230+(offset//3)*204, 296, 188,
                                   entry['name'], value=value or '',
                                   album_card=True, earned=entry['unlocked'], secret=entry['secret'],
                                   image=self.rogue_album_image(entry), progress=progress,
                                   progress_label=progress['label'] if progress else None))
        rows.append(self._item('rogue-album-hint', 'text', 268, 648, 940, 28,
                               f'Page {page+1} / {pages} / LB-RB Pages / A Details / B Back', disabled=True))
        return rows

    def rogue_reward_detail_items(self):
        entries = self.rogue_album_entries()
        index = self.rogue_album_detail
        if type(index) is not int or not 0 <= index < len(entries):
            return []
        entry = entries[index]
        progress = entry.get('progress')
        status = 'Discovered / kept between runs' if entry['unlocked'] else 'Undiscovered'
        rows = [self._item('rogue-reward-title', 'text', 268, 164, 940, 46,
                           entry['name'], scale=2, disabled=True),
                self._item('rogue-reward-art', 'rogue-sticker', 268, 226, 300, 284, '',
                           image=self.rogue_album_image(entry), earned=entry['unlocked'],
                           secret=entry['secret'], art_only=True, disabled=True),
                self._item('rogue-reward-description', 'text', 600, 226, 608, 84,
                           status, value=entry['description'], disabled=True),
                self._item('rogue-reward-requirement', 'text', 600, 338, 608, 92,
                           'Discovery', value=entry['requirement'] or 'Keep driving to discover this badge.', disabled=True),
                self._item('rogue-reward-progress', 'text', 600, 454, 608, 56,
                           'Progress', value=progress['label'] if progress else
                           'Discovered' if entry['unlocked'] else 'Hidden until discovery', disabled=True)]
        quote = entry.get('quote') if entry['unlocked'] else None
        if quote:
            rows += [self._item('rogue-reward-quote', 'text', 268, 538, 940, 68,
                                '“'+quote['text']+'”', scale=1.4, disabled=True),
                     self._item('rogue-reward-attribution', 'text', 268, 616, 940, 52,
                                quote['author']+' / '+quote['work'],
                                value=quote['location']+' / Translation: '+quote['translator'],
                                scale=1.2, disabled=True)]
        else:
            if entry['secret']:
                reward_title = 'Badge discovery'
                reward_note = ('Grants +1 spare life once per run, up to a reserve of 3. Your achievements are kept after a run reset.'
                               if entry['unlocked'] else
                               'A hidden discovery awaits. Your permanent achievements is kept after a defeat or run reset.')
            else:
                reward_title = 'Cosmetic reward'
                reward_note = 'XP and achievements stay saved after a defeat or run reset. Stickers do not grant extra lives.'
            rows.append(self._item('rogue-reward-permanent', 'text', 268, 570, 940, 62,
                                   reward_title, value=reward_note, disabled=True))
        return rows

    def rogue_profile_reset_items(self):
        rows = [self._item('rogue-profile-reset-warning', 'text', 268, 204, 940, 112,
                           'All Rogue progress will be reset.',
                           value='XP, badges, stickers, the best-run record and the current run will be cleared.', disabled=True),
                self._item('rogue-profile-reset-backup', 'text', 268, 346, 940, 72,
                           'An existing profile is backed up locally first.',
                           value='Other events, settings and session history stay saved.', disabled=True),
                self._item('rogue-profile-reset-confirm', 'button', 268, 458, 420, 54,
                           'Reset profile', disabled=not self.can_reset_rogue_profile()),
                self._item('rogue-profile-reset-cancel', 'button', 708, 458, 420, 54,
                           'Keep profile', primary=True)]
        if self.rogue_profile_reset_error:
            rows.append(self._item('rogue-profile-reset-error', 'text', 268, 550, 940, 72,
                                   'Could not reset the Rogue profile.',
                                   value='Your profile is unchanged. Check local storage and try again.', disabled=True))
        return rows

    def rogue_album_back(self):
        if self.overlay == 'rogue-profile-reset':
            self.overlay = 'rogue-album'
            self.overlay_title = 'Achievements'
            self.focus_id = 'rogue-profile-reset'
            self.rogue_profile_reset_error = False
            return True
        if self.overlay != 'rogue-reward-detail':
            return False
        self.overlay = 'rogue-album'
        self.overlay_title = 'Achievements'
        self.focus_id = 'rogue-reward:'+str(self.rogue_album_detail)
        return True

    def rogue_album_activate(self, identity):
        if identity == 'close' and self.rogue_album_back():
            return True
        if identity == 'rogue-profile-reset':
            if self.overlay == 'rogue-album' and self.can_reset_rogue_profile():
                self.rogue_profile_reset_error = False
                self.overlay = 'rogue-profile-reset'
                self.overlay_title = 'Reset Rogue profile?'
                self.focus_id = 'rogue-profile-reset-cancel'
            return True
        if identity == 'rogue-profile-reset-cancel':
            if self.overlay == 'rogue-profile-reset':
                self.rogue_album_back()
            return True
        if identity == 'rogue-profile-reset-confirm':
            if self.overlay != 'rogue-profile-reset' or not self.can_reset_rogue_profile():
                return True
            try:
                self.rogue_store.reset_profile()
            except (OSError, ValueError, RuntimeError, TypeError):
                self.rogue_profile_reset_error = True
                self.focus_id = 'rogue-profile-reset-cancel'
                self.message = 'Could not reset the Rogue profile. Your profile is unchanged.'
                return True
            self._rogue_announced = None
            self.rogue_result = self.rogue_last_result = None
            self.rogue_album_page = 0
            self.rogue_album_detail = None
            self._rogue_album_images.clear()
            self.rogue_album_back()
            self.message = 'Rogue profile reset.'
            return True
        if self.overlay == 'rogue-album' and identity in ('rogue-album-prev', 'rogue-album-next'):
            self.rogue_album_page += -1 if identity.endswith('prev') else 1
            entries = self.rogue_album_entries()
            pages = max(1, (len(entries)+PAGE_SIZE-1)//PAGE_SIZE)
            self.rogue_album_page = max(0, min(self.rogue_album_page, pages-1))
            self.focus_id = 'rogue-reward:'+str(self.rogue_album_page*PAGE_SIZE)
            return True
        if self.overlay == 'rogue-album' and identity.startswith('rogue-reward:'):
            try:
                index = int(identity.split(':')[1])
            except (ValueError, IndexError):
                return True
            if 0 <= index < len(self.rogue_album_entries()):
                self.rogue_album_detail = index
                self.overlay = 'rogue-reward-detail'
                self.overlay_title = 'Achievement details'
                self.focus_id = 'close'
            return True
        return False

    def rogue_album_action(self, action):
        if self.overlay in ('rogue-reward-detail', 'rogue-profile-reset') and action == 'back':
            return self.rogue_album_back()
        if self.overlay == 'rogue-album' and action in ('tab_prev', 'page_up', 'tab_next', 'page_down'):
            self.rogue_album_activate('rogue-album-prev' if action in ('tab_prev', 'page_up') else 'rogue-album-next')
            return True
        return False

    def rogue_mastery_items(self, selection, profile):
        key = selection['track']+'|'+selection.get('layout', '')
        rows = []
        for identity, label, xp, x in (
                ('car', 'Car', profile.get('car_xp', {}).get(selection['car'], 0), 248),
                ('track', 'Circuit', profile.get('track_xp', {}).get(key, 0), 756)):
            level = rogue_rewards.mastery(xp)
            next_level = (f"{level['remaining_xp']} XP to level {level['level']+1}"
                          if level['next_xp'] is not None else 'Maximum level')
            rows.append(self._item('rogue-'+identity+'-mastery', 'rogue-mastery', x, 588, 492, 24,
                                   f"{label} / Level {level['level']} / {level['title']}",
                                   value=f"{xp} XP / {next_level}", compact_label=f"{label} / Lv {level['level']} / {xp} XP",
                                   disabled=True))
        return rows
