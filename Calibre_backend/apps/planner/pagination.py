from rest_framework.pagination import PageNumberPagination


class LargePageNumberPagination(PageNumberPagination):
    """
    Pagination for endpoints that may return many items (e.g., events with repeats).
    Allows up to 200 items per page, default 20.
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200
