"""Custom pagination classes for StaySuitePH."""

from rest_framework.pagination import PageNumberPagination


class FlexiblePageNumberPagination(PageNumberPagination):
    """
    Pagination that allows clients to set page_size via query parameter.
    Defaults to 200 items per page, max 500.
    """
    page_size = 200
    page_size_query_param = 'page_size'
    max_page_size = 500
