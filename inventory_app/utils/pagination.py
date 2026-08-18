import math
from urllib.parse import urlencode

class Pagination:
    """
    Standard pagination model for StockSetu.
    Handles page bounds, slicing calculations, and page range iteration.
    """
    def __init__(self, page: int = 1, per_page: int = 25, total: int = 0):
        try:
            self.page = max(1, int(page or 1))
        except (ValueError, TypeError):
            self.page = 1

        try:
            self.per_page = max(1, min(100, int(per_page or 25)))
        except (ValueError, TypeError):
            self.per_page = 25

        try:
            self.total = max(0, int(total or 0))
        except (ValueError, TypeError):
            self.total = 0

        self.pages = max(1, math.ceil(self.total / self.per_page)) if self.total > 0 else 1
        
        # Clamp page within valid bounds
        if self.page > self.pages and self.total > 0:
            self.page = self.pages

        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1 if self.has_prev else None
        self.next_num = self.page + 1 if self.has_next else None

        self.start_item = ((self.page - 1) * self.per_page + 1) if self.total > 0 else 0
        self.end_item = min(self.page * self.per_page, self.total)

    def iter_pages(self, left_edge=1, left_current=2, right_current=2, right_edge=1):
        """Yields page numbers with None representing ellipses (e.g. 1, 2, None, 5, 6, 7, None, 10)."""
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (self.page - left_current <= num <= self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num

    def url_for_page(self, page_num: int, args: dict = None) -> str:
        """Constructs query string preserving active filter arguments."""
        params = dict(args or {})
        params['page'] = page_num
        params['per_page'] = self.per_page
        # Clean empty values
        cleaned = {k: v for k, v in params.items() if v is not None and v != ''}
        return '?' + urlencode(cleaned)
