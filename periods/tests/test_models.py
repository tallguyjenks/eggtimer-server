import datetime

from django.contrib.auth import get_user_model, models as auth_models
from django.test import TestCase
from mock import patch

from periods import models as period_models


class TestModels(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            password='bogus', email='jessamyn@example.com', first_name=u'Jessamyn')
        self.basic_user = get_user_model().objects.create_user(
            password='bogus', email='basic@example.com')

    def _create_period(self, start_date, save=True):
        period = period_models.Period.objects.create(user=self.user, start_date=start_date)
        if save:
            period.save()
        return period

    def test_user_get_full_name_email(self):
        self.assertEqual(u'basic@example.com', '%s' % self.basic_user.get_full_name())

    def test_user_get_full_name(self):
        self.assertEqual(u'Jessamyn', '%s' % self.user.get_full_name())

    def test_user_get_short_name_email(self):
        self.assertEqual(u'basic@example.com', '%s' % self.basic_user.get_short_name())

    def test_user_get_short_name(self):
        self.assertEqual(u'Jessamyn', '%s' % self.user.get_short_name())

    def test_user_str(self):
        self.assertEqual(u'Jessamyn', '%s' % self.user.get_short_name())

    def test_period_unicode_no_start_time(self):
        period = self._create_period(start_date=datetime.date(2013, 4, 15), save=False)
        self.assertEqual(u'Jessamyn (2013-04-15)', '%s' % period)

    def test_period_unicode_with_start_time(self):
        period = self._create_period(start_date=datetime.date(2013, 4, 15), save=False)
        period.start_time = datetime.time(1, 2, 3)
        self.assertEqual(u'Jessamyn (2013-04-15 01:02:03)', '%s' % period)

    def test_statistics_str(self):
        stats = period_models.Statistics.objects.filter(user=self.user)[0]

        self.assertEqual(u'Jessamyn (jessamyn@example.com)', '%s' % stats)
        self.assertEqual([], stats.next_periods)
        self.assertEqual([], stats.next_ovulations)

    def test_statistics_with_average(self):
        self._create_period(start_date=datetime.date(2013, 2, 15))
        self._create_period(start_date=datetime.date(2013, 3, 15))
        self._create_period(start_date=datetime.date(2013, 4, 10))

        stats = period_models.Statistics.objects.filter(user=self.user)[0]

        self.assertEqual(u'Jessamyn (jessamyn@example.com)', '%s' % stats)
        self.assertEqual(27, stats.average_cycle_length)
        expected_periods = [datetime.date(2013, 5, 7),
                            datetime.date(2013, 6, 3),
                            datetime.date(2013, 6, 30)]
        self.assertEqual(expected_periods, stats.next_periods)
        expected_ovulations = [datetime.date(2013, 4, 23),
                               datetime.date(2013, 5, 20),
                               datetime.date(2013, 6, 16)]
        self.assertEqual(expected_ovulations, stats.next_ovulations)

    def test_statistics_current_cycle_length_no_periods(self):
        stats = period_models.Statistics.objects.filter(user=self.user)[0]

        self.assertEqual(-1, stats.current_cycle_length)
        self.assertEqual([], stats.next_periods)
        self.assertEqual([], stats.next_ovulations)

    def test_add_to_permissions_group_group_does_not_exist(self):
        user = period_models.User(email='jane@jane.com')
        user.save()
        user.groups.all().delete()

        period_models.add_to_permissions_group(period_models.User, user)

        groups = user.groups.all()
        self.assertEqual(1, groups.count())
        self.assertEqual(3, groups[0].permissions.count())
        for permission in groups[0].permissions.all():
            self.assertEqual('_period', permission.codename[-7:])

    def test_add_to_permissions_group_group_exists(self):
        user = period_models.User(email='jane@jane.com')
        user.save()
        user.groups.all().delete()
        auth_models.Group(name='users').save()

        period_models.add_to_permissions_group(period_models.User, user)

        groups = user.groups.all()
        self.assertEqual(1, groups.count())
        self.assertEqual(0, groups[0].permissions.count())

    def test_update_length_none_existing(self):
        period = self._create_period(start_date=datetime.date(2013, 4, 15), save=False)

        period_models.update_length(period_models.Period, period)

        self.assertIsNone(period.length)

    def test_update_length_previous_exists(self):
        previous = self._create_period(start_date=datetime.date(2013, 4, 1))
        period = self._create_period(start_date=datetime.date(2013, 4, 15), save=False)

        period_models.update_length(period_models.Period, period)

        self.assertIsNone(period.length)
        self.assertEqual(14, period_models.Period.objects.get(pk=previous.pk).length)

    def test_update_length_next_exists(self):
        period = self._create_period(start_date=datetime.date(2013, 4, 15), save=False)
        self._create_period(start_date=datetime.date(2013, 4, 30))

        period_models.update_length(period_models.Period, period)

        self.assertEqual(15, period.length)

    @patch('periods.models.Statistics.save')
    def test_update_statistics_deleted_user(self, mock_save):
        period = self._create_period(start_date=datetime.date(2013, 4, 15))
        period.user.delete()
        pre_update_call_count = mock_save.call_count

        period_models.update_statistics(period_models.Period, period)

        self.assertEqual(pre_update_call_count, mock_save.call_count)

    @patch('periods.models._today')
    def test_update_statistics_none_existing(self, mock_today):
        mock_today.return_value = datetime.date(2013, 5, 5)
        period = self._create_period(start_date=datetime.date(2013, 4, 15))

        period_models.update_statistics(period_models.Period, period)

        stats = period_models.Statistics.objects.get(user=self.user)
        self.assertEqual(28, stats.average_cycle_length)
        self.assertEqual(20, stats.current_cycle_length)
        next_periods = [
            datetime.date(2013, 5, 13),
            datetime.date(2013, 6, 10),
            datetime.date(2013, 7, 8)
        ]
        self.assertEqual(next_periods, stats.next_periods)

    @patch('periods.models._today')
    def test_update_statistics_periods_exist(self, mock_today):
        mock_today.return_value = datetime.date(2013, 5, 5)
        self._create_period(start_date=datetime.date(2013, 3, 15))
        self._create_period(start_date=datetime.date(2013, 4, 1))
        period = self._create_period(start_date=datetime.date(2013, 4, 15))
        self._create_period(start_date=datetime.date(2013, 4, 30))

        period_models.update_statistics(period_models.Period, period)

        stats = period_models.Statistics.objects.get(user=self.user)
        self.assertEqual(15, stats.average_cycle_length)
        self.assertEqual(5, stats.current_cycle_length)
        next_periods = [
            datetime.date(2013, 5, 15),
            datetime.date(2013, 5, 30),
            datetime.date(2013, 6, 14)
        ]
        self.assertEqual(next_periods, stats.next_periods)
