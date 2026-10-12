import unittest

from library.fun.pet import MAX_SPEED, MIN_SPEED, CpuPet

AREA_WIDTH = 330
FPS = 10.0


class TestCpuPet(unittest.TestCase):
    def test_step_per_frame_does_not_depend_on_frame_duration(self):
        # A frame that took 330 ms to send used to make the cat jump 3 times further than usual
        pet = CpuPet()
        steps = []
        for dt in (0.1, 0.1, 0.33, 0.1, 0.25, 0.1):
            x = pet.x
            pet.update(dt, 30.0, 45.0, AREA_WIDTH, FPS)
            steps.append(round(pet.x - x, 6))
        self.assertEqual(len(set(steps)), 1)

    def test_speed_follows_cpu_load_progressively(self):
        pet = CpuPet()
        pet.update(0.1, 5.0, 45.0, AREA_WIDTH, FPS)
        slow = pet.speed
        speeds = []
        for _ in range(30):  # 3 seconds at 30% CPU
            pet.update(0.1, 30.0, 45.0, AREA_WIDTH, FPS)
            speeds.append(pet.speed)
        self.assertGreater(speeds[0], slow)
        self.assertTrue(all(b > a for a, b in zip(speeds, speeds[1:])))
        jumps = [b - a for a, b in zip([slow] + speeds, speeds)]
        self.assertLess(max(jumps), (MAX_SPEED - MIN_SPEED) * 0.25 / 10)

    def test_no_flicker_between_sleep_and_run_around_threshold(self):
        pet = CpuPet()
        states = set()
        for i in range(100):
            pet.update(0.1, 2.0 if i % 2 else 5.0, 45.0, AREA_WIDTH, FPS)
            if i > 10:
                states.add(pet.sleeping)
        self.assertEqual(len(states), 1)

    def test_sleeps_when_idle_and_wakes_up_under_load(self):
        pet = CpuPet()
        for _ in range(50):
            pet.update(0.1, 1.0, 45.0, AREA_WIDTH, FPS)
        self.assertTrue(pet.sleeping)
        x = pet.x
        pet.update(0.1, 1.0, 45.0, AREA_WIDTH, FPS)
        self.assertEqual(pet.x, x)

        for _ in range(50):
            pet.update(0.1, 40.0, 45.0, AREA_WIDTH, FPS)
        self.assertFalse(pet.sleeping)

    def test_leg_cadence_is_regular(self):
        pet = CpuPet()
        changes = []
        for i in range(60):
            frame = pet.frame
            pet.update(0.1, 30.0, 45.0, AREA_WIDTH, FPS)
            if pet.frame != frame:
                changes.append(i)
        gaps = {b - a for a, b in zip(changes[10:], changes[11:])}
        self.assertLessEqual(max(gaps) - min(gaps), 1)


if __name__ == '__main__':
    unittest.main()
