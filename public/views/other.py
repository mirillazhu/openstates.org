import feedparser
from collections import Counter
from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import render
from openstates.data.models import Bill, Organization, Person
from public.views.bills import BillList
from utils.common import abbr_to_jid, states, sessions_with_bills, jid_to_abbr
from utils.bills import search_bills, EXCLUDED_CLASSIFICATIONS
from utils.people import person_as_dict


def styleguide(request):
    return render(request, "public/views/styleguide.html")


def _get_latest_updates():
    RSS_FEED = "https://blog.openstates.org/index.xml"

    feed = feedparser.parse(RSS_FEED)
    return [
        {"title": entry.title, "link": entry.link, "date": entry.published}
        for entry in feed.entries
    ][:3]


def _preprocess_sponsors(bills):
    FIRST_SPONSORS_COUNT = 3

    for bill in bills:
        bill.first_sponsors = []
        sponsorships = list(bill.sponsorships.all())
        bill.first_sponsors = sorted(
            sponsorships, key=lambda s: (s.primary, s.person_id or "zzz", s.id)
        )[:FIRST_SPONSORS_COUNT]
        bill.extra_sponsors = len(sponsorships) - len(bill.first_sponsors)


def home(request):
    # cache these to try to keep the homepage as cheap as possible
    cache_time = 60 * 60 * 24  # cache for a full day
    updates = cache.get_or_set(
        "homepage-blog-updates-cb", _get_latest_updates, cache_time
    )

    context = {"states": states, "blog_updates": updates}
    return render(request, "public/views/home.html", context)


def state(request, state):
    RECENTLY_INTRODUCED_BILLS_TO_SHOW = 4
    RECENTLY_PASSED_BILLS_TO_SHOW = 4

    jid = abbr_to_jid(state)

    # we need basically all of the orgs, so let's just do one big query for them
    legislature = None
    chambers = []

    organizations = (
        Organization.objects.filter(jurisdiction_id=jid)
        .annotate(seats=Sum("posts__maximum_memberships"))
        .select_related("parent")
    )

    for org in organizations:
        if org.classification == "legislature":
            legislature = org
        elif org.classification in ("upper", "lower"):
            chambers.append(org)

    # unicameral
    if not chambers:
        chambers = [legislature]

    # legislators
    legislators = Person.objects.current_legislators_with_roles(chambers)

    for chamber in chambers:
        parties = []
        titles = []
        for legislator in legislators:
            if legislator.current_role["org_classification"] == chamber.classification:
                parties.append(legislator.primary_party)
                titles.append(legislator.current_role["title"])

        chamber.parties = dict(Counter(parties).most_common())
        try:
            chamber.title = titles[0]
        except IndexError:
            chamber.title = "Legislator"

    # bills
    bills = (
        Bill.objects.all()
        .select_related("legislative_session", "legislative_session__jurisdiction")
        .filter(from_organization__in=chambers)
        .prefetch_related("sponsorships", "sponsorships__person")
    )

    recently_introduced_bills = list(
        bills.filter(first_action_date__isnull=False).order_by("-first_action_date")[
            :RECENTLY_INTRODUCED_BILLS_TO_SHOW
        ]
    )

    recently_passed_bills = list(
        bills.filter(latest_passage_date__isnull=False).order_by(
            "-latest_passage_date"
        )[:RECENTLY_PASSED_BILLS_TO_SHOW]
    )

    _preprocess_sponsors(recently_introduced_bills)
    _preprocess_sponsors(recently_passed_bills)

    all_sessions = sessions_with_bills(jid)

    return render(
        request,
        "public/views/state.html",
        {
            "state": state,
            "state_nav": "overview",
            "legislature": legislature,
            "chambers": chambers,
            "chambers_json": {c.classification: c.name for c in chambers},
            "recently_introduced_bills": recently_introduced_bills,
            "recently_passed_bills": recently_passed_bills,
            "all_sessions": all_sessions,
        },
    )


def site_search(request):
    query = request.GET.get("query")
    state = request.GET.get("state")

    bills_view = BillList()

    bills = []
    people = []

    context = {
        "query": query,
        "state": state,
        "bills": bills,
        "people": people,
    }

    if query:
        if state:
            # bill search (call BillList methods)
            bills, form = bills_view.get_bills(request, state)
            paginator, page_num = bills_view.paginate_bills(request, bills)
            sort_context = bills_view.get_sort_context(request)

            # compute/retrieve/set filter options
            is_initial_query = True  # initial query is true iff request is not made through search options form
            is_initial_query = not request.GET.get("filter_form")

            if is_initial_query:  # if bills haven't been filtered yet

                base_bills_exist = bills.exists()
                request.session["base_bills_exist"] = base_bills_exist

                if (
                    base_bills_exist
                ):  # only compute filter options if there is a nonzero number of base bills
                    (
                        filter_options,
                        available_classifications,
                        available_subjects,
                        available_sponsors,
                    ) = bills_view.get_filter_options(state, base_bills=bills)
                    request.session[
                        "available_classifications"
                    ] = available_classifications
                    request.session["available_subjects"] = available_subjects
                    request.session["available_sponsors"] = available_sponsors

            else:  # if not initial query and base bills exist, retrieve previously computed classifications, subjects, sponsors

                base_bills_exist = request.session.get("base_bills_exist")

                if base_bills_exist:
                    available_classifications = request.session.get(
                        "available_classifications"
                    )
                    available_subjects = request.session.get("available_subjects")
                    available_sponsors = request.session.get("available_sponsors")
                    filter_options, *_ = bills_view.get_filter_options(
                        state,
                        base_bills=bills,
                        available_classifications=available_classifications,
                        available_subjects=available_subjects,
                        available_sponsors=available_sponsors,
                    )  # include bills as fallback for computation in case session variables fail, but shouldn't need to be used

            # people search
            people = []
            for p in Person.objects.search(query, state=state):
                pd = person_as_dict(p)
                pd["current_state"] = jid_to_abbr(p.current_jurisdiction_id).upper()
                people.append(pd)

            context.update(
                {
                    "bills": paginator.page(page_num),
                    "people": people,
                    "form": form,
                    **sort_context,
                    "base_bills_exist": base_bills_exist,
                }
            )

            if base_bills_exist:  # only display search options form if base bills exist
                context.update(filter_options)

        else:  # no state provided (placeholder, can streamline later)

            bills = search_bills(
                state=None,
                query=query,
                sort="-latest_action",
                exclude_classifications=EXCLUDED_CLASSIFICATIONS,
            )

            # pagination
            try:
                page_num = int(request.GET.get("page", 1))
            except ValueError:
                raise Http404()
            bills_paginator = Paginator(bills, 20)
            try:
                bills = bills_paginator.page(page_num)
            except EmptyPage:
                raise Http404()

            # people search
            people = []
            for p in Person.objects.search(query, state=None):
                pd = person_as_dict(p)
                pd["current_state"] = jid_to_abbr(p.current_jurisdiction_id).upper()
                people.append(pd)

            context.update(
                {
                    "bills": bills,
                    "people": people,
                }
            )

    return render(request, "public/views/search.html", context)
