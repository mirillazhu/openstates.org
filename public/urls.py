from django.urls import path, re_path
from .views.other import home, state, site_search
from .views.legislators import legislators, person, find_your_legislator
from .views.bills import (
    bills,
    bill_dashboard,
    bill,
    vote,
    bill_document,
    document_proxy_for_development,
)
from .views.fallback import fallback, legislator_fallback
from utils.common import states


OCD_ID_PATTERN = r"[a-z\d]{8}-[a-z\d]{4}-[a-z\d]{4}-[a-z\d]{4}-[a-z\d]{12}"
# Only allow valid state abbreviations
state_abbrs = [s.abbr.lower() for s in states] + ["us"]
state_abbr_pattern = r"({})".format("|".join(state_abbrs))

urlpatterns = [
    # path("styleguide", styleguide, name="styleguide"),
    # top level views
    path("", home, name="home"),
    path("bill_dashboard/", bill_dashboard, name="bill_dashboard"),
    # non state-specific search (placeholder)
    path("search/", site_search, name="search"),
    re_path(r"^(?P<state>{})/$".format(state_abbr_pattern), state, name="state"),
    # find your legislator
    re_path(
        r"^(?P<state>{})/find_your_legislator/$".format(state_abbr_pattern),
        find_your_legislator,
        name="find_your_legislator",
    ),
    # people
    re_path(
        r"^(?P<state>{})/legislators/$".format(state_abbr_pattern),
        legislators,
        name="legislators",
    ),
    re_path(r"^person/.*\-(?P<person_id>[0-9A-Za-z]+)/$", person, name="person-detail"),
    # state-specific search
    re_path(
        r"^(?P<state>{})/search/$".format(state_abbr_pattern),
        site_search,
        name="state_search",
    ),
    # bills
    re_path(
        r"^(?P<state>{})/bills/$".format(state_abbr_pattern),
        bills,
        name="bills",
    ),
    # has trailing slash for consistency
    # re_path(
    #     r"^(?P<state>{})/bills/feed/$".format(state_abbr_pattern),
    #     bills_feed,
    #     name="bills_feed",
    # ),
    re_path(
        r"^(?P<state>{})/bills/(?P<session>[-\w ]+)/(?P<bill_id>[-\w\. ]+)/$".format(
            state_abbr_pattern
        ),
        bill,
        name="bill",
    ),
    re_path(r"^vote/(?P<vote_id>[-0-9a-f]+)/$", vote, name="vote-detail"),
    re_path(
        r"^document/(?P<document_type>[\w]+)/(?P<document_link_id>[-0-9a-f]+)/$",
        bill_document,
        name="bill_document",
    ),
    # for development only -- remove for production
    path("development-pdf-proxy/<path:remote_url>", document_proxy_for_development),
    # fallbacks
    path("reportcard/", fallback),
    re_path(r"[a-z]{2}/votes/[A-Z]{2}V\d{8}/$", fallback),
    re_path(
        r"[a-z]{2}/legislators/(?P<legislator_id>[A-Z]{2}L\d{6})/", legislator_fallback
    ),
]
