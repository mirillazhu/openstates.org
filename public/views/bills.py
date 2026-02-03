from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, reverse, redirect
from django.utils.feedgenerator import Rss201rev2Feed
from django.views.decorators.cache import never_cache
from openstates.data.models import (
    Bill,
    BillActionRelatedEntity,
    VoteEvent,
    Person,
)
from openstates.utils.transformers import fix_bill_id
from utils.common import (
    get_state_abbr,
    abbr_to_jid,
    jid_to_abbr,
    pretty_url,
)
from profiles.models import Subscription
from utils.bills import get_bills, get_filter_options, paginate_bills, get_sort_context
from utils.bill_stages import get_bill_chambers, compute_bill_stages
from .fallback import fallback


def bill_list(request, state):
    """
    form values:
        chamber: lower|upper
        session
        status: passed-lower-chamber|passed-upper-chamber|signed
        sponsor (ocd-person ID)
        classification
        subjects
    """
    bills, form = get_bills(request, state)
    paginator, page_num = paginate_bills(request, bills, 20)
    sort_context = get_sort_context(request, ["first_action", "latest_action"], [])

    # filter options: try to retrieve from cache or compute if none cached
    cache_key = f"filter_options_{state}"
    cached_filter_options = cache.get(cache_key)

    if cached_filter_options is not None:
        filter_options = cached_filter_options
    else:
        jid = abbr_to_jid(state)
        base_bills = Bill.objects.all().filter(
            legislative_session__jurisdiction_id=jid
        )  # compute filter options from all bills in state

        filter_options = get_filter_options(state, base_bills)
        cache.set(cache_key, filter_options, 60 * 60 * 12)  # cache for 12 hours

    context = {
        "state": state,
        "state_nav": "bills",
        "bills": paginator.page(page_num),
        "form": form,
        **sort_context,
    }
    context.update(filter_options)

    return render(request, "public/views/bills.html", context)


def bill_feed(request, state):
    bills, form = get_bills(request, state)
    host = request.get_host()
    link = "https://{}{}?{}".format(
        host,
        reverse("bills", kwargs={"state": state}),
        request.META["QUERY_STRING"],
    )
    feed_url = "https://%s%s?%s" % (
        host,
        reverse("bills_feed", kwargs={"state": state}),
        request.META["QUERY_STRING"],
    )
    description = f"{state.upper()} Bills"
    if form["session"]:
        description += f" ({form['session']})"
    # TODO: improve RSS description
    feed = Rss201rev2Feed(
        title=description,
        link=link,
        feed_url=feed_url,
        ttl=360,
        description=description,
    )
    for item in bills[:100]:
        link = "https://{}{}".format(host, pretty_url(item))
        description = f"""{item.title}<br />
                    Latest Action: {item.latest_action_description}
                    <i>{item.latest_action_date}</i>"""

        feed.add_item(
            title=item.identifier,
            link=link,
            unique_id=link,
            description=description,
        )
    return HttpResponse(feed.writeString("utf-8"), content_type="application/xml")


@login_required
@never_cache
def bill_dashboard(request):

    # get state for state dropdown
    state = request.session.get("selected_state", "")

    # clear cache so that unread count on dashboard page header always matches number of unread rows on dashboard
    cache.delete(f"unread_bills_{request.user.id}")

    # get all active bill subscriptions
    bill_subscriptions = (
        request.user.subscriptions.filter(
            bill_id__isnull=False,
            active=True,
        )
        .select_related("bill")
        .order_by("bill_id")
    )

    tracked_bills = []

    for subscription in bill_subscriptions:
        bill = subscription.bill

        bill_state_abbr = get_state_abbr(bill.legislative_session.jurisdiction.name)
        bill.identifier_with_state = f"{bill_state_abbr} {bill.identifier}"

        # get bill actions for determining (a) bill status and (2) whether the latest bill action is unread
        actions = list(
            bill.actions.all()
            .select_related("organization")
            .order_by("-date", "-order")
        )

        # determine bill status
        first_chamber, second_chamber = get_bill_chambers(bill, actions)
        bill_state = jid_to_abbr(bill.legislative_session.jurisdiction.id)
        _, latest_stage = compute_bill_stages(
            actions, first_chamber, second_chamber, bill_state
        )

        if latest_stage:
            bill.status = latest_stage["text"]
            if "Override" in bill.status:
                bill.status = "Veto " + bill.status  # add for clarity
        else:
            bill.status = (
                "Introduced in " + bill.from_organization.name
            )  # fallback for bills with no stages

        # determine if there has been a bill update since user last viewed bill
        latest_action = actions[0] if actions else None

        if subscription.last_viewed_bill_action_id and latest_action:
            if (
                subscription.last_viewed_bill_action_id != latest_action.id
            ):  # there is a new bill action
                bill.has_unread_action = True
            else:  # no new bill action; latest_action id is same as last viewed
                bill.has_unread_action = False
        elif latest_action:  # never viewed but has actions
            bill.has_unread_action = True
        else:  # bill has no actions
            bill.has_unread_action = False

        tracked_bills.append(bill)

    # sort tracked bills
    sort = request.GET.get("sort", "-latest_action")

    sort_key_mapping = {
        "bill_id": lambda b: b.identifier_with_state,
        "bill_title": lambda b: b.title.lower(),  # to ensure sort is independent of capitalization
        "bill_status": lambda b: b.status,
        "session": lambda b: b.legislative_session.name,
        "first_action": lambda b: b.first_action_date or "",
        "latest_action": lambda b: b.latest_action_date or "",
    }

    field = sort.lstrip("-")
    if field in sort_key_mapping:
        tracked_bills.sort(key=sort_key_mapping[field], reverse=sort.startswith("-"))

    # get sort context
    sortable_columns = list(sort_key_mapping.keys())
    ascending_by_default = [
        "bill_id",
        "bill_title",
        "bill_status",
    ]
    sort_context = get_sort_context(request, sortable_columns, ascending_by_default)

    # paginate
    paginator, page_num = paginate_bills(request, tracked_bills, 8)

    return render(
        request,
        "public/views/bill_dashboard.html",
        {"tracked_bills": paginator.page(page_num), "state": state, **sort_context},
    )


def _document_sort_key(doc):
    ordering = ["text/html", "application/pdf"]
    if doc.media_type in ordering:
        return (ordering.index(doc.media_type), doc.media_type)
    return (100, doc.media_type)


def bill(request, state, session, bill_id):

    request.session["selected_state"] = state

    # canonicalize without space
    if " " in bill_id:
        return redirect(
            "bill", state, session, bill_id.replace(" ", ""), permanent=True
        )

    jid = abbr_to_jid(state)
    identifier = fix_bill_id(bill_id)

    try:
        bill = Bill.objects.select_related(
            "legislative_session",
            "legislative_session__jurisdiction",
            "from_organization",
        ).get(
            legislative_session__jurisdiction_id=jid,
            legislative_session__identifier=session,
            identifier=identifier,
        )
    except Bill.DoesNotExist:
        # try to find the asset in S3
        request.path = request.path.replace(bill_id, identifier)
        return fallback(request)

    # sponsorships, attach people manually
    sponsorships = list(bill.sponsorships.all())
    sponsor_people = {
        p.id: p
        for p in Person.objects.filter(
            id__in=[s.person_id for s in sponsorships if s.person_id]
        ).prefetch_related(
            "memberships", "memberships__organization", "memberships__post"
        )
    }
    for s in sponsorships:
        s.person = sponsor_people.get(s.person_id)

    related_entities = Prefetch(
        "related_entities",
        BillActionRelatedEntity.objects.all().select_related("person", "organization"),
    )
    actions = list(
        bill.actions.all()
        .select_related("organization")
        .prefetch_related(related_entities)
        .order_by("-date", "-order")
    )
    votes = list(
        bill.votes.all().select_related("organization")
    )  # .prefetch_related('counts')

    # stage calculation and determination of whether bill is unicameral
    first_chamber, second_chamber = get_bill_chambers(bill, actions)
    stages, _ = compute_bill_stages(actions, first_chamber, second_chamber, state)

    unicameral = False
    if first_chamber == "Legislature" and second_chamber is None:
        unicameral = True

    versions = list(bill.versions.order_by("-date").prefetch_related("links"))
    documents = list(bill.documents.order_by("-date").prefetch_related("links"))
    try:
        sorted_links = sorted(versions[0].links.all(), key=_document_sort_key)
        read_link = sorted_links[0].url
    except IndexError:
        read_link = None

    # update last viewed bill action for dashboard read/unread logic
    latest_action = actions[0] if actions else None

    if request.user.is_authenticated and latest_action:

        # update last viewed bill action if active subscription
        updated = Subscription.objects.filter(
            user=request.user,
            bill=bill,
            active=True,
        ).update(last_viewed_bill_action_id=latest_action.id)

        # if there is an update to last viewed bill action, clear cache item that tracks number of unread bills (context_preprocessors.py)
        if updated > 0:
            cache.delete(f"unread_bills_{request.user.id}")

    return render(
        request,
        "public/views/bill.html",
        {
            "state": state,
            "state_nav": "bills",
            "unicameral": unicameral,
            "bill": bill,
            "sponsorships": sponsorships,
            "actions": actions,
            "stages": stages,
            "votes": votes,
            "versions": versions,
            "documents": documents,
            "read_link": read_link,
        },
    )


def _vote_sort_key(v):
    if v.option == "yes":
        return (1, v.option)
    elif v.option == "no":
        return (2, v.option)
    else:
        return (3, v.option)


def vote(request, vote_id):
    vote = get_object_or_404(
        VoteEvent.objects.all().select_related(
            "organization",
            "legislative_session",
            "bill",
            "bill__legislative_session",
            "bill__from_organization",
            "bill__legislative_session__jurisdiction",
        ),
        pk="ocd-vote/" + vote_id,
    )

    state = jid_to_abbr(vote.organization.jurisdiction_id)
    request.session["selected_state"] = state

    vote_counts = sorted(vote.counts.all(), key=_vote_sort_key)
    person_votes = sorted(
        vote.votes.all().select_related("voter"),
        key=lambda pv: (
            _vote_sort_key(pv),
            pv.voter.name if pv.voter else pv.voter_name,
        ),
    )

    # add percentages to vote_counts
    total = sum(vc.value for vc in vote_counts)
    if total:
        for vc in vote_counts:
            vc.percent = vc.value / total * 100

    # party -> option -> value
    party_votes = defaultdict(lambda: defaultdict(int))

    # attach party to people & calculate party-option crosstab
    for pv in person_votes:
        # combine other options
        if pv.option not in ("yes", "no"):
            option = "other"
        else:
            option = pv.option

        if pv.voter and pv.voter.primary_party:
            pv.party = pv.voter.primary_party
            party_votes[pv.party][option] += 1
        else:
            party_votes["Unknown"][option] += 1

    # only show party breakdown if most people are matched
    votes_with_party = len(
        [pv for pv in person_votes if pv.voter and pv.voter.primary_party]
    )
    if not person_votes or (votes_with_party / len(person_votes) < 0.8):
        party_votes = None
    else:
        party_votes = sorted(dict(party_votes).items())

    # determine whether to display parties field in roll call header
    has_voter_parties = any(hasattr(pv, "party") and pv.party for pv in person_votes)

    return render(
        request,
        "public/views/vote.html",
        {
            "state": state,
            "state_nav": "bills",
            "vote": vote,
            "vote_counts": vote_counts,
            "person_votes": person_votes,
            "party_votes": party_votes,
            "has_voter_parties": has_voter_parties,
        },
    )
