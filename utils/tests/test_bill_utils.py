import pytest
from django.test import RequestFactory
from django.core.paginator import Paginator
from django.http import Http404
from openstates.data.models import Bill
from testutils.populators import populate_db, populate_unicam
from utils.bills import (
    get_filter_options,
    get_sort_context,
    paginate_bills,
    PageOutOfBounds,
)


@pytest.mark.django_db
def setup():
    populate_db()


@pytest.mark.django_db
def test_get_filter_options_all_bills_in_state():
    # all bills in state (default for bills view)
    base_bills = Bill.objects.all().filter(
        legislative_session__jurisdiction__name="Alaska"
    )
    options = get_filter_options("ak", base_bills)

    assert len(options) == 5
    assert options["chambers"] == {"lower": "Alaska House", "upper": "Alaska Senate"}
    assert options["sessions"] == {"2017": "2017", "2018": "2018"}
    assert all(
        item in options["classifications"]
        for item in ["bill", "constitutional amendment"]
    )
    assert all(item in options["subjects"] for item in ["moose not meese", "nature"])
    assert options["sponsor_names"] == ["Amanda Adams"]


@pytest.mark.django_db
def test_get_filter_options_bills_in_search_queryset():
    # limited set of base bills (default for search view)
    populate_unicam()  # nebraska
    base_bills = Bill.objects.all().filter(identifier="LB 42")
    options = get_filter_options("ne", base_bills)

    assert options["chambers"] == {"legislature": "Nebraska Legislature"}
    assert options["sessions"] == {"2018": "2018"}
    assert options["classifications"] == ["bill"]
    assert options["subjects"] == ["farms"]
    assert options["sponsor_names"] == []


@pytest.mark.django_db
def test_get_filter_options_empty_queryset():
    # search query returns no bills
    populate_unicam()  # nebraska
    base_bills = Bill.objects.all().filter(identifier="LB 1807")
    options = get_filter_options("ne", base_bills)

    assert options["chambers"] == {"legislature": "Nebraska Legislature"}
    assert options["sessions"] == {
        "2018": "2018"
    }  # sessions should be all sessions with bills, regardless of whether the session contains bills in query
    assert options["classifications"] == []
    assert options["subjects"] == []
    assert options["sponsor_names"] == []


@pytest.mark.django_db
def test_paginate_bills():
    factory = RequestFactory()
    bills = list(range(100))

    # standard pagination
    request = factory.get("/ct/bills/?page=2")
    paginator, page_num = paginate_bills(request, bills, page_size=8)

    assert isinstance(paginator, Paginator)
    assert paginator.count == 100
    assert paginator.num_pages == 13
    assert page_num == 2

    # no page number specified -- should default to first page
    request = factory.get("/ct/bills/")
    paginator, page_num = paginate_bills(request, bills, page_size=8)

    assert isinstance(paginator, Paginator)
    assert page_num == 1

    # invalid page
    request = factory.get("/ct/bills/?page=invalid")

    with pytest.raises(Http404):
        paginate_bills(request, bills, page_size=8)

    # empty page
    request = factory.get("/ct/bills/?page=999")

    with pytest.raises(PageOutOfBounds):
        paginate_bills(request, bills, page_size=8)


@pytest.mark.django_db
def test_get_sort_context_bills_and_search_view():
    sortable_columns = ["first_action", "latest_action"]
    ascending_by_default = []

    factory = RequestFactory()

    # first action ascending
    request = factory.get("/ct/bills/?sort=first_action")
    context = get_sort_context(request, sortable_columns, ascending_by_default)

    assert (len(context)) == 4
    assert context["first_action_sort_url"] == "/ct/bills/?sort=-first_action&page=1"
    assert context["first_action_arrow"] == "\u2191"  # up
    assert context["latest_action_sort_url"] == "/ct/bills/?sort=-latest_action&page=1"
    assert context["latest_action_arrow"] == ""

    # first action descending
    request = factory.get("/ct/bills/?sort=-first_action")
    context = get_sort_context(request, sortable_columns, ascending_by_default)

    assert (len(context)) == 4
    assert context["first_action_sort_url"] == "/ct/bills/?sort=first_action&page=1"
    assert context["first_action_arrow"] == "\u2193"  # down
    assert context["latest_action_sort_url"] == "/ct/bills/?sort=-latest_action&page=1"
    assert context["latest_action_arrow"] == ""

    # latest action ascending
    request = factory.get("/ct/bills/?sort=latest_action")
    context = get_sort_context(request, sortable_columns, ascending_by_default)

    assert (len(context)) == 4
    assert context["first_action_sort_url"] == "/ct/bills/?sort=-first_action&page=1"
    assert context["first_action_arrow"] == ""
    assert context["latest_action_sort_url"] == "/ct/bills/?sort=-latest_action&page=1"
    assert context["latest_action_arrow"] == "\u2191"  # up

    # latest action descending
    request = factory.get("/ct/bills/?sort=-latest_action")
    context = get_sort_context(request, sortable_columns, ascending_by_default)

    assert (len(context)) == 4
    assert context["first_action_sort_url"] == "/ct/bills/?sort=-first_action&page=1"
    assert context["first_action_arrow"] == ""
    assert context["latest_action_sort_url"] == "/ct/bills/?sort=latest_action&page=1"
    assert context["latest_action_arrow"] == "\u2193"  # down

    # no default sort specified -- should be same as latest action descending
    request = factory.get("/ct/bills/")
    context = get_sort_context(request, sortable_columns, ascending_by_default)

    assert (len(context)) == 4
    assert context["first_action_sort_url"] == "/ct/bills/?sort=-first_action&page=1"
    assert context["first_action_arrow"] == ""
    assert context["latest_action_sort_url"] == "/ct/bills/?sort=latest_action&page=1"
    assert context["latest_action_arrow"] == "\u2193"  # down


@pytest.mark.django_db
def test_get_sort_context_bill_dashboard_view():
    sortable_columns = [
        "bill_id",
        "bill_title",
        "bill_status",
        "session",
        "first_action",
        "latest_action",
    ]
    ascending_by_default = [
        "bill_id",
        "bill_title",
        "bill_status",
    ]

    factory = RequestFactory()

    # test ascending by default field -- ascending
    request = factory.get("/bill_dashboard/?sort=bill_id")
    context = get_sort_context(request, sortable_columns, ascending_by_default)

    assert (len(context)) == 12
    assert (
        context["first_action_sort_url"] == "/bill_dashboard/?sort=-first_action&page=1"
    )
    assert context["first_action_arrow"] == ""
    assert context["bill_id_sort_url"] == "/bill_dashboard/?sort=-bill_id&page=1"
    assert context["bill_id_arrow"] == "\u2191"  # up

    # test ascending by default field -- descending
    request = factory.get("/bill_dashboard/?sort=-bill_id")
    context = get_sort_context(request, sortable_columns, ascending_by_default)

    assert (len(context)) == 12
    assert (
        context["first_action_sort_url"] == "/bill_dashboard/?sort=-first_action&page=1"
    )
    assert context["first_action_arrow"] == ""
    assert context["bill_id_sort_url"] == "/bill_dashboard/?sort=bill_id&page=1"
    assert context["bill_id_arrow"] == "\u2193"  # down
