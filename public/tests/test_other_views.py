import pytest
from testutils.populators import populate_db


@pytest.fixture(autouse=True)
def setup(db):
    populate_db()


@pytest.mark.django_db
def test_homepage(client, django_assert_num_queries):
    with django_assert_num_queries(7):
        resp = client.get("/")
    assert resp.status_code == 200
    assert len(resp.context["states"]) == 53


@pytest.mark.django_db
def test_state_specific_search_initial_query(client):
    # test title search works
    resp = client.post("/ak/search/", data={"query": "moose"}, follow=True)
    assert resp.redirect_chain[0][1] == 302
    assert resp.status_code == 200
    assert client.session["search_query"] == "moose"
    assert len(resp.context["bills"]) == 1
    assert len(resp.context["people"]) == 0

    # test search in bill text works
    resp = client.post("/ak/search/", data={"query": "gorgonzola"}, follow=True)
    assert resp.redirect_chain[0][1] == 302
    assert resp.status_code == 200
    assert client.session["search_query"] == "gorgonzola"
    assert len(resp.context["bills"]) == 1
    assert len(resp.context["people"]) == 0

    resp = client.post("/ak/search/", data={"query": "HB 1"}, follow=True)
    assert resp.redirect_chain[0][1] == 302
    assert resp.status_code == 200
    assert client.session["search_query"] == "HB 1"
    assert len(resp.context["bills"]) == 1

    resp = client.post("/ak/search/", data={"query": "hb 1"}, follow=True)
    assert resp.redirect_chain[0][1] == 302
    assert resp.status_code == 200
    assert client.session["search_query"] == "hb 1"
    assert len(resp.context["bills"]) == 1

    resp = client.post("/ak/search/", data={"query": "amanda"}, follow=True)
    assert resp.redirect_chain[0][1] == 302
    assert resp.status_code == 200
    assert client.session["search_query"] == "amanda"
    assert len(resp.context["bills"]) == 0
    assert len(resp.context["people"]) == 1

    resp = client.post("/al/search/", data={"query": "moose"}, follow=True)
    assert resp.redirect_chain[0][1] == 302
    assert resp.status_code == 200
    assert client.session["search_query"] == "moose"
    assert len(resp.context["bills"]) == 0
    assert len(resp.context["people"]) == 0

    resp = client.post("/al/search/", data={"query": "amanda"}, follow=True)
    assert resp.redirect_chain[0][1] == 302
    assert resp.status_code == 200
    assert client.session["search_query"] == "amanda"
    assert len(resp.context["bills"]) == 0
    assert len(resp.context["people"]) == 0


@pytest.mark.django_db
def test_state_specific_search_sessioning_for_filter_options(
    client, django_assert_num_queries
):

    # inital query, base bills exist -- should call get filter options and store in session
    with django_assert_num_queries(17):
        client.post("/ak/search/", data={"query": "moose"}, follow=True)

    session = client.session

    assert session["search_query"] == "moose"
    assert "filter_options" in session
    saved_filter_options = session["filter_options"]
    assert "subjects" in saved_filter_options

    # subsequent query with search options form -- should not call get filter options (fewer calls to DB)
    with django_assert_num_queries(7):
        client.get("/ak/search/?is_filter_form=true")

    session = client.session

    assert session["search_query"] == "moose"  # previous query saved in session
    assert session["filter_options"] == saved_filter_options

    session.clear()
    session.save()

    # initial query, base bills do not exist -- should not set filter options
    client.post("/ak/search/", data={"query": "buffalo"}, follow=True)

    session = client.session

    assert session["base_bills_exist"] is False
    assert "filter_options" not in session
