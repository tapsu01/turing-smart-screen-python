import unittest

from PIL import Image, ImageDraw

from library.fun.frame_sender import FrameSender


class RecordingLcd:
    def __init__(self):
        self.calls = []

    def DisplayPILImage(self, image, x=0, y=0, image_width=0, image_height=0):
        self.calls.append((x, y, image.width, image.height))


def blank() -> Image.Image:
    return Image.new("RGB", (480, 320), (10, 20, 30))


def sender_after_first_frame(**kwargs):
    lcd = RecordingLcd()
    sender = FrameSender(lcd, **kwargs)
    sender.push(blank())
    lcd.calls.clear()
    return lcd, sender


class TestFrameSender(unittest.TestCase):
    def test_first_frame_is_sent_entirely(self):
        lcd = RecordingLcd()
        sender = FrameSender(lcd)
        self.assertEqual(sender.push(blank()), 480 * 320)
        self.assertEqual(lcd.calls, [(0, 0, 480, 320)])

    def test_identical_frame_sends_nothing(self):
        lcd, sender = sender_after_first_frame()
        self.assertEqual(sender.push(blank()), 0)
        self.assertEqual(lcd.calls, [])

    def test_far_apart_changes_on_the_same_rows_are_sent_separately(self):
        # Previously both changes shared one 330px wide rectangle: the clock second hand + seconds digits case
        lcd, sender = sender_after_first_frame()
        frame = blank()
        draw = ImageDraw.Draw(frame)
        draw.rectangle((100, 10, 109, 19), fill=(255, 0, 0))
        draw.rectangle((420, 12, 439, 21), fill=(0, 255, 0))
        sender.push(frame)
        self.assertEqual(lcd.calls, [(100, 10, 10, 10), (420, 12, 20, 10)])

    def test_sprite_across_tile_rows_is_sent_in_one_piece(self):
        # Previously a sprite crossing y=288 was sent as 2 consecutive updates: visibly torn
        lcd, sender = sender_after_first_frame()
        frame = blank()
        ImageDraw.Draw(frame).rectangle((50, 263, 139, 316), fill=(247, 160, 72))
        sender.push(frame)
        self.assertEqual(lcd.calls, [(50, 263, 90, 54)])

    def test_sparse_diagonal_is_not_sent_as_its_bounding_box(self):
        lcd, sender = sender_after_first_frame()
        frame = blank()
        ImageDraw.Draw(frame).line([(100, 40), (190, 130)], fill=(255, 255, 255), width=2)
        pixels = sender.push(frame)
        self.assertGreater(len(lcd.calls), 1)
        self.assertLess(pixels, 91 * 91 / 3)

    def test_priority_box_is_sent_first(self):
        lcd, sender = sender_after_first_frame(priority_box=(0, 256, 330, 320))
        frame = blank()
        draw = ImageDraw.Draw(frame)
        draw.rectangle((10, 10, 19, 19), fill=(255, 0, 0))
        draw.rectangle((60, 280, 79, 299), fill=(0, 255, 0))
        sender.push(frame)
        self.assertEqual(lcd.calls, [(60, 280, 20, 20), (10, 10, 10, 10)])

    def test_single_channel_change_is_detected(self):
        lcd, sender = sender_after_first_frame()
        frame = blank()
        frame.putpixel((5, 5), (10, 20, 31))
        sender.push(frame)
        self.assertEqual(lcd.calls, [(5, 5, 1, 1)])

    def test_invalidate_forces_full_frame(self):
        lcd, sender = sender_after_first_frame()
        sender.invalidate()
        sender.push(blank())
        self.assertEqual(lcd.calls, [(0, 0, 480, 320)])


if __name__ == '__main__':
    unittest.main()
