from rest_framework.pagination import PageNumberPagination


class OptionalPostPagination(PageNumberPagination):
    """Keep the lecture's list response; opt in with ?page=1 for bounded pages."""
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 30

    def paginate_queryset(self, queryset, request, view=None):
        if 'page' not in request.query_params and 'page_size' not in request.query_params:
            return None
        return super().paginate_queryset(queryset, request, view)
