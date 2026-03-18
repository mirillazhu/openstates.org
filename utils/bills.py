import re
from django.contrib.postgres.search import SearchQuery
from django.core.paginator import Paginator, EmptyPage
from django.db.models import F, Func
from django.http import Http404
from openstates.data.models import Bill, Person
from openstates.utils.transformers import fix_bill_id
from .common import abbr_to_jid, sessions_with_bills
from .orgs import get_chambers_from_abbr
import snowballstemmer

# decision was made in openstates/issues#193 to exclude these by default to not confuse users
EXCLUDED_CLASSIFICATIONS = ["proposed bill"]


class Unnest(Func):
    function = "UNNEST"


def replace_query_params(request, **params):
    get = request.GET.copy()
    for k, v in params.items():
        get[k] = v
    return request.path + "?" + get.urlencode()


stemmer = snowballstemmer.stemmer("english")


SYNONYM_GROUPS = [
    # budget and finance
    ["appropriation", "funding", "allocation", "budget", "expenditure"],
    ["revenue", "income", "earnings"],
    ["tax", "levy", "tariff"],
    ["deficit", "shortfall", "debt"],
    ["fee", "surcharge", "fine"],
    # education
    ["education", "school", "learning", "instruction"],
    ["student", "pupil", "learner"],
    ["teacher", "instructor", "educator", "faculty"],
    ["university", "college", "higher education"],
    ["scholarship", "financial aid", "tuition assistance"],
    # healthcare
    ["prescription", "medication", "pharmaceutical"],
    ["doctor", "physician"],
    ["vaccine", "immunization"],
    ["addiction", "substance abuse", "drug abuse", "substance use"],
    ["abortion", "reproductive"],
    # housing
    ["landlord", "lessor"],
    ["tenant", "rent", "lessee", "occupant"],
    ["mortgage", "home loan", "housing loan"],
    # crime and justice
    ["prison", "correction", "jail", "incarceration"],
    ["parole", "supervised release", "community supervision", "compassionate release"],
    ["probation", "supervised release", "community supervision"],
    ["law enforcement", "police", "sheriff"],
    ["bail", "pretrial"],
    ["dog", "canine"],
    ["drug", "substance", "narcotic"],
    ["crime", "offense", "violation", "felony"],
    ["criminal", "offender", "inmate", "incarcerated individual"],
    ["attorney", "lawyer", "public defender"],
    ["sentence", "conviction", "resentencing"],
    ["juvenile", "youth"],
    ["solitary", "isolated confinement", "restrictive housing"],
    ["death penalty", "capital punishment", "execution"],
    ["oversight", "ombudsman"],
    ["record clearing", "clean slate", "erasure", "expungement"],
    # environment
    ["environment", "ecology", "natural resources", "conservation"],
    ["farm", "agriculture"],
    ["pollution", "contamination", "emissions"],
    ["climate", "global warming", "greenhouse gas"],
    # infrastructure
    ["infrastructure", "public works", "utilities"],
    ["transportation", "transit", "commute"],
    ["highway", "freeway", "expressway"],
    ["broadband", "internet", "telecommunications", "connectivity"],
    ["phone", "communication"],
    ["artificial intelligence", "ai", "algorithm"],
    # social services
    ["welfare", "public assistance", "social services", "benefits"],
    ["unemployment", "joblessness"],
    ["disability", "impairment", "handicap"],
    ["veteran", "military service", "servicemember"],
    ["social security", "retirement", "pension"],
    ["child care", "childcare", "early childhood"],
    ["divorce", "child custody", "alimony"],
    ["nutrition", "food assistance", "food security"],
    ["poverty", "low income", "poor"],
    ["senior", "elderly", "aging"],
    # immigration
    ["asylum", "refugee", "displaced person"],
    ["citizenship", "naturalization", "green card"],
    ["undocumented", "immigrant", "sanctuary", "immigration detention"],
    # business
    ["license", "permit", "certification"],
    ["small business", "startup", "entrepreneur"],
    # labor and civil rights
    ["worker", "employee", "laborer"],
    ["wage", "salary", "compensation", "pay", "earnings"],
    ["union", "collective bargaining", "labor organization"],
    ["workplace", "work environment", "osha"],
    ["discrimination", "bias", "inequity", "prejudice"],
    ["religious freedom", "religion", "faith", "church"],
    # government
    ["election", "vote", "ballot", "disenfranchisement"],
    ["redistricting", "gerrymandering", "reapportionment"],
    ["municipality", "county", "local government"],
]


SYNONYM_MAP = {}
for group in SYNONYM_GROUPS:
    stemmed_group = [stemmer.stemWord(term) for term in group]
    for term in group:
        SYNONYM_MAP[stemmer.stemWord(term)] = stemmed_group


def _make_search_query(term):
    words = term.strip().split()
    if len(words) == 1:
        return SearchQuery(term, config="english", search_type="plain")
    else:
        # treat multi-word synonyms as phrases
        return SearchQuery(term, config="english", search_type="phrase")


def _expand_query(query_string):
    terms = query_string.lower().split()
    expanded_terms = []
    for term in terms:
        stemmed_term = stemmer.stemWord(term)
        synonyms = SYNONYM_MAP.get(
            stemmed_term, [term]
        )  # fallback to original term if term is not in synonym mapping

        # apply search query with plain search_type to each synonym individually to ensure proper stemming
        # use english config to match stemming used to generate search vectors
        synonym_queries = [_make_search_query(synonym) for synonym in synonyms]

        # combine stemmed synonyms with 'or'
        combined = synonym_queries[0]
        for q in synonym_queries[1:]:
            combined = combined | q
        expanded_terms.append(combined)

    # combine expanded term groups with 'and'
    result = expanded_terms[0]
    for q in expanded_terms[1:]:
        result = result & q

    return result


def search_bills(
    *,
    sort,
    bills=None,
    query=None,
    state=None,
    chamber=None,
    session=None,
    sponsor=None,
    sponsor_name=None,
    classification=None,
    exclude_classifications=None,
    subjects=None,
    status=None,
):
    if bills is None:
        bills = Bill.objects.all().select_related(
            "legislative_session",
            "legislative_session__jurisdiction",
        )
    if state:
        jid = abbr_to_jid(state.lower())
        bills = bills.filter(legislative_session__jurisdiction_id=jid)
    if query:
        if re.match(r"\w{1,3}\s*\d{1,5}", query):  # bill id, e.g. SB 23
            bills = bills.filter(identifier__iexact=fix_bill_id(query))
        else:  # bill keywords
            bills = bills.filter(searchable__search_vector=_expand_query(query))
    if chamber:
        bills = bills.filter(from_organization__classification=chamber)
    if session:
        bills = bills.filter(legislative_session__identifier=session)
    if sponsor:
        bills = bills.filter(sponsorships__person_id=sponsor)
    if sponsor_name:
        bills = bills.filter(sponsorships__person__name=sponsor_name)
    if classification:
        bills = bills.filter(classification__contains=[classification])
    elif exclude_classifications:
        bills = bills.exclude(classification__contains=exclude_classifications)
    if subjects:
        bills = bills.filter(subject__overlap=subjects)

    if not status:
        status = []
    if "passed-lower-chamber" in status:
        bills = bills.filter(
            actions__classification__contains=["passage"],
            actions__organization__classification="lower",
        )
    elif "passed-upper-chamber" in status:
        if state == "dc" or state == "ne":  # unicameral
            bills = bills.filter(
                actions__classification__contains=["passage"],
                actions__organization__classification="legislature",
            )
        else:
            bills = bills.filter(
                actions__classification__contains=["passage"],
                actions__organization__classification="upper",
            )
    elif "signed" in status:
        bills = bills.filter(actions__classification__contains=["executive-signature"])

    if sort is None:
        pass
    elif sort == "-updated":
        bills = bills.order_by("-updated_at")
    elif sort == "first_action":
        bills = bills.order_by(F("first_action_date").asc(nulls_last=True))
    elif sort == "-first_action":
        bills = bills.order_by(F("first_action_date").desc(nulls_last=True))
    elif sort == "latest_action":
        bills = bills.order_by(F("latest_action_date").asc(nulls_last=True))
    else:  # -latest_action, or not specified
        bills = bills.order_by(F("latest_action_date").desc(nulls_last=True))

    return bills


def get_bills(request, state, allow_query=True):
    # query parameter filtering
    query = request.GET.get("query", "") if allow_query else ""
    chamber = request.GET.get("chamber")
    session = request.GET.get("session")
    sponsor = request.GET.get("sponsor")
    sponsor_name = request.GET.get("sponsor_name")
    classification = request.GET.get("classification")
    q_subjects = request.GET.getlist("subjects")
    status = request.GET.getlist("status")
    sort = request.GET.get("sort", "-latest_action")

    form = {
        "chamber": chamber,
        "session": session,
        "sponsor": sponsor,
        "sponsor_name": sponsor_name,
        "classification": classification,
        "subjects": q_subjects,
        "status": status,
    }

    bills = search_bills(
        state=state,
        query=query,
        chamber=chamber,
        session=session,
        sponsor=sponsor,
        sponsor_name=sponsor_name,
        classification=classification,
        exclude_classifications=EXCLUDED_CLASSIFICATIONS,
        subjects=q_subjects,
        status=status,
        sort=sort,
    )

    return bills, form


def get_search_summary(form, sessions, chambers, sponsors):
    summary = []

    if form["classification"] and form["chamber"]:
        summary.append(
            f'{chambers[form["chamber"]]} {form["classification"].title()}s only'
        )
    elif form["classification"]:
        summary.append(f'{form["classification"].title()}s only')
    elif form["chamber"]:
        if form["chamber"] not in chambers:
            raise Http404()
        summary.append(f'{chambers[form["chamber"]]} only')

    if form["session"]:
        # this is almost always bad crawlers or XSS attempts
        if form["session"] not in sessions:
            raise Http404()
        summary.append("from " + sessions[form["session"]])
    if form["sponsor"]:
        # there are ways this can happen that are legit, so just warn about it
        if form["sponsor"] not in sponsors:
            summary.append("invalid sponsor")
        else:
            summary.append(f"sponsored by {sponsors[form['sponsor']]}")
    if form["sponsor_name"]:
        summary.append(f"sponsored by {form['sponsor_name']}")
    if form["subjects"]:
        summary.append(f"including subjects {', '.join(form['subjects'])}")

    status_text = []
    if "passed-lower-chamber" in form["status"]:
        status_text.append(f"passed in the {chambers['lower']}")
    if "passed-upper-chamber" in form["status"]:
        if "legislature" in chambers:
            status_text.append(f"passed in the {chambers['legislature']}")
        else:
            status_text.append(f"passed in the {chambers['upper']}")
    if "signed" in form["status"]:
        status_text.append("been signed into law")

    if status_text:
        summary.append("which have " + " and ".join(status_text))

    return ", ".join(summary)


def get_filter_options(state, base_bills):
    options = {}
    jid = abbr_to_jid(state)
    chambers = get_chambers_from_abbr(state)
    options["chambers"] = {c.classification: c.name for c in chambers}
    options["sessions"] = {s.identifier: s.name for s in sessions_with_bills(jid)}

    classifications = base_bills.annotate(
        type=Unnest("classification", distinct=True)
    ).values_list("type", flat=True)
    options["classifications"] = sorted(set(classifications))

    subjects = base_bills.annotate(sub=Unnest("subject", distinct=True)).values_list(
        "sub", flat=True
    )
    options["subjects"] = sorted(set(subjects))

    sponsor_ids = base_bills.values_list(
        "sponsorships__person_id", flat=True
    ).distinct()
    sponsor_names = {
        p.name
        for p in Person.objects.filter(
            id__in=sponsor_ids,
            memberships__organization__jurisdiction_id=jid,
        )
        .order_by("name")
        .distinct()
    }
    options["sponsor_names"] = sorted(set(sponsor_names))

    return options


def paginate_bills(request, bills, page_size):
    # handle pagination for bills queryset
    try:
        page_num = int(request.GET.get("page", 1))
    except ValueError:
        raise Http404()  # invalid pages not found
    paginator = Paginator(bills, page_size)
    try:
        bills = paginator.page(page_num)
    except EmptyPage:
        raise Http404()

    return paginator, page_num


def get_sort_context(request, sortable_columns, ascending_by_default):
    # get sort urls & arrows
    sort = request.GET.get("sort", "-latest_action")

    context = {}
    for col_name in sortable_columns:
        arrow = ""

        if col_name in ascending_by_default:
            if sort == col_name:
                sort_url = replace_query_params(request, sort=f"-{col_name}", page=1)
                arrow = "\u2191"  # up
            else:
                sort_url = replace_query_params(request, sort=col_name, page=1)
                if sort == f"-{col_name}":
                    arrow = "\u2193"  # down
        else:  # descending sort
            if sort == f"-{col_name}":
                sort_url = replace_query_params(request, sort=col_name, page=1)
                arrow = "\u2193"  # down
            else:
                sort_url = replace_query_params(request, sort=f"-{col_name}", page=1)
                if sort == col_name:
                    arrow = "\u2191"  # up

        context[f"{col_name}_sort_url"] = sort_url
        context[f"{col_name}_arrow"] = arrow

    return context
