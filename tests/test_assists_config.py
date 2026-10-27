import configparser
from dataclasses import FrozenInstanceError, asdict, fields, replace
from decimal import Decimal, localcontext
import unittest
from unittest.mock import patch

from src.launcher.assists_config import AssistsSettings, AssistState, build_assists_ini
from tests.support.assists_fixtures import SYNTHETIC_ASSISTS, SYNTHETIC_ASSISTS_INI


class AssistsConfigTests(unittest.TestCase):
    def value(self, settings, key):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(build_assists_ini(settings))
        return parser['ASSISTS'][key]

    def test_fourteen_synthetic_fields_have_exact_keys_and_values(self):
        self.assertEqual(build_assists_ini(SYNTHETIC_ASSISTS), SYNTHETIC_ASSISTS_INI)
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(SYNTHETIC_ASSISTS_INI)
        self.assertEqual(parser.sections(), ['ASSISTS'])
        self.assertEqual(len(parser['ASSISTS']), 14)
        self.assertNotIn('VISUAL_DAMAGE', SYNTHETIC_ASSISTS_INI)

    def test_each_field_is_required_without_constructor_defaults(self):
        explicit = asdict(SYNTHETIC_ASSISTS)
        self.assertEqual(len(fields(AssistsSettings)), 14)
        for name in explicit:
            incomplete = {key: value for key, value in explicit.items() if key != name}
            with self.subTest(name=name), self.assertRaises(TypeError):
                AssistsSettings(**incomplete)
        with self.assertRaises(TypeError):
            AssistsSettings()

    def test_settings_are_immutable_and_not_mutated(self):
        before = asdict(SYNTHETIC_ASSISTS)
        build_assists_ini(SYNTHETIC_ASSISTS)
        self.assertEqual(asdict(SYNTHETIC_ASSISTS), before)
        with self.assertRaises(FrozenInstanceError):
            SYNTHETIC_ASSISTS.damage = '0'

    def test_missing_unknown_or_wrong_container_rejected(self):
        for value in (None, {}, asdict(SYNTHETIC_ASSISTS), SYNTHETIC_ASSISTS_INI, 0):
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                build_assists_ini(value)
        with self.assertRaises(TypeError):
            AssistsSettings(**asdict(SYNTHETIC_ASSISTS), unknown=True)

    def test_booleans_encode_zero_and_one_independently(self):
        mapping = {'ideal_line': 'IDEAL_LINE', 'auto_blip': 'AUTO_BLIP',
                   'auto_brake': 'AUTO_BRAKE', 'auto_shifter': 'AUTO_SHIFTER',
                   'auto_clutch': 'AUTO_CLUTCH', 'visual_damage': 'VISUALDAMAGE',
                   'tyre_blankets': 'TYRE_BLANKETS'}
        for name, key in mapping.items():
            for value in (False, True):
                with self.subTest(name=name, value=value):
                    self.assertEqual(self.value(replace(SYNTHETIC_ASSISTS, **{name: value}), key), str(int(value)))

    def test_boolean_fields_do_not_coerce_strings_numbers_or_none(self):
        names = ('ideal_line', 'auto_blip', 'auto_brake', 'auto_shifter',
                 'auto_clutch', 'visual_damage', 'tyre_blankets')
        for name in names:
            for value in (0, 1, '0', 'True', None, 1.0, AssistState.ON):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    build_assists_ini(replace(SYNTHETIC_ASSISTS, **{name: value}))

    def test_all_declared_assist_states_are_encoded_as_int32(self):
        self.assertEqual([int(s) for s in AssistState], [0, 1, 2])
        for state in AssistState:
            for name, key in (('abs_state', 'ABS'), ('traction_control', 'TRACTION_CONTROL')):
                with self.subTest(name=name, state=state):
                    self.assertEqual(self.value(replace(SYNTHETIC_ASSISTS, **{name: state}), key), str(int(state)))

    def test_enum_closure_is_explicit_prototype_policy(self):
        for name in ('abs_state', 'traction_control'):
            for value in (-1, 0, 1, 2, 3, True, 'Factory', None, 1.0):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    build_assists_ini(replace(SYNTHETIC_ASSISTS, **{name: value}))
        with self.assertRaises(ValueError):
            AssistState(3)

    def test_stability_control_int32_range_has_no_invented_percent_clamp(self):
        for value in (-(2**31), -1, 0, 100, 101, 2**31-1):
            with self.subTest(value=value):
                self.assertEqual(self.value(replace(SYNTHETIC_ASSISTS, stability_control=value), 'STABILITY_CONTROL'), str(value))

    def test_stability_control_rejects_bool_enum_and_non_int32(self):
        for value in (-(2**31)-1, 2**31, True, AssistState.ON, 1.0, '1', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_assists_ini(replace(SYNTHETIC_ASSISTS, stability_control=value))

    def test_all_double_fields_are_required_as_explicit_numeric_strings(self):
        for name in ('damage', 'fuel_consumption', 'tyre_wear_multiplier', 'slipstream_multiplier'):
            for value in (None, 0, 1, True, 1.25, Decimal('1.25')):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    build_assists_ini(replace(SYNTHETIC_ASSISTS, **{name: value}))

    def test_decimal_canonicalization_uses_no_locale_or_clr_oracle(self):
        cases = {'+001.2500': '1.25', '.50': '0.5', '1.': '1', '1e2': '100',
                 '1E-2': '0.01', '-1.25e1': '-12.5', '100': '100',
                 '-0': '0', '-0.000': '0', '0e999999': '0'}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(self.value(replace(SYNTHETIC_ASSISTS, damage=value), 'DAMAGE'), expected)

    def test_double_values_are_not_clamped_to_unproven_simulation_bounds(self):
        for name, key in (('damage', 'DAMAGE'), ('fuel_consumption', 'FUEL_RATE'),
                          ('tyre_wear_multiplier', 'TYRE_WEAR'), ('slipstream_multiplier', 'SLIPSTREAM')):
            for value in ('-1.5', '0', '0.125', '100.5', '1000'):
                with self.subTest(name=name, value=value):
                    self.assertEqual(self.value(replace(SYNTHETIC_ASSISTS, **{name: value}), key), value)

    def test_nonfinite_overflow_and_underflow_to_zero_rejected(self):
        for value in ('NaN', 'sNaN', 'Infinity', '-Infinity', '1e309', '-1e309', '1e-325', '-1e-325'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_assists_ini(replace(SYNTHETIC_ASSISTS, damage=value))

    def test_finite_double_extremes_remain_numeric(self):
        for value in ('1.7976931348623157e308', '-1.7976931348623157e308', '5e-324', '-5e-324'):
            with self.subTest(value=value):
                output = self.value(replace(SYNTHETIC_ASSISTS, damage=value), 'DAMAGE')
                self.assertEqual(Decimal(output), Decimal(value))
                self.assertNotIn('e', output.lower())

    def test_decimal_context_does_not_round_explicit_digits(self):
        value = '1.23456789012345678901234567890123456789'
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(self.value(replace(SYNTHETIC_ASSISTS, damage=value), 'DAMAGE'), value)

    def test_numeric_injection_non_ascii_whitespace_and_comma_rejected(self):
        for value in ('1,25', ' 1.25', '1.25 ', '1_000', '\u0661.25', '1\n[REMOTE]',
                      '1\rOTHER=2', '1;comment', '1\x00', '1\t', '', '1/2', '\u22121',
                      '1e', '+', '1.2.3', '1\u2028OTHER=2'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_assists_ini(replace(SYNTHETIC_ASSISTS, damage=value))

    def test_numeric_input_size_limit_is_prototype_policy(self):
        for value in ('0'*129, '1'+'0'*128, '0e'+'9'*127):
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                build_assists_ini(replace(SYNTHETIC_ASSISTS, damage=value))
        self.assertEqual(self.value(replace(SYNTHETIC_ASSISTS, damage='0'*128), 'DAMAGE'), '0')

    def test_output_is_deterministic_ascii_and_one_line_per_field(self):
        output = build_assists_ini(SYNTHETIC_ASSISTS)
        self.assertEqual(output, build_assists_ini(SYNTHETIC_ASSISTS))
        self.assertTrue(output.isascii())
        self.assertEqual(len(output.splitlines()), 15)
        self.assertNotIn('\r', output)
        self.assertTrue(output.endswith('\n'))

    def test_generator_performs_no_io_or_process_operations(self):
        with patch('builtins.open', side_effect=AssertionError('IO')), \
             patch('subprocess.Popen', side_effect=AssertionError('processo')), \
             patch('os.getenv', side_effect=AssertionError('ambiente')), \
             patch('locale.localeconv', side_effect=AssertionError('cultura')):
            self.assertEqual(build_assists_ini(SYNTHETIC_ASSISTS), SYNTHETIC_ASSISTS_INI)


if __name__ == '__main__':
    unittest.main()
