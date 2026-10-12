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


class TestFrameSender(unittest.TestCase):
    def test_first_frame_is_sent_entirely(self):
        lcd = RecordingLcd()
        sender = FrameSender(lcd)
        self.assertEqual(sender.push(blank()), 480 * 320)
        self.assertEqual(lcd.calls, [(0, 0, 480, 320)])

    def test_identical_frame_sends_nothing(self):
        lcd = RecordingLcd()
        sender = FrameSender(lcd)
        sender.push(blank())
        lcd.calls.clear()
        self.assertEqual(sender.push(blank()), 0)
        self.assertEqual(lcd.calls, [])

    def test_only_changed_areas_are_sent(self):
        lcd = RecordingLcd()
        sender = FrameSender(lcd, band_height=32)
        sender.push(blank())
        lcd.calls.clear()

        frame = blank()
        draw = ImageDraw.Draw(frame)
        draw.rectangle((100, 10, 109, 19), fill=(255, 0, 0))  # inside band 0..31
        draw.rectangle((400, 300, 419, 309), fill=(0, 255, 0))  # inside band 288..319
        sender.push(frame)
        self.assertEqual(lcd.calls, [(100, 10, 10, 10), (400, 300, 20, 10)])

    def test_change_across_bands_is_split(self):
        lcd = RecordingLcd()
        sender = FrameSender(lcd, band_height=32)
        sender.push(blank())
        lcd.calls.clear()

        frame = blank()
        ImageDraw.Draw(frame).rectangle((0, 20, 9, 39), fill=(255, 255, 255))
        sender.push(frame)
        self.assertEqual(lcd.calls, [(0, 20, 10, 12), (0, 32, 10, 8)])

    def test_invalidate_forces_full_frame(self):
        lcd = RecordingLcd()
        sender = FrameSender(lcd)
        sender.push(blank())
        sender.invalidate()
        lcd.calls.clear()
        sender.push(blank())
        self.assertEqual(lcd.calls, [(0, 0, 480, 320)])


if __name__ == '__main__':
    unittest.main()
