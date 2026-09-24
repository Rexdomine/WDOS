class RawBodyRejectedCsrfBypassMiddleware:
    """Let the non-mutating oversized-body recovery view render its 422 state.

    RawBodyLimitMiddleware has already discarded the body and marked the request;
    without this pre-CSRF marker Django would return a generic 403 before the
    onboarding view can show the localized recovery state.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.META.get('wdos.raw_body_rejected'):
            request._dont_enforce_csrf_checks = True
        return self.get_response(request)
