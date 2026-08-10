def get_page_range(paginator, page, window=2):
    """
    Safely resolve a page number against `paginator` and return
    (page_obj, page_range).

    `page` may be any raw value from request.GET.get('page', 1) — a
    string, None, or an int. Invalid or out-of-range values fall back
    to page 1 rather than raising a 500. This is the ONLY place
    page-number parsing should happen — views must never duplicate the
    try/except here (see coding standards).

    `page_range` is a windowed list of page numbers around the current
    page, for rendering a windowed pagination control in templates.
    `None` is used as an ellipsis marker for gaps, e.g.:
        [1, None, 4, 5, 6, None, 10]

    Usage in a view:
        page_obj, page_range = get_page_range(paginator, request.GET.get('page', 1))
    """
    try:
        page_number = int(page)
    except (TypeError, ValueError):
        page_number = 1

    if page_number < 1:
        page_number = 1

    page_obj = paginator.get_page(page_number)
    current = page_obj.number
    total = paginator.num_pages

    start = max(current - window, 1)
    end = min(current + window, total)

    page_range = list(range(start, end + 1))

    if start > 1:
        page_range = ([1, None] if start > 2 else [1]) + page_range
    if end < total:
        page_range = page_range + ([None, total] if end < total - 1 else [total])

    return page_obj, page_range