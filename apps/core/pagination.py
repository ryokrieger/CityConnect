"""Shared, safe pagination helpers — the only place `?page=` is parsed."""
from django.core.paginator import Paginator


def safe_page_number(raw, default=1):
    """Parse a page number from user input without ever raising."""
    try:
        page = int(raw)
    except (TypeError, ValueError):
        return default
    return page if page >= 1 else default


def get_page_range(paginator, page, window=2):
    """Windowed page list for a pagination control.

    Returns page numbers around `page`, always including the first and last
    pages, with ``None`` marking a gap (render it as an ellipsis).
    Example: ``[1, None, 4, 5, 6, 7, 8, None, 20]``.
    """
    total = paginator.num_pages
    page = min(max(safe_page_number(page), 1), total)
    start = max(page - window, 1)
    end = min(page + window, total)

    pages = list(range(start, end + 1))
    if start > 1:
        pages = [1] + ([None] if start > 2 else []) + pages
    if end < total:
        pages = pages + ([None] if end < total - 1 else []) + [total]
    return pages


def paginate(request, items, per_page=10):
    """Paginate `items` using ``?page=``; returns ``(page_obj, page_range)``."""
    paginator = Paginator(items, per_page)
    page_obj = paginator.get_page(safe_page_number(request.GET.get('page', 1)))
    return page_obj, get_page_range(paginator, page_obj.number)