"""Reconcile settings explicitly edited by the CSP app during a session."""
import configparser
import re
from pathlib import Path

from . import content, file_io as safe, proximity_alert


def read_edits(roots, handled_token=None, *, strict=False):
    def invalid():
        if strict:
            raise ValueError('Proximity app settings could not be reconciled; preserve the existing files')
        return {}

    candidates = []
    for root in roots:
        path = Path(root)/proximity_alert.CONFIG
        try:
            safe.check_components(path)
            if not path.exists():
                continue
            safe.require_reference(path.lstat(), path)
            ini = content.read_ini(path)
            if ini.get('SETTINGS', 'EDITED', fallback='0') != '1':
                continue
            token = ini.get('SETTINGS', 'SESSION_TOKEN', fallback='')
            if not re.fullmatch(r'[0-9a-f]{32}', token):
                return invalid()
            enabled = ini.get('SETTINGS', 'ENABLED', fallback='')
            lateral = ini.get('SETTINGS', 'LATERAL_RANGE', fallback='')
            rear = ini.get('SETTINGS', 'REAR_RANGE', fallback='')
            if enabled not in ('0', '1') or not lateral.isdecimal() or not rear.isdecimal():
                return invalid()
            values = {'proximity_alert': enabled == '1', 'proximity_lateral_range': int(lateral),
                      'proximity_rear_range': int(rear), 'proximity_handled_session': token}
            proximity_alert.validate(values)
            candidates.append(values)
        except (OSError, ValueError, RuntimeError, configparser.Error):
            return invalid()
    if not candidates:
        return {}
    if any(item != candidates[0] for item in candidates[1:]):
        return invalid()
    return {} if candidates[0]['proximity_handled_session'] == handled_token else candidates[0]
