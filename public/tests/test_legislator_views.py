import pytest
from graphapi.tests.utils import populate_db
from openstates.data.models import Person
from public.views.legislators import _people_from_lat_lon
from utils.common import pretty_url


@pytest.mark.django_db
def setup():
    populate_db()


@pytest.mark.django_db
def test_legislators_view(client, django_assert_num_queries):
    with django_assert_num_queries(12):
        resp = client.get("/ak/legislators/")
    assert resp.status_code == 200
    assert resp.context["state"] == "ak"
    assert resp.context["state_nav"] == "legislators"
    assert len(resp.context["chambers"]) == 2
    assert len(resp.context["legislators"]) == 6


@pytest.mark.django_db
def test_person_view(client, django_assert_num_queries):
    p = Person.objects.get(name="Amanda Adams")
    with django_assert_num_queries(17):
        resp = client.get(pretty_url(p))
    assert resp.status_code == 200
    assert resp.context["state"] == "ak"
    assert resp.context["state_nav"] == "legislators"
    person = resp.context["person"]
    assert person.name == "Amanda Adams"
    assert person.primary_party == "Republican"
    assert (
        person.current_jurisdiction_id
        == "ocd-jurisdiction/country:us/state:ak/government"
    )
    assert person.current_role == {
        "org_classification": "lower",
        "district": 1,
        "division_id": "ocd-division/country:us/state:ak/sldl:1",
        "title": "Representative",
    }
    assert person.selected_link.url == "https://amandaadamsforstaterep.com"
    assert len(person.sponsored_bills) == 2
    assert len(person.vote_events) == 1
    assert resp.context["retired"] is False


@pytest.mark.django_db
def test_person_view_retired(client, django_assert_num_queries):
    p = Person.objects.get(name="Rhonda Retired")
    # fewer views, we don't do the bill queries
    with django_assert_num_queries(17):
        resp = client.get(pretty_url(p))
    assert resp.status_code == 200
    assert resp.context["state"] == "ak"
    assert resp.context["state_nav"] == "legislators"
    person = resp.context["person"]
    assert person.name == "Rhonda Retired"
    assert resp.context["retired"] is True


@pytest.mark.django_db
def test_person_view_invalid_uuid(client, django_assert_num_queries):
    p = Person.objects.get(name="Rhonda Retired")
    resp = client.get(
        pretty_url(p)[:-1] + "abcdefghij/"
    )  # this won't be a valid pretty UUID
    assert resp.status_code == 404


@pytest.mark.django_db
def test_people_from_lat_lon(django_assert_num_queries):
    lat = 44.4032
    lon = -104.3700  # sundance, wyoming (WY State House 1)

    with django_assert_num_queries(2):
        people = _people_from_lat_lon(lat, lon)
        assert len(people) == 2

        names = set(p["name"] for p in people)
        assert names == set(["Greta Gonzalez", "Hank Horn"])


@pytest.mark.django_db
def test_people_from_lat_lon_past_memberships(django_assert_num_queries):
    lat = 59.4166667
    lon = -135.9330556  # wells, alaska (AK State House 3, Senate B)

    with django_assert_num_queries(2):
        people = _people_from_lat_lon(lat, lon)
        assert len(people) == 2

        names = set(p["name"] for p in people)
        assert (
            "Rhonda Retired" not in names
        )  # previously AK Senate B but should not be included because she is retired
        assert names == set(["Carrie Carr", "Frank Fur"])


@pytest.mark.django_db
def test_people_from_lat_lon_no_legislators(django_assert_num_queries):
    lat = 42.368195
    lon = -73.285858  # lenox, massachusetts (no test DB legislators for MA)

    with django_assert_num_queries(1):
        people = _people_from_lat_lon(lat, lon)
        assert len(people) == 0


# TODO: test _people_from_lat_lon with federal legislators
