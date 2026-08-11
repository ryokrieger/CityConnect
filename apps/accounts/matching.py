"""
Design Pattern 2 — Strategy Pattern
Applied to: interest-based user matching.

The platform supports matching by city scope and neighborhood scope.
Encoding both as interchangeable strategy classes means adding a new
scope (e.g., country-wide) requires only a new class — MatchingContext
and every call site stay untouched.
"""

from abc import ABC, abstractmethod

from django.db.models import Count, Q


class MatchingStrategy(ABC):
    """Abstract base for all interest-based matching strategies."""

    @abstractmethod
    def get_scope_filter(self, user) -> dict:
        """Return a Django ORM filter dict to scope the candidate user pool."""
        pass

    def get_matches(self, user, page=1, per_page=10):
        from apps.accounts.models import User
        from apps.social.models import Friendship

        scope_filter = self.get_scope_filter(user)
        user_interest_ids = list(user.interests.values_list('id', flat=True))

        if not user_interest_ids:
            return [], 0

        friend_ids = Friendship.objects.get_friend_ids(user.id)

        queryset = (
            User.objects
            .filter(**scope_filter)
            .filter(interests__id__in=user_interest_ids)
            .exclude(id=user.id)
            .exclude(id__in=friend_ids)
            .annotate(shared_count=Count('interests', filter=Q(interests__id__in=user_interest_ids)))
            .order_by('-shared_count', 'username')
            .distinct()
        )

        total = queryset.count()
        offset = (page - 1) * per_page
        return queryset[offset:offset + per_page], total


class CityMatchingStrategy(MatchingStrategy):
    def get_scope_filter(self, user) -> dict:
        return {'city': user.city}


class NeighborhoodMatchingStrategy(MatchingStrategy):
    def get_scope_filter(self, user) -> dict:
        return {'neighborhood': user.neighborhood}


class MatchingContext:
    """Selects and executes the appropriate matching strategy."""

    STRATEGIES = {
        'city': CityMatchingStrategy,
        'neighborhood': NeighborhoodMatchingStrategy,
    }

    def __init__(self, scope: str):
        strategy_class = self.STRATEGIES.get(scope)
        if not strategy_class:
            raise ValueError(f"Unknown matching scope: {scope}")
        self._strategy = strategy_class()

    def get_matches(self, user, page=1, per_page=10):
        return self._strategy.get_matches(user, page, per_page)


# Usage:
#   context = MatchingContext(scope='city')  # or 'neighborhood'
#   matches, total = context.get_matches(request.user, page=page_number)