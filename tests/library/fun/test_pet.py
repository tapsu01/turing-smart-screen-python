import unittest

from PIL import Image

from library.fun.costume import Costume
from library.fun.pet import MAX_SPEED, MIN_SPEED, Action, CpuPet

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

    def run_frames(self, pet: CpuPet, seconds: float, cpu_percent: float):
        for _ in range(round(seconds * FPS)):
            pet.update(1 / FPS, cpu_percent, 45.0, AREA_WIDTH, FPS)

    def test_startles_on_cpu_spike_then_runs_again(self):
        pet = CpuPet()
        self.run_frames(pet, 3, 10.0)
        pet.update(0.1, 80.0, 45.0, AREA_WIDTH, FPS)
        self.assertIs(pet.action, Action.STARTLE)
        x = pet.x
        self.run_frames(pet, 0.8, 80.0)
        self.assertEqual(pet.x, x)
        self.run_frames(pet, 0.5, 80.0)
        self.assertIsNone(pet.action)
        self.assertGreater(pet.x, x)

    def test_startle_has_cooldown(self):
        pet = CpuPet()
        startles = 0
        for cpu_percent in (10.0, 80.0, 10.0, 80.0):
            for _ in range(30):
                action = pet.action
                pet.update(0.1, cpu_percent, 45.0, AREA_WIDTH, FPS)
                startles += pet.action is Action.STARTLE and action is not Action.STARTLE
        self.assertEqual(startles, 1)

    def test_startle_wakes_up_from_a_nap(self):
        pet = CpuPet()
        self.run_frames(pet, 5, 1.0)
        self.assertTrue(pet.sleeping)
        pet.update(0.1, 60.0, 45.0, AREA_WIDTH, FPS)
        self.assertIs(pet.action, Action.STARTLE)
        self.assertFalse(pet.sleeping)

    def test_stretches_when_woken_up(self):
        pet = CpuPet()
        self.run_frames(pet, 1, 30.0)
        pet.force_sleep = True
        self.run_frames(pet, 1, 30.0)
        self.assertTrue(pet.sleeping)
        pet.force_sleep = False
        pet.update(0.1, 30.0, 45.0, AREA_WIDTH, FPS)
        self.assertIs(pet.action, Action.STRETCH)
        x = pet.x
        self.run_frames(pet, 1.3, 30.0)
        self.assertEqual(pet.x, x)
        self.run_frames(pet, 0.5, 30.0)
        self.assertGreater(pet.x, x)

    def test_forced_sleep_ignores_cpu_load(self):
        pet = CpuPet()
        self.run_frames(pet, 1, 10.0)
        pet.force_sleep = True
        self.run_frames(pet, 1, 90.0)
        self.assertTrue(pet.sleeping)
        self.assertIsNone(pet.action)

    def test_celebration_wakes_up_then_back_to_sleep(self):
        pet = CpuPet()
        pet.force_sleep = True
        self.run_frames(pet, 1, 30.0)
        pet.celebrate()
        self.run_frames(pet, 2.8, 30.0)
        self.assertFalse(pet.sleeping)
        self.run_frames(pet, 0.4, 30.0)
        self.assertTrue(pet.sleeping)

        pet.celebrate(big=True)
        self.run_frames(pet, 4.8, 30.0)
        self.assertIs(pet.action, Action.CELEBRATE)
        self.run_frames(pet, 0.4, 30.0)
        self.assertTrue(pet.sleeping)

    def test_requested_actions_are_played_at_next_update(self):
        pet = CpuPet()
        self.run_frames(pet, 1, 30.0)
        for action in (Action.STARTLE, Action.STRETCH):
            pet.request(action)
            self.assertIsNone(pet.action)
            pet.update(0.1, 30.0, 45.0, AREA_WIDTH, FPS)
            self.assertIs(pet.action, action)
            self.run_frames(pet, 2, 30.0)
        pet.request(Action.CELEBRATE, variant=True)
        pet.update(0.1, 30.0, 45.0, AREA_WIDTH, FPS)
        self.assertIs(pet.action, Action.CELEBRATE)
        self.assertTrue(pet.big_celebration)

    def test_requested_action_wakes_up_then_back_to_sleep(self):
        pet = CpuPet()
        pet.force_sleep = True
        self.run_frames(pet, 1, 30.0)
        pet.request(Action.STARTLE)
        pet.update(0.1, 30.0, 45.0, AREA_WIDTH, FPS)
        self.assertFalse(pet.sleeping)
        self.run_frames(pet, 1.2, 30.0)
        self.assertTrue(pet.sleeping)

    def test_disabled_reactions_are_not_played(self):
        pet = CpuPet()
        pet.startle_enabled = False
        pet.stretch_enabled = False
        self.run_frames(pet, 3, 10.0)
        pet.update(0.1, 80.0, 45.0, AREA_WIDTH, FPS)
        self.assertIsNone(pet.action)
        pet.force_sleep = True
        self.run_frames(pet, 1, 80.0)
        pet.force_sleep = False
        x = pet.x
        pet.update(0.1, 80.0, 45.0, AREA_WIDTH, FPS)
        self.assertIsNone(pet.action)
        self.assertGreater(pet.x, x)

    def test_draw_every_state_stays_in_box(self):
        box = (0, 10, AREA_WIDTH, 67)
        states = [dict(), dict(sad=True), dict(force_sleep=True), dict(action=Action.STARTLE),
                  dict(action=Action.STRETCH), dict(action=Action.CELEBRATE, variant=True),
                  dict(action=Action.EAT), dict(action=Action.EAT, variant=True), dict(action=Action.PURR)]
        for costume in Costume:
            for state in states:
                for x in (-90, 0, 120, 250, AREA_WIDTH):
                    for time in (0.1, 0.35, 0.6, 2.9):
                        pet = CpuPet()
                        pet.x, pet.time, pet.temperature = x, time, 90.0
                        pet.action_left, pet.action_duration, pet.costume = 1.0, 3.0, costume
                        for name, value in state.items():
                            setattr(pet, name, value)
                        img = Image.new("RGB", (400, 80), (0, 0, 0))
                        pet.draw(img, box)
                        outside = img.copy()
                        outside.paste((0, 0, 0), box)
                        self.assertIsNone(outside.getbbox(), f"{costume} {state} x={x} t={time}")

    def test_eat_and_purr_stand_still_for_their_duration(self):
        for action, duration in ((Action.EAT, 3.0), (Action.PURR, 2.5)):
            pet = CpuPet()
            self.run_frames(pet, 1, 30.0)
            pet.request(action)
            pet.update(0.1, 30.0, 45.0, AREA_WIDTH, FPS)
            x = pet.x
            self.run_frames(pet, duration - 0.3, 30.0)
            self.assertIs(pet.action, action)
            self.assertEqual(pet.x, x)
            self.run_frames(pet, 0.5, 30.0)
            self.assertIsNone(pet.action)

    def test_hungry_or_sad_cat_runs_slower(self):
        pet = CpuPet()
        pet.update(0.1, 50.0, 45.0, AREA_WIDTH, FPS)
        normal = pet.speed
        pet.hungry = True
        hungry = pet.speed
        pet.sad = True
        self.assertLess(hungry, normal)
        self.assertLess(pet.speed, hungry)

    def test_cpu_spike_does_not_interrupt_eating(self):
        pet = CpuPet()
        self.run_frames(pet, 3, 10.0)
        pet.request(Action.EAT)
        pet.update(0.1, 10.0, 45.0, AREA_WIDTH, FPS)
        pet.update(0.1, 90.0, 45.0, AREA_WIDTH, FPS)
        self.assertIs(pet.action, Action.EAT)


if __name__ == '__main__':
    unittest.main()
