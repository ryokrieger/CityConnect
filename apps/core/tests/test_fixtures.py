from django.core.management import call_command
from django.test import TestCase

from apps.core.models import City, Interest, Neighborhood


class InitialDataFixtureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('loaddata', 'apps/core/fixtures/initial_data.json', verbosity=0)

    def test_counts(self):
        self.assertEqual(City.objects.count(), 8)
        self.assertEqual(Neighborhood.objects.count(), 64)
        self.assertEqual(Interest.objects.count(), 12)

    def test_all_cities_are_in_bangladesh(self):
        self.assertFalse(City.objects.exclude(country='Bangladesh').exists())
        self.assertEqual(
            sorted(City.objects.values_list('city_name', flat=True)),
            ['Barishal', 'Chattogram', 'Dhaka', 'Khulna', 'Mymensingh', 'Rajshahi', 'Rangpur', 'Sylhet'],
        )

    def test_every_neighborhood_has_a_city(self):
        dhaka = City.objects.get(city_name='Dhaka')
        names = set(dhaka.neighborhoods.values_list('area_name', flat=True))
        self.assertTrue({'Gazipur', 'Narayanganj', 'Tangail'} <= names)

    def test_fixture_loads_twice_without_duplicates(self):
        call_command('loaddata', 'apps/core/fixtures/initial_data.json', verbosity=0)
        self.assertEqual(City.objects.count(), 8)
        self.assertEqual(Interest.objects.count(), 12)