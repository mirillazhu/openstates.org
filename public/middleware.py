from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta

# for whole-app demo login, which is separate and distinct from profiles/accounts login

EXEMPT_PATHS = ["/login/", "/static/"]
DEMO_SESSION_HOURS = 24


def login_required_middleware(get_response):
    def middleware(request):

        # if more than 24 hours has passed since the user has signed in, automatically sign out
        authenticated_at = request.session.get("authenticated_at", None)

        if authenticated_at:
            time_authenticated = timezone.now() - timezone.datetime.fromisoformat(
                authenticated_at
            ).replace(tzinfo=timezone.utc)
            if time_authenticated > timedelta(hours=DEMO_SESSION_HOURS):
                request.session.pop("is_authenticated", None)
                request.session.pop("authenticated_at", None)

        if not request.session.get("is_authenticated"):
            if not any(request.path.startswith(p) for p in EXEMPT_PATHS):
                return redirect(f"/login/?next={request.path}")

        return get_response(request)

    return middleware
