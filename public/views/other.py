from collections import Counter
from django.conf import settings
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import render, redirect
from django.utils import timezone
from openstates.data.models import Bill, Organization, Person
from utils.common import abbr_to_jid, sessions_with_bills, jid_to_abbr
from utils.bills import (
    get_bills,
    get_sort_context,
    get_filter_options,
    paginate_bills,
    PageOutOfBounds,
)
from utils.people import person_as_dict


def styleguide(request):
    return render(request, "public/views/styleguide.html")


def _preprocess_sponsors(bills):
    FIRST_SPONSORS_COUNT = 3

    for bill in bills:
        bill.first_sponsors = []
        sponsorships = list(bill.sponsorships.all())
        bill.first_sponsors = sorted(
            sponsorships, key=lambda s: (s.primary, s.person_id or "zzz", s.id)
        )[:FIRST_SPONSORS_COUNT]
        bill.extra_sponsors = len(sponsorships) - len(bill.first_sponsors)


# state-specific homepage
def home(request, state="us"):
    request.session["selected_state"] = state
    context = {"state": state}
    return render(request, "public/views/home.html", context)


def state(request, state):
    RECENTLY_INTRODUCED_BILLS_TO_SHOW = 4
    RECENTLY_PASSED_BILLS_TO_SHOW = 4

    request.session["selected_state"] = state

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


def resources(request):
    state = request.session.get("selected_state", "")
    context = {"state": state}
    return render(request, "public/views/resources.html", context)


# state-specific search -- state is now required
def state_search(request, state):

    # for initial form submission (via POST), store search query in session and redirect to GET
    if request.method == "POST":
        request.session["search_query"] = request.POST.get("query")
        return redirect("state_search", state)

    # clear search query in session if arriving from footer link, then redirect
    if request.GET.get("clear"):
        request.session.pop("search_query", None)
        return redirect("state_search", state)

    # upon redirect or GET requests from filter form, pagination, sort, nav buttons, etc., get search query from session
    query = request.session.get("search_query", "")

    # also save state as selected_state to session
    request.session["selected_state"] = state

    bills = []
    people = []

    context = {
        "query": query,
        "state": state,
        "bills": bills,
        "people": people,
    }

    if query:
        # bill search
        bills, form = get_bills(request, state, query)
        try:
            paginator, page_num = paginate_bills(request, bills, 20)
        except PageOutOfBounds:
            raise Http404()
        sort_context = get_sort_context(request, ["first_action", "latest_action"], [])

        # compute/retrieve/set filter options
        is_initial_query = True  # initial query is true iff request is not made through search options form
        is_initial_query = not request.GET.get("is_filter_form")

        if is_initial_query:  # if bills haven't been filtered yet

            base_bills_exist = bills.exists()
            request.session["base_bills_exist"] = base_bills_exist

            if base_bills_exist:
                filter_options = get_filter_options(state, bills)
                request.session["filter_options"] = filter_options

        else:  # if not initial query and base bills exist, retrieve previously computed filter options from session
            base_bills_exist = request.session.get("base_bills_exist")
            if base_bills_exist is None:  # fallback for lost session data
                base_bills_exist = bills.exists()
                request.session["base_bills_exist"] = base_bills_exist

            if base_bills_exist:
                filter_options = request.session.get("filter_options")
                if filter_options is None:  # fallback for lost session data
                    filter_options = get_filter_options(state, bills)
                    request.session["filter_options"] = filter_options

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

    return render(request, "public/views/search.html", context)


def demo_login(request):
    error = None

    if request.method == "POST":
        if request.POST.get("password") == settings.DEMO_PASSWORD:
            request.session["is_authenticated"] = True
            request.session["authenticated_at"] = timezone.now().isoformat()
            return redirect(request.GET.get("next", "/"))
        else:
            error = "Incorrect sign in, please reach out if needed!"

    context = {"error": error}
    return render(request, "public/views/demo_login.html", context)
