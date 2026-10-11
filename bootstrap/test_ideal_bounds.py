"""Zero-dependency theorem-reference smoke tests (stdlib unittest)."""
import math
import unittest

try:
    from ideal_bounds import BASES, log10_bound, min_length_for_target
except ImportError:
    from bootstrap.ideal_bounds import BASES, log10_bound, min_length_for_target

class BoundSmokeTests(unittest.TestCase):
    def test_wiesner_n1(self):
        self.assertAlmostEqual(10 ** log10_bound('W1', 1), 0.75)

    def test_ideal_models_distinct(self):
        self.assertNotEqual(BASES['W1'][0], BASES['S1'][0])

    def test_classical_verification_variant_is_distinct(self):
        self.assertGreater(BASES['W1_CLASSICAL_VARIANT'][0], BASES['W1'][0])

    def test_length_rounding(self):
        target = 1e-9
        for model, (b, _) in BASES.items():
            n = min_length_for_target(model, target)
            self.assertLessEqual(b**n, target * (1 + 1e-12))
            if n > 1:
                self.assertGreater(b**(n - 1), target)

    def test_bad_input_cannot_silently_certify(self):
        with self.assertRaises(ValueError):
            log10_bound('S2_NOISY', 64)
        with self.assertRaises(ValueError):
            log10_bound('W1', 0)
        for bad in [-1, 0, 1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                min_length_for_target('W1', bad)

if __name__ == '__main__':
    unittest.main()
