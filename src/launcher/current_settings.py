"""Read settings owned by the game when the launcher has no explicit choice."""
import configparser
from decimal import Decimal, DecimalException
from pathlib import Path

from . import content, controls, gamepad_fx


def _read(path):
    try:
        return content.read_ini(path) if path.is_file() else None
    except (OSError, ValueError, RuntimeError, configparser.Error):
        return None


def _number(ini, section, key, scale):
    if ini is None:
        return None
    try:
        value = Decimal(ini.get(section, key))*scale
    except (ValueError, TypeError, LookupError, configparser.Error, DecimalException):
        return None
    return value if value.is_finite() and abs(value) <= 1000000 else None


def read(cfg, base_cfg=None, csp_roots=(), *, aga_supported=True):
    cfg = Path(cfg)
    def native(name):
        path = cfg/name
        if not path.exists() and base_cfg is not None:
            path = Path(base_cfg)/name
        return _read(path)

    result = {}
    ini = native('controls.ini')
    for key, (field, _) in controls.FIELDS.items():
        result[key] = _number(ini, 'X360', field, 100)
    result['steer_gamma_tenths'] = _number(ini, 'X360', 'STEER_GAMMA', 10)
    result['car_damage_pct'] = _number(native('assists.ini'), 'ASSISTS', 'DAMAGE', 1)
    video = native('video.ini')
    result['pp_filter'] = video.get('POST_PROCESS', 'FILTER', fallback=None) if video else None

    # The CSP app records only values witnessed in a running AGA session.
    snapshots = []
    for root in csp_roots if aga_supported else ():
        path = Path(root)/gamepad_fx.SNAPSHOT
        try:
            if path.is_file():
                snapshots.append((path.stat().st_mtime_ns, path))
        except OSError:
            continue
    ini = _read(max(snapshots)[1]) if snapshots else None
    if (ini is not None and ini.get('AGA', 'OWNER', fallback='') == 'ac-deck'
            and ini.get('AGA', 'VERSION', fallback='') == gamepad_fx.AGA_VERSION):
        enabled = ini.get('AGA', 'ASSISTENABLED', fallback='')
        result['aga_enabled'] = {'1':'on', '0':'off'}.get(enabled)
    return result
