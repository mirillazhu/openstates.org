import pytest
from graphapi.tests.utils import populate_db, populate_unicam


@pytest.mark.django_db
def setup():
    populate_db()


@pytest.mark.django_db
def test_state_view(client, django_assert_max_num_queries):
    # difficult to make this one exact, so settled for max of 13,
    # fluctuates between 12-13 (not including state sessioning)
    # expected: organization, person, membership, organization, post,
    #   bill, billsponsorship, person, bill, billsponsorship, person,
    #   legislativesession, organization
    # then add 4 for state sessioning
    with django_assert_max_num_queries(17):
        resp = client.get("/ak/")
    assert resp.status_code == 200
    assert resp.context["state"] == "ak"
    assert resp.context["state_nav"] == "overview"
    assert len(resp.context["chambers"]) == 2

    # check chambers
    ch1, ch2 = resp.context["chambers"]
    if ch1.classification == "upper":
        upper, lower = ch1, ch2
    else:
        lower, upper = ch1, ch2
    assert lower.parties == {"Democratic": 1, "Republican": 3}
    assert lower.seats == 5
    assert upper.parties == {"Democratic": 1, "Independent": 1}
    assert upper.seats == 3

    # bills
    assert len(resp.context["recently_introduced_bills"]) == 4
    assert len(resp.context["recently_passed_bills"]) == 1

    # sessions
    assert resp.context["all_sessions"][0].identifier == "2018"
    assert len(resp.context["all_sessions"]) == 2


@pytest.mark.django_db
def test_state_view_unicam(client, django_assert_num_queries):
    populate_unicam()
    resp = client.get("/ne/")
    assert resp.status_code == 200
    assert resp.context["state"] == "ne"
    assert resp.context["state_nav"] == "overview"
    assert len(resp.context["chambers"]) == 1
    legislature = resp.context["chambers"][0]
    assert legislature.parties == {"Nonpartisan": 2}
    assert legislature.seats == 2


@pytest.mark.django_db
def test_homepage(client, django_assert_num_queries):
    with django_assert_num_queries(0):
        resp = client.get("/")
    assert resp.status_code == 200
    assert len(resp.context["states"]) == 53
    assert len(resp.context["blog_updates"])


@pytest.mark.django_db
def test_search(client, django_assert_num_queries):
    with django_assert_num_queries(7):
        resp = client.get("/search/?query=moose")
    assert resp.status_code == 200
    assert len(resp.context["bills"]) == 1
    assert len(resp.context["people"]) == 0

    with django_assert_num_queries(6):
        resp = client.get("/search/?query=amanda")
    assert len(resp.context["bills"]) == 0
    assert len(resp.context["people"]) == 1


@pytest.mark.django_db
def test_state_specific_search(client):
    # test title search works
    resp = client.get("/ak/search/?query=moose")
    assert resp.status_code == 200
    assert len(resp.context["bills"]) == 1
    assert len(resp.context["people"]) == 0

    # test search in bill text works
    resp = client.get("/ak/search/?query=gorgonzola")
    assert len(resp.context["bills"]) == 1
    assert len(resp.context["people"]) == 0

    resp = client.get("/ak/search/?query=HB 1")
    assert resp.status_code == 200
    assert len(resp.context["bills"]) == 1

    resp = client.get("/ak/search/?query=hb 1")
    assert resp.status_code == 200
    assert len(resp.context["bills"]) == 1

    resp = client.get("/ak/search/?query=amanda")
    assert len(resp.context["bills"]) == 0
    assert len(resp.context["people"]) == 1

    resp = client.get("/al/search/?query=moose")
    assert resp.status_code == 200
    assert len(resp.context["bills"]) == 0
    assert len(resp.context["people"]) == 0

    resp = client.get("/al/search/?query=amanda")
    assert len(resp.context["bills"]) == 0
    assert len(resp.context["people"]) == 0
