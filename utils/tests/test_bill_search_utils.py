import pytest
from django.contrib.postgres.search import (
    CombinedSearchQuery,
    SearchQuery,
    SearchVector,
)
from django.db import connection
from django.db.models.sql.query import Query
from openstates.data.models import SearchableBill
from utils.bill_search import _make_search_query, expand_query


# fixture to provide compiler for tests using as_sql
@pytest.fixture
def query_compiler():
    django_query = Query(model=None)
    return django_query.get_compiler(connection=connection)


# helper function to extract the set of search terms in the combined query
def extract_search_terms(query):
    if isinstance(query, SearchQuery) and not isinstance(query, CombinedSearchQuery):
        value_obj = query.source_expressions[1]
        return [value_obj.value]
    elif isinstance(query, CombinedSearchQuery):
        return extract_search_terms(query.lhs) + extract_search_terms(query.rhs)
    else:
        return []


def test_make_search_query_single_word():
    result = _make_search_query("resources")

    assert isinstance(result, SearchQuery)
    assert result.function == "plainto_tsquery"  # plain search
    assert str(result.config.config.value) == "english"


def test_make_search_query_phrase():
    result = _make_search_query("natural resources")

    assert isinstance(result, SearchQuery)
    assert result.function == "phraseto_tsquery"
    assert str(result.config.config.value) == "english"


def test_expand_query_single_word_no_synonyms():
    query = expand_query("foccacia")
    terms = extract_search_terms(query)
    assert len(terms) == 1
    assert set(terms) == {"foccacia"}


def test_expand_query_multiple_words_no_synonyms(query_compiler):
    query = expand_query("sesame foccacia")
    terms = extract_search_terms(query)
    assert len(terms) == 2
    assert set(terms) == {"sesame", "foccacia"}

    sql, _ = query.as_sql(query_compiler, connection)
    assert "&&" in sql or "AND" in sql
    assert "||" not in sql and "OR" not in sql


def test_expand_query_word_with_synonyms(query_compiler):
    query = expand_query("permit")
    terms = extract_search_terms(query)
    assert len(terms) == 3
    assert set(terms) == {"licens", "permit", "certif"}  # synonyms stemmed

    sql, _ = query.as_sql(query_compiler, connection)
    assert "||" in sql or "OR" in sql
    assert "&&" not in sql and "AND" not in sql


def test_expand_query_stemmed_word_with_synonyms(query_compiler):
    query = expand_query("permits")
    terms = extract_search_terms(query)
    assert len(terms) == 3
    assert set(terms) == {"licens", "permit", "certif"}  # synonyms stemmed

    sql, _ = query.as_sql(query_compiler, connection)
    assert "||" in sql or "OR" in sql
    assert "&&" not in sql and "AND" not in sql


def test_expand_query_multiple_words_with_synonyms(query_compiler):
    query = expand_query("sesame foccacia taxes")
    terms = extract_search_terms(query)
    assert len(terms) == 5
    assert set(terms) == {"sesame", "foccacia", "tax", "levi", "tariff"}

    sql, _ = query.as_sql(query_compiler, connection)
    assert "&&" in sql or "AND" in sql
    assert "||" in sql or "OR" in sql


@pytest.mark.django_db
def test_expand_query_find_bills():
    SearchableBill.objects.create(
        all_titles="Sesame Foccacia Referendum",
        raw_text="Reduce taxes on sesame foccacia",
        search_vector="",
    )
    SearchableBill.objects.create(
        all_titles="Everything Bagel Referendum",
        raw_text="Sesame must be on everything bagels",
        search_vector="",
    )
    SearchableBill.objects.update(
        search_vector=SearchVector("raw_text", config="english")
    )

    query = expand_query("sesame tariffs")
    results = SearchableBill.objects.filter(search_vector=query)

    assert results.count() == 1
    assert "Reduce taxes on sesame foccacia" in results.first().raw_text
