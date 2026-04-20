from django.urls import path, include
from django.conf import settings
from django.contrib import admin
from django.views.generic import TemplateView


class FlatPageView(TemplateView):
    # get selected state for header
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["state"] = self.request.session.get("selected_state", "")
        return context


urlpatterns = [
    path("djadmin/", admin.site.urls),
    # path("accounts/", include("allauth.urls")),
    # path("accounts/profile/", include("profiles.urls")),
    path("dashboard/", include("dashboards.urls")),
    path("", include("public.urls")),
    # path("", include("web.redirects")),
    # flatpages
    path("about/", FlatPageView.as_view(template_name="flat/about.html")),
    # path(
    #     "about/contributing/",
    #     FlatPageView.as_view(template_name="flat/contributing.html"),
    # ),
    # path(
    #     "about/subscriptions/",
    #     FlatPageView.as_view(template_name="flat/subscriptions.html"),
    # ),
    path("tos/", FlatPageView.as_view(template_name="flat/tos.html")),
    # path("api/registered/", FlatPageView.as_view(template_name="flat/registered.html")),
]


if settings.DEBUG:
    from django.views.defaults import page_not_found, server_error

    urlpatterns += [
        path("404/", page_not_found, {"exception": None}),
        path("500/", server_error),
        # url(r'^silk/', include('silk.urls', namespace='silk')),
    ]
