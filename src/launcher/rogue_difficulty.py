"""Rogue presets and independent opponent settings."""
from copy import deepcopy
import math

MIN_AI, MAX_AI = 50, 100
MAX_RACE_TARGET = 3
DIFFICULTIES = ('normal', 'easy')
_PRESETS = {
    'normal': dict(label='Hurt me plenty', ai=80, aggression=0, lives=1),
    'easy': dict(label="I'm too young to die", ai=60, aggression=0, lives=2),
}


def label(difficulty):
    if not isinstance(difficulty, str) or difficulty not in _PRESETS:
        raise ValueError('Invalid Rogue difficulty.')
    return _PRESETS[difficulty]['label']


def preset(difficulty='normal'):
    label(difficulty)
    values = _PRESETS[difficulty]
    return dict(difficulty=difficulty, ai=values['ai'], aggression=values['aggression'])


def clean_settings(value=None):
    if value is None:
        return preset()
    if not isinstance(value, dict) or set(value) != {'difficulty', 'ai', 'aggression'}:
        raise ValueError('Invalid Rogue settings.')
    label(value['difficulty'])
    if type(value['ai']) is not int or not MIN_AI <= value['ai'] <= MAX_AI:
        raise ValueError('Rogue opponent AI must be between 50 and 100.')
    if type(value['aggression']) is not int or not 0 <= value['aggression'] <= 100:
        raise ValueError('Rogue aggression must be between 0 and 100.')
    return deepcopy(value)


def run_settings(run):
    values = run.get('settings')
    if values is None:
        values = preset(run.get('difficulty', 'normal'))
        values['ai'] = run.get('base', {}).get('ai', values['ai'])
    values = clean_settings(values)
    if run.get('difficulty', values['difficulty']) != values['difficulty']:
        raise ValueError('Rogue run difficulty differs from its settings.')
    return values


def initial_lives(difficulty):
    label(difficulty)
    return _PRESETS[difficulty]['lives']


def race_target(target, grid, difficulty):
    label(difficulty)
    if difficulty == 'easy':
        target += math.ceil(grid / 4)
    return min(grid, MAX_RACE_TARGET, target)


def solo_target(target, mode, difficulty):
    label(difficulty)
    if difficulty != 'easy':
        return target
    if mode == 1:
        return min(2147483647, (target * 115 + 99) // 100)
    return max(1, target * (75 if mode == 3 else 60) // 100)
