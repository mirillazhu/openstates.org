from django.http import Http404
from django.shortcuts import render, redirect
from openstates.data.models import Person
from utils.common import jid_to_abbr
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


# state-specific homepage
def home(request, state="us"):
    request.session["selected_state"] = state
    context = {"state": state}
    return render(request, "public/views/home.html", context)


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
        for p in Person.objects.search(query, state=state).distinct():
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
