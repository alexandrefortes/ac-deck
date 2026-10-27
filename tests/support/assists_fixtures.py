"""Valores autorais sintéticos; não são recomendação nem perfil do jogador."""
from src.launcher.assists_config import AssistsSettings, AssistState


SYNTHETIC_ASSISTS = AssistsSettings(
    ideal_line=False,
    auto_blip=True,
    stability_control=7,
    auto_brake=False,
    auto_shifter=True,
    abs_state=AssistState.FACTORY,
    traction_control=AssistState.ON,
    auto_clutch=False,
    visual_damage=True,
    damage='72.5',
    fuel_consumption='1.25',
    tyre_wear_multiplier='0.75',
    tyre_blankets=True,
    slipstream_multiplier='1.125',
)

SYNTHETIC_ASSISTS_INI = (
    '[ASSISTS]\n'
    'IDEAL_LINE=0\n'
    'AUTO_BLIP=1\n'
    'STABILITY_CONTROL=7\n'
    'AUTO_BRAKE=0\n'
    'AUTO_SHIFTER=1\n'
    'ABS=1\n'
    'TRACTION_CONTROL=2\n'
    'AUTO_CLUTCH=0\n'
    'VISUALDAMAGE=1\n'
    'DAMAGE=72.5\n'
    'FUEL_RATE=1.25\n'
    'TYRE_WEAR=0.75\n'
    'TYRE_BLANKETS=1\n'
    'SLIPSTREAM=1.125\n'
)
