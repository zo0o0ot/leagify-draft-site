"""
Unit tests for get_leagify_points().

Validates the Python port matches the original C# scoring logic.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scoring import get_leagify_points


class TestRound1:
    def test_first_overall(self):
        assert get_leagify_points(1, 1, False) == 40

    def test_first_overall_traded(self):
        assert get_leagify_points(1, 1, True) == 50

    def test_picks_2_through_10(self):
        for pick in range(2, 11):
            assert get_leagify_points(1, pick, False) == 35, f"Pick {pick} failed"

    def test_picks_2_through_10_traded(self):
        for pick in range(2, 11):
            assert get_leagify_points(1, pick, True) == 45, f"Pick {pick} failed"

    def test_picks_11_through_20(self):
        for pick in range(11, 21):
            assert get_leagify_points(1, pick, False) == 30, f"Pick {pick} failed"

    def test_picks_11_through_20_traded(self):
        for pick in range(11, 21):
            assert get_leagify_points(1, pick, True) == 40, f"Pick {pick} failed"

    def test_picks_21_through_32(self):
        for pick in range(21, 33):
            assert get_leagify_points(1, pick, False) == 25, f"Pick {pick} failed"

    def test_picks_21_through_32_traded(self):
        for pick in range(21, 33):
            assert get_leagify_points(1, pick, True) == 35, f"Pick {pick} failed"


class TestRound2:
    def test_picks_1_through_16(self):
        for pick in range(1, 17):
            assert get_leagify_points(2, pick, False) == 20, f"Pick {pick} failed"

    def test_picks_1_through_16_traded(self):
        for pick in range(1, 17):
            assert get_leagify_points(2, pick, True) == 30, f"Pick {pick} failed"

    def test_picks_17_and_above(self):
        for pick in range(17, 50):
            assert get_leagify_points(2, pick, False) == 15, f"Pick {pick} failed"

    def test_picks_17_and_above_traded(self):
        for pick in range(17, 50):
            assert get_leagify_points(2, pick, True) == 25, f"Pick {pick} failed"


class TestRounds3Through7:
    def test_round_3(self):
        assert get_leagify_points(3, 1, False) == 10

    def test_round_3_traded(self):
        assert get_leagify_points(3, 1, True) == 20

    def test_round_4(self):
        assert get_leagify_points(4, 1, False) == 8

    def test_round_4_traded(self):
        assert get_leagify_points(4, 1, True) == 18

    def test_round_5(self):
        assert get_leagify_points(5, 1, False) == 7

    def test_round_5_traded(self):
        assert get_leagify_points(5, 1, True) == 17

    def test_round_6(self):
        assert get_leagify_points(6, 1, False) == 6

    def test_round_6_traded(self):
        assert get_leagify_points(6, 1, True) == 16

    def test_round_7(self):
        assert get_leagify_points(7, 1, False) == 5

    def test_round_7_traded(self):
        assert get_leagify_points(7, 1, True) == 15

    def test_invalid_round(self):
        assert get_leagify_points(8, 1, False) == 0
