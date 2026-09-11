import datetime
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from openstates.data.models import Bill, Person, Membership
from utils.common import decode_uuid, jid_to_abbr, pretty_url
from utils.geo import coords_to_divisions
from utils.orgs import get_chambers_from_abbr
from utils.people import person_as_dict


def _people_from_lat_lon(lat, lon):
    today = datetime.date.today()

    # map coordinates to division, then filter legislators by specified division
    legislators_qs = Person.objects.all()

    if lat and lon:
        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            raise ValueError("invalid lat or lon")

        divisions = coords_to_divisions(lat, lon)

        legislators_qs = legislators_qs.filter(
            Q(memberships__post__division__id__in=divisions),
            Q(memberships__end_date="") | Q(memberships__end_date__gt=today),
        )

    elif lat or lon:
        raise ValueError("must provide lat & lon together")

    # build memberships queryset for prefetch related
    memberships_qs = Membership.objects.filter(
        Q(start_date="") | Q(start_date__lte=today),
        Q(end_date="") | Q(end_date__gte=today),
    )  # current memberships only

    memberships_qs = memberships_qs.filter(
        organization__classification__in=["upper", "lower", "legislature"]
    )  # exclude committee, subcommittee, executive

    memberships_qs = memberships_qs.select_related(
        "post",
        "post__division",
        "organization",
    )

    # prefetch memberships
    legislators_qs = legislators_qs.prefetch_related(
        Prefetch(
            "memberships",
            queryset=memberships_qs,
            to_attr="current_memberships",
        )
    )

    people = []

    for legislator in legislators_qs:
        person = {
            "id": legislator.id,
            "name": legislator.name,
            "image": legislator.image,
            "party": legislator.primary_party,
            "pretty_url": pretty_url(legislator),
        }
        for membership in legislator.current_memberships:
            person["chamber"] = membership.organization.classification
            person["district"] = membership.post.label
            person["division_id"] = membership.post.division.id
            person["jurisdiction_id"] = membership.organization.jurisdiction_id
            person["level"] = (
                "federal"
                if membership.organization.jurisdiction_id
                == "ocd-jurisdiction/country:us/government"
                else "state"
            )
            break
        people.append(person)

    return people


def find_your_legislator(request, state):
    request.session["selected_state"] = state

    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    json = request.GET.get("json")

    if json and lat and lon:
        # got a passed lat/lon. Let's build off it.
        people = _people_from_lat_lon(lat, lon)
        return JsonResponse({"legislators": people})

    address = request.POST.get("address")

    return render(
        request,
        "public/views/find_your_legislator.html",
        {"state": state, "address": address},
    )


def legislators(request, state):
    request.session["selected_state"] = state

    chambers = get_chambers_from_abbr(state)

    legislators = [
        person_as_dict(p)
        for p in Person.objects.current_legislators_with_roles(chambers)
    ]

    chambers = {c.classification: c.name for c in chambers}

    return render(
        request,
        "public/views/legislators.html",
        {
            "state": state,
            "chambers": chambers,
            "legislators": legislators,
            "state_nav": "legislators",
        },
    )


def person(request, person_id):

    SPONSORED_BILLS_TO_SHOW = 4
    RECENT_VOTES_TO_SHOW = 3

    try:
        ocd_person_id = decode_uuid(person_id)
    except ValueError:
        ocd_person_id = (
            person_id  # will be invalid and raise 404, but useful in logging later
        )
    person = get_object_or_404(
        Person.objects.prefetch_related("memberships__organization"),
        pk=ocd_person_id,
    )

    # to display district in front of district name, or not?
    district_maybe = ""

    # canonicalize the URL
    canonical_url = pretty_url(person)
    if request.path != canonical_url:
        return redirect(canonical_url, permanent=True)

    if not person.current_jurisdiction_id:
        state = None
        retired = True
    elif not person.current_role:
        #  this breaks if they held office in two states, but we don't really worry about that
        state = jid_to_abbr(person.current_jurisdiction_id)
        retired = True
    else:
        state = jid_to_abbr(person.current_jurisdiction_id)
        retired = False
        # does it start with a number?
        if str(person.current_role["district"])[0] in "0123456789":
            district_maybe = "District"

    # choose one person link to list -- filter out specific kinds of links, then choose shortest link
    person_links = list(person.links.all())
    keywords_to_exclude = [
        "conflict of interest",
        "linkedin",
        "youtube",
        "radio show",
        "finance",
    ]

    person_links = [
        link
        for link in person_links
        if not link.note
        or not any(word in link.note.lower() for word in keywords_to_exclude)
    ]

    person.selected_link = min(
        person_links, key=lambda link: len(link.url), default=None
    )

    # choose at most one office of each classification to display
    person_offices = list(
        person.offices.all().order_by("classification", "address")
    )  # fix an order
    selected_offices = []
    added_classifications = []

    for office in person_offices:
        if office.classification not in added_classifications:
            added_classifications.append(office.classification)
            selected_offices.append(office)

    person.selected_offices = selected_offices

    person.sponsored_bills = list(
        Bill.objects.all()
        .select_related(
            "legislative_session",
            "legislative_session__jurisdiction",
        )
        .filter(sponsorships__person=person)
        .order_by("-created_at", "id")[:SPONSORED_BILLS_TO_SHOW]
    )

    person.committee_memberships = person.memberships.filter(
        organization__classification="committee"
    ).all()

    votes = (
        person.votes.all()
        .select_related("vote_event", "vote_event__bill")
        .order_by(
            "-vote_event__start_date",
            "vote_event__bill__identifier",
            "vote_event__motion_text",
        )[:RECENT_VOTES_TO_SHOW]
    )
    person.vote_events = []
    for vote in votes:
        vote_event = vote.vote_event
        vote_event.legislator_vote = vote
        person.vote_events.append(vote_event)

    request.session["selected_state"] = state

    return render(
        request,
        "public/views/legislator.html",
        {
            "state": state,
            "person": person,
            "state_nav": "legislators",
            "retired": retired,
            "district_maybe": district_maybe,
        },
    )
