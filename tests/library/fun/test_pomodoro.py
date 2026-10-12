import unittest
from datetime import date

from library.fun.pomodoro import Phase, Pomodoro


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.day = date(2026, 10, 12)

    def __call__(self) -> float:
        return self.now


def new_pomodoro(clock: FakeClock, changes: list) -> Pomodoro:
    return Pomodoro(focus_s=25, short_break_s=5, long_break_s=15, rounds=2,
                    on_phase_change=lambda old, new: changes.append((old, new)),
                    clock=clock, today=lambda: clock.day)


class TestPomodoro(unittest.TestCase):
    def test_full_cycle(self):
        clock, changes = FakeClock(), []
        pomodoro = new_pomodoro(clock, changes)
        self.assertEqual(pomodoro.state().phase, Phase.IDLE)

        pomodoro.start()
        state = pomodoro.state()
        self.assertEqual((state.phase, state.remaining, state.round_in_cycle), (Phase.FOCUS, 25, 1))

        clock.now += 10
        pomodoro.tick()
        self.assertEqual(pomodoro.state().remaining, 15)
        self.assertAlmostEqual(pomodoro.state().progress, 0.4)

        clock.now += 15
        pomodoro.tick()
        state = pomodoro.state()
        self.assertEqual((state.phase, state.completed_today, state.round_in_cycle), (Phase.SHORT_BREAK, 1, 2))

        clock.now += 5
        pomodoro.tick()
        self.assertEqual(pomodoro.state().phase, Phase.FOCUS)

        clock.now += 25
        pomodoro.tick()
        state = pomodoro.state()
        self.assertEqual((state.phase, state.completed_today, state.round_in_cycle), (Phase.LONG_BREAK, 2, 1))

        clock.now += 15
        pomodoro.tick()
        self.assertEqual(pomodoro.state().phase, Phase.FOCUS)
        self.assertEqual(changes, [(Phase.FOCUS, Phase.SHORT_BREAK), (Phase.SHORT_BREAK, Phase.FOCUS),
                                   (Phase.FOCUS, Phase.LONG_BREAK), (Phase.LONG_BREAK, Phase.FOCUS)])

    def test_pause_freezes_remaining_time(self):
        clock, changes = FakeClock(), []
        pomodoro = new_pomodoro(clock, changes)
        pomodoro.start()
        clock.now += 10
        pomodoro.pause()
        clock.now += 1000
        pomodoro.tick()
        state = pomodoro.state()
        self.assertEqual((state.phase, state.paused, state.remaining), (Phase.FOCUS, True, 15))

        pomodoro.resume()
        clock.now += 15
        pomodoro.tick()
        self.assertEqual(pomodoro.state().phase, Phase.SHORT_BREAK)

    def test_skipped_focus_is_not_counted(self):
        clock, changes = FakeClock(), []
        pomodoro = new_pomodoro(clock, changes)
        pomodoro.start()
        pomodoro.skip()
        state = pomodoro.state()
        self.assertEqual((state.phase, state.completed_today), (Phase.SHORT_BREAK, 0))
        self.assertEqual(changes, [(Phase.FOCUS, Phase.SHORT_BREAK)])

    def test_stop_and_counter_reset_on_new_day(self):
        clock, changes = FakeClock(), []
        pomodoro = new_pomodoro(clock, changes)
        pomodoro.start()
        clock.now += 25
        pomodoro.tick()
        self.assertEqual(pomodoro.state().completed_today, 1)

        pomodoro.stop()
        self.assertEqual(pomodoro.state().phase, Phase.IDLE)

        clock.day = date(2026, 10, 13)
        self.assertEqual(pomodoro.state().completed_today, 0)


if __name__ == '__main__':
    unittest.main()
