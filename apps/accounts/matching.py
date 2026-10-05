"""Strategy Pattern — interest-based user matching.

Each scope (city, neighborhood) is an interchangeable strategy that only
decides *which users are candidates*. Adding a new scope means adding one
class and one entry in `MatchingContext.STRATEGIES`.
"""
from abc import ABC, abstractmethod

from django.db.models import Count, Q


class MatchingStrategy(ABC):
    """Abstract base for all interest-based matching strategies."""

    @abstractmethod
    def get_scope_filter(self, user) -> dict | None:
        """Return an ORM filter dict scoping the candidate pool.

        Return ``None`` when the user has no value for this scope (for example
        no neighborhood set), so no one is matched rather than everyone with a
        blank value.
        """

    def get_matches(self, user, page=1, per_page=10):
        """Return ``(users_on_page, total_count)`` ordered by shared interests.

        Each returned user has ``shared_count`` and ``shared_interest_names``
        attributes. Friends, the user themself and restricted users are excluded.
        """
        from apps.accounts.models import User, UserInterest
        from apps.social.models import Friendship

        scope_filter = self.get_scope_filter(user)
        user_interest_ids = list(user.interests.values_list('id', flat=True))
        if not scope_filter or not user_interest_ids:
            return [], 0

        friend_ids = Friendship.objects.get_friend_ids(user.id)

        queryset = (
            User.objects
            .filter(**scope_filter, is_restricted=False)
            .filter(interests__id__in=user_interest_ids)
            .exclude(id=user.id)
            .exclude(id__in=friend_ids)
            .annotate(shared_count=Count('interests', filter=Q(interests__id__in=user_interest_ids)))
            .order_by('-shared_count', 'username')
        )

        total = queryset.count()
        page = max(int(page), 1)
        offset = (page - 1) * per_page
        users = list(queryset[offset:offset + per_page])

        # One extra query for the whole page — never one per user.
        names = {u.id: [] for u in users}
        rows = (
            UserInterest.objects
            .filter(user_id__in=names.keys(), interest_id__in=user_interest_ids)
            .select_related('interest')
            .order_by('interest__interest_name')
        )
        for row in rows:
            names[row.user_id].append(row.interest.interest_name)
        for u in users:
            u.shared_interest_names = names[u.id]

        return users, total


class CityMatchingStrategy(MatchingStrategy):
    def get_scope_filter(self, user):
        return {'city_id': user.city_id} if user.city_id else None


class NeighborhoodMatchingStrategy(MatchingStrategy):
    def get_scope_filter(self, user):
        return {'neighborhood_id': user.neighborhood_id} if user.neighborhood_id else None


class MatchingContext:
    """Selects and executes the appropriate matching strategy."""

    STRATEGIES = {
        'city': CityMatchingStrategy,
        'neighborhood': NeighborhoodMatchingStrategy,
    }

    def __init__(self, scope: str):
        strategy_class = self.STRATEGIES.get(scope)
        if not strategy_class:
            raise ValueError(f'Unknown matching scope: {scope}')
        self._strategy = strategy_class()

    def get_matches(self, user, page=1, per_page=10):
        return self._strategy.get_matches(user, page, per_page)