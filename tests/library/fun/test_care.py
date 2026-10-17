import tempfile
import unittest
from pathlib import Path

from library.fun.care import FOOD_EMPTY_S, JOY_EMPTY_S, PetCare


class TestPetCare(unittest.TestCase):
    def test_stats_go_down_at_their_own_pace(self):
        care = PetCare(food=100, joy=100)
        care.tick(FOOD_EMPTY_S / 2)
        state = care.state()
        self.assertAlmostEqual(state.food, 50)
        self.assertAlmostEqual(state.joy, 100 - 50 * FOOD_EMPTY_S / JOY_EMPTY_S)
        care.tick(FOOD_EMPTY_S)
        self.assertEqual(care.state().food, 0)
        self.assertEqual(care.state().joy, 0)
        self.assertTrue(care.state().hungry)
        self.assertTrue(care.state().sad)

    def test_feed_and_pet_are_capped(self):
        care = PetCare(food=70, joy=90)
        self.assertTrue(care.feed())
        self.assertEqual(care.state().food, 100)
        care.pet()
        self.assertEqual(care.state().joy, 100)

    def test_full_cat_refuses_food(self):
        care = PetCare(food=96, joy=50)
        self.assertFalse(care.feed())
        self.assertEqual(care.state().food, 96)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pet_state.json"
            PetCare(food=12.5, joy=64).save(path)
            care = PetCare.load(path)
            self.assertEqual((care.state().food, care.state().joy), (12.5, 64))

    def test_missing_or_broken_file_starts_again(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pet_state.json"
            self.assertEqual(PetCare.load(path).state(), PetCare().state())
            path.write_text("{not json")
            self.assertEqual(PetCare.load(path).state(), PetCare().state())


if __name__ == '__main__':
    unittest.main()
