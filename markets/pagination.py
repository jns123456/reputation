"""Pagination helpers for large market listings."""

from __future__ import annotations

from django.core.paginator import Paginator


def markets_list_requires_windowed_pagination(*, status: str) -> bool:
    """Return True when a full-table COUNT is too expensive for Postgres.

    Always windowed: even filtered OPEN listings (e.g. category + deep pages)
    can OOM Postgres on Heroku Essential-0 during COUNT aggregation.
    """
    return True


class WindowedPaginator:
    """Paginator that never runs COUNT; uses a page_size+1 window instead."""

    count_is_approximate = True

    def __init__(self, *, object_list, per_page: int, has_next: bool, page_number: int):
        self.object_list = object_list
        self.per_page = per_page
        self._has_next = has_next
        self._page_number = page_number

    @property
    def count(self) -> int:
        end = (self._page_number - 1) * self.per_page + len(self.object_list)
        if self._has_next:
            return end + 1
        return end

    @property
    def num_pages(self) -> int:
        if self._has_next:
            return self._page_number + 1
        return max(self._page_number, 1)


class WindowedPage:
    """Page object compatible with Django pagination templates."""

    def __init__(self, object_list, number: int, paginator: WindowedPaginator):
        self.object_list = object_list
        self.number = number
        self.paginator = paginator

    def __iter__(self):
        return iter(self.object_list)

    def __len__(self):
        return len(self.object_list)

    def __getitem__(self, index):
        return self.object_list[index]

    @property
    def has_next(self) -> bool:
        return self.paginator._has_next

    @property
    def has_previous(self) -> bool:
        return self.number > 1

    @property
    def has_other_pages(self) -> bool:
        return self.has_previous or self.has_next

    @property
    def next_page_number(self) -> int:
        return self.number + 1

    @property
    def previous_page_number(self) -> int:
        return self.number - 1

    @property
    def start_index(self) -> int:
        if not self.object_list:
            return 0
        return (self.number - 1) * self.paginator.per_page + 1

    @property
    def end_index(self) -> int:
        if not self.object_list:
            return 0
        return self.start_index + len(self.object_list) - 1


def paginate_queryset_windowed(qs, *, page, per_page: int):
    """Return a Page without issuing a COUNT query."""
    page_number = max(1, int(page or 1))
    offset = (page_number - 1) * per_page
    window = list(qs[offset : offset + per_page + 1])
    has_next = len(window) > per_page
    object_list = window[:per_page]
    paginator = WindowedPaginator(
        object_list=object_list,
        per_page=per_page,
        has_next=has_next,
        page_number=page_number,
    )
    return WindowedPage(object_list, page_number, paginator)


def paginate_queryset(qs, *, page, per_page: int, windowed: bool = False):
    """Paginate a queryset, optionally skipping COUNT for large listings."""
    if windowed:
        return paginate_queryset_windowed(qs, page=page, per_page=per_page)

    paginator = Paginator(qs, per_page)
    return paginator.get_page(page)
