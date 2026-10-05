from django.core.paginator import Paginator
from django.test import SimpleTestCase

from apps.core.pagination import get_page_range, safe_page_number


class SafePageNumberTests(SimpleTestCase):
    def test_valid(self):
        self.assertEqual(safe_page_number('3'), 3)

    def test_malformed_values_default_to_one(self):
        for raw in ('abc', '', None, '1.5', '-4', '0'):
            self.assertEqual(safe_page_number(raw), 1, raw)


class GetPageRangeTests(SimpleTestCase):
    def paginator(self, pages):
        return Paginator(list(range(pages * 10)), 10)

    def test_few_pages_shows_all(self):
        self.assertEqual(get_page_range(self.paginator(3), 2), [1, 2, 3])

    def test_middle_has_both_gaps(self):
        self.assertEqual(get_page_range(self.paginator(20), 10), [1, None, 8, 9, 10, 11, 12, None, 20])

    def test_start_has_trailing_gap_only(self):
        self.assertEqual(get_page_range(self.paginator(20), 1), [1, 2, 3, None, 20])

    def test_end_has_leading_gap_only(self):
        self.assertEqual(get_page_range(self.paginator(20), 20), [1, None, 18, 19, 20])

    def test_adjacent_pages_have_no_gap_marker(self):
        self.assertEqual(get_page_range(self.paginator(7), 4), [1, 2, 3, 4, 5, 6, 7])

    def test_out_of_range_page_is_clamped(self):
        self.assertEqual(get_page_range(self.paginator(5), 99), get_page_range(self.paginator(5), 5))