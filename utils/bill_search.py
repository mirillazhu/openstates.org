from django.contrib.postgres.search import SearchQuery
import snowballstemmer


stemmer = snowballstemmer.stemmer("english")


SYNONYM_GROUPS = [
    # budget and finance
    ["appropriation", "funding", "allocation", "budget", "expenditure"],
    ["tax", "levy", "tariff"],
    ["deficit", "shortfall", "debt"],
    ["fee", "surcharge", "fine"],
    # education
    ["education", "school", "learning"],
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
    ["healthcare", "health"],
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
    ["crime", "offense", "felony"],
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
    ["religious freedom", "religion", "faith"],
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

    # use english config to match stemming used to generate search vectors
    if len(words) == 1:
        # apply search query with plain search_type to each term individually to ensure proper stemming
        return SearchQuery(term, config="english", search_type="plain")
    else:
        # treat multi-word synonyms as phrases
        return SearchQuery(term, config="english", search_type="phrase")


def expand_query(query_string):
    terms = query_string.lower().split()
    expanded_terms = []
    for term in terms:
        stemmed_term = stemmer.stemWord(term)
        synonyms = SYNONYM_MAP.get(
            stemmed_term, [term]
        )  # fallback to original term if stemmed term is not in synonym mapping

        synonym_queries = [_make_search_query(synonym) for synonym in synonyms]

        # combine stemmed synonyms with 'or'
        combined = synonym_queries[0]
        for query in synonym_queries[1:]:
            combined = combined | query
        expanded_terms.append(combined)

    # combine expanded term groups with 'and'
    result = expanded_terms[0]
    for query in expanded_terms[1:]:
        result = result & query

    return result
