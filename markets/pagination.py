"""Pagination helpers for large market listings."""

from __future__ import annotations

from collections import OrderedDict

from django.core.paginator import Paginator
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param

from markets.models import Market


def resolve_markets_list_status(request) -> tuple[str | None, str]:
    """Return (filter for ``get_markets_list``, status key for windowed pagination).

    Matches the HTML market list: default to open; explicit ``?status=`` lists all.
    """
    if "status" in request.query_params:
        raw = request.query_params.get("status", "")
        return (raw or None, raw)
    return (Market.Status.OPEN, Market.Status.OPEN)


def markets_list_requires_windowed_pagination(*, status: str) -> bool:
    """Return True when a full-table COUNT is too expensive for Postgres."""
    normalized = (status or "").strip().casefold()
    return normalized in ("", Market.Status.RESOLVED)


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


class MarketApiPagination(PageNumberPagination):
    """DRF pagination that skips COUNT for all-status and resolved market listings."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def _windowed_status(self) -> str:
        _, status_key = resolve_markets_list_status(self.request)
        return status_key

    def _use_windowed(self) -> bool:
        return markets_list_requires_windowed_pagination(status=self._windowed_status())

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        self._windowed = False
        if not self._use_windowed():
            return super().paginate_queryset(queryset, request, view)

        page_size = self.get_page_size(request)
        if not page_size:
            return None

        page_number = request.query_params.get(self.page_query_param, 1)
        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            page_number = 1

        self.windowed_page = paginate_queryset_windowed(
            queryset,
            page=page_number,
            per_page=page_size,
        )
        self._windowed = True
        return list(self.windowed_page.object_list)

    def get_next_link(self):
        if not getattr(self, "_windowed", False):
            return super().get_next_link()
        if not self.windowed_page.has_next:
            return None
        return self._page_link(self.windowed_page.next_page_number)

    def get_previous_link(self):
        if not getattr(self, "_windowed", False):
            return super().get_previous_link()
        if not self.windowed_page.has_previous:
            return None
        return self._page_link(self.windowed_page.previous_page_number)

    def _page_link(self, page_number: int) -> str:
        url = self.request.build_absolute_uri()
        return replace_query_param(url, self.page_query_param, page_number)

    def get_paginated_response(self, data):
        if not getattr(self, "_windowed", False):
            return super().get_paginated_response(data)

        return Response(
            OrderedDict(
                [
                    ("count", self.windowed_page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("results", data),
                ]
            )
        )
