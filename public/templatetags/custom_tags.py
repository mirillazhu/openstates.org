import dateutil.parser
import json
import bleach
from django import template
from django.utils.safestring import mark_safe
import re
import us

from utils.common import states, pretty_url
from utils.orgs import get_legislature_from_abbr


register = template.Library()


@register.simple_tag()
def canonical_url(obj):
    return pretty_url(obj)


@register.inclusion_tag("public/components/header.html", takes_context=True)
def header(context):
    return {
        "user": context.get("user"),
        "state": context.get("state"),
        "state_nav": context.get("state_nav"),
        "messages": context.get("messages"),
        "states": states,
    }


@register.inclusion_tag("public/components/sources.html")
def sources(state, sources=None):
    if state:
        legislature = get_legislature_from_abbr(state)
        return {
            "legislature_name": legislature.name,
            "legislature_url": legislature.jurisdiction.url,
            "sources": sources,
        }


@register.inclusion_tag("public/components/pagination.html")
def pagination(page, request_get):
    request_get = request_get.copy()
    request_get.pop("page", None)
    return {"page": page, "base_querystring": request_get.urlencode()}


@register.inclusion_tag("public/components/bill-card.html")
def bill_card(state, bill):
    return {"state": state, "bill": bill}


@register.inclusion_tag("public/components/vote-card.html")
def vote_card(vote):
    # Model needs to be wrapped in a dict, per custom-tag requirements
    return {"vote": vote}


@register.inclusion_tag("public/components/action-card.html")
def action_card(action):
    # Model needs to be wrapped in a dict, per custom-tag requirements
    return {"action": action}


@register.inclusion_tag("public/components/document-card.html")
def document_card(document):
    return {"document": document}


@register.filter()
def state_name(state_abbr):
    # lookup returns None if there's no such state, but can't take a None value itself
    state = us.states.lookup(state_abbr or "")
    if state:
        return state.name
    return ""


@register.filter()
def party_pluralize(party_name, count):
    if party_name == "Democratic":
        party_name = "Democrat"

    if count > 1:
        return party_name + "s"
    else:
        return party_name


@register.filter()
def party_noun(party_name):
    if party_name == "Democratic":
        return "Democrat"
    else:
        return party_name


@register.filter()
def district_maybe(district):
    if district and str(district)[0] in "0123456789":
        return "District"
    else:
        return ""


@register.filter()
def party_color(party_name):
    if "Democratic" in party_name and "Republican" in party_name:  # just in case
        return "#fff3cd"
    elif "Democratic" in party_name:  # includes Democratic-Farmer-Labor party
        return "#cfe5f4"
    elif "Republican" in party_name:
        return "#f5d7db"
    elif party_name == "Unknown":
        return "#edf3f8"
    else:
        return "#fff3cd"


@register.filter()
def titlecase_caps(title):
    if title.isupper():
        return title.title()
    else:
        return title


@register.filter()
def titlecase_caps_for_votes(title):
    title = title.title()

    # uppercase bill abbreviations with vowels
    bill_abbreviations_with_vowels = {
        "AB",
        "ACR",
        "HRES",
        "SRES",
        "AJR",
        "AR",
        "CA",
        "HJRES",
    }
    pattern = r"\b(" + "|".join(bill_abbreviations_with_vowels) + r")(?=\s|\d|$)"
    title = re.sub(pattern, lambda m: m.group(1).upper(), title, flags=re.IGNORECASE)

    # uppercase bill abbreviations (or any words) with no vowels or y's
    title = re.sub(
        r"\b[a-zA-Z]+(?=\s|\d|$)",
        lambda m: m.group(0).upper()
        if not re.search(r"[aeiouyAEIOUY]", m.group(0))
        else m.group(0),
        title,
    )

    # lowercase letters after digits (e.g. 3rd)
    title = re.sub(r"(\d)([A-Z])", lambda m: m.group(1) + m.group(2).lower(), title)

    # fix apostrophes
    title = re.sub(r"’", "'", title)
    title = re.sub(r"'([A-Z])", lambda m: "'" + m.group(1).lower(), title)

    return title


@register.filter()
def dash_check(session):
    if "-" in session:
        return session.replace("-", "_")
    else:
        return session


@register.filter()
def format_uuid(person_id):
    return person_id.split("/")[1]


@register.filter()
def format_address(address):
    return mark_safe(address.replace(";", "<br>"))


@register.filter()
def jsonify(data):
    # Source: https://gist.github.com/pirate/c18bfe4fd96008ffa0aef25001a2e88f
    uncleaned = json.dumps(data)
    clean = bleach.clean(uncleaned)
    return mark_safe(clean)


@register.filter()
def fdate(date, format):
    if not date:
        return ""
    if isinstance(date, str):
        date = dateutil.parser.parse(date)
    return date.strftime(format)
