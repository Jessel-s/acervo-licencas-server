import unittest

from availability import is_available_after_return, parse_datetime_value, schedule_start


class AvailabilityTests(unittest.TestCase):
    def test_blocks_schedule_before_predicted_return(self):
        self.assertFalse(
            is_available_after_return(
                '2026-08-28', '16:00', '2026-08-28 16:50:00'
            )
        )

    def test_allows_schedule_at_or_after_predicted_return(self):
        self.assertTrue(
            is_available_after_return(
                '2026-08-28', '17:00', '2026-08-28 16:50:00'
            )
        )

    def test_parses_stored_text_and_builds_schedule_start(self):
        self.assertEqual(
            parse_datetime_value('2026-08-28 16:50:00').hour,
            16
        )
        self.assertEqual(
            schedule_start('2026-08-28', '17:00').strftime('%H:%M'),
            '17:00'
        )


if __name__ == '__main__':
    unittest.main()