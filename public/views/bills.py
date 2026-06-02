import json
from collections import defaultdict
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.cache import never_cache
from openstates.data.models import (
    Bill,
    BillActionRelatedEntity,
    VoteEvent,
    Person,
    BillVersionLink,
    BillDocumentLink,
)
from utils.common import (
    DEFAULT_STATE,
    get_state_abbr,
    abbr_to_jid,
    jid_to_abbr,
)
from utils.bills import (
    get_bills,
    get_search_summary,
    get_filter_options,
    get_sort_context,
    paginate_bills,
    PageOutOfBounds,
    hacky_motion_text,
)
from utils.bill_stages import get_bill_chambers, compute_bill_stages
from utils.bill_subscriptions import (
    get_bill_subscriptions,
    follow_bill,
    unfollow_bill,
    is_bill_followed,
    update_last_viewed_bill_action,
)
from .fallback import fallback
import requests
import boto3


def bills(request, state):
    """
    form values:
        chamber: lower|upper
        session
        status: passed-lower-chamber|passed-upper-chamber|signed
        sponsor (ocd-person ID)
        classification
        subjects
    """

    bills, form = get_bills(request, state, query=None)
    try:
        paginator, page_num = paginate_bills(request, bills, 20)
    except PageOutOfBounds:
        raise Http404()
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
    context["search_summary"] = get_search_summary(
        context["form"],
        context["sessions"],
        context["chambers"],
    )

    return render(request, "public/views/bills.html", context)


@never_cache
def bill_dashboard(request):

    # get state for state dropdown
    state = DEFAULT_STATE.abbr.lower()

    # clear cache so that unread count on dashboard page header always matches number of unread rows on dashboard
    session_key = request.session.session_key
    cache.delete(f"unread_bills_{session_key}")

    # get all bill subscriptions
    bill_subscriptions = get_bill_subscriptions(
        request, get_related_fields=True
    )  # includes legislative session, jurisdiction, organization for bills

    # loop through bill subscriptions to append additional fields
    for bill in bill_subscriptions:
        bill_state_abbr = get_state_abbr(bill.legislative_session.jurisdiction.name)
        bill.identifier_with_state = f"{bill_state_abbr} {bill.identifier}"

        # get bill actions for determining (a) bill status and (2) whether the latest bill action is unread
        actions = list(
            bill.actions.all()
        )  # actions prefetched in descending order in get_bill_subscriptions

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

        if bill.last_viewed_bill_action_id and latest_action:
            if bill.last_viewed_bill_action_id != str(
                latest_action.id
            ):  # there is a new bill action
                bill.has_unread_action = True
            else:  # no new bill action; latest_action id is same as last viewed
                bill.has_unread_action = False
        elif latest_action:  # never viewed but has actions
            bill.has_unread_action = True
        else:  # bill has no actions
            bill.has_unread_action = False

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

    # convert bills from queryset to list for sorting
    bill_subscriptions = list(bill_subscriptions)

    field = sort.lstrip("-")
    if field in sort_key_mapping:
        bill_subscriptions.sort(
            key=sort_key_mapping[field], reverse=sort.startswith("-")
        )

    # get sort context
    sortable_columns = list(sort_key_mapping.keys())
    ascending_by_default = [
        "bill_id",
        "bill_title",
        "bill_status",
    ]
    sort_context = get_sort_context(request, sortable_columns, ascending_by_default)

    # paginate
    try:
        paginator, page_num = paginate_bills(request, bill_subscriptions, 8)
    except PageOutOfBounds as e:
        params = request.GET.copy()
        params["page"] = e.last_page
        return redirect(f"{request.path}?{params.urlencode()}")

    return render(
        request,
        "public/views/bill_dashboard.html",
        {"tracked_bills": paginator.page(page_num), "state": state, **sort_context},
    )


def bill_subscription(request):

    if request.method == "POST":
        bill_id = json.loads(request.body)["bill_id"]
        latest_action_id = json.loads(request.body)["latest_action_id"]
        follow_bill(request, bill_id, latest_action_id)
        active = True
    elif request.method == "DELETE":
        bill_id = json.loads(request.body)["bill_id"]
        unfollow_bill(request, bill_id)
        active = False

    return JsonResponse({"active": active, "bill_id": bill_id})


def _document_sort_key(doc):
    ordering = ["text/html", "application/pdf"]
    if doc.media_type in ordering:
        return (ordering.index(doc.media_type), doc.media_type)
    return (100, doc.media_type)


def bill(request, state, session, bill_id):

    jid = abbr_to_jid(state)
    bill_id = "ocd-bill/" + bill_id

    try:
        bill = Bill.objects.select_related(
            "legislative_session",
            "legislative_session__jurisdiction",
            "from_organization",
        ).get(
            legislative_session__jurisdiction_id=jid,
            legislative_session__identifier=session,
            id=bill_id,
        )
    except Bill.DoesNotExist:
        return fallback(
            request
        )  # to do: figure out fallback rerouting given url change

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
        if s.person_id:
            s.person = sponsor_people.get(s.person_id)
        elif s.name.startswith("b'") and s.name.endswith("'"):
            s.name = s.name[2:-1]  # byte encoding formatting fix

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
    votes.sort(
        key=lambda v: hacky_motion_text(v), reverse=True
    )  # hacky sorting fix for ct
    votes.sort(key=lambda v: v.start_date)

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
        read_link = sorted_links[0]
    except IndexError:
        read_link = None

    # update last viewed bill action for dashboard read/unread logic
    latest_action = actions[0] if actions else None

    if latest_action:
        # update last viewed bill action if bill is tracked
        is_updated = update_last_viewed_bill_action(request, bill_id, latest_action.id)

        # if there is an update to last viewed bill action, clear cache item that tracks number of unread bills (context_preprocessors.py)
        if is_updated > 0:
            session_key = request.session.session_key
            cache.delete(f"unread_bills_{session_key}")

    # get latest action id and following state for follow button logic
    latest_action_id = latest_action.id if latest_action else None
    is_followed = is_bill_followed(request, bill_id)

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
            "latest_action_id": latest_action_id,
            "is_followed": is_followed,
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


def bill_document(request, document_link_id, document_type):

    if document_type == "bill_text":
        document_link = get_object_or_404(
            BillVersionLink.objects.all().select_related(
                "version__bill",
                "version__bill__legislative_session",
                "version__bill__from_organization",
                "version__bill__legislative_session__jurisdiction",
            ),
            pk=document_link_id,
        )
        document = document_link.version
        document_type_formatted = "Bill Text"
    else:  # related
        document_link = get_object_or_404(
            BillDocumentLink.objects.all().select_related(
                "document__bill",
                "document__bill__legislative_session",
                "document__bill__from_organization",
                "document__bill__legislative_session__jurisdiction",
            ),
            pk=document_link_id,
        )
        document = document_link.document
        document_type_formatted = "Related Document"

    # to do: simplify s3 path logic by storing as key in DB (this also helps keep track of which files have already been downloaded)
    state = jid_to_abbr(document.bill.from_organization.jurisdiction_id)
    session_identifier = document.bill.legislative_session.identifier.replace(" ", "_")

    # get file type from url using same logic as downloader script
    parts = document_link.url.rsplit(".", 1)
    file_type = parts[1].lower() if len(parts) == 2 else ""

    if file_type:
        s3_key = f"{state}/{session_identifier}/{document_type}/{document_link.id}.{file_type}"
    else:
        s3_key = f"{state}/{session_identifier}/{document_type}/{document_link.id}"

    s3 = boto3.client("s3", region_name="us-east-1")
    s3_document_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": "openstates-bill-documents", "Key": s3_key},
        ExpiresIn=3600,  # 1 hour
    )

    return render(
        request,
        "public/views/bill_document.html",
        {
            "state": state,
            "state_nav": "bills",
            "document": document,
            "document_link": document_link,
            "s3_document_url": s3_document_url,
            "document_type_formatted": document_type_formatted,
            "viewer_mode": "pdf",  # image or pdf, temp solution for testing
        },
    )


# to allow pdf render in pdf.js -- for development only
def document_proxy_for_development(request, remote_url):
    if not remote_url:
        return HttpResponse("Missing 'url' parameter", status=400)

    if "://" not in remote_url:
        remote_url = remote_url.replace(":/", "://", 1)

    response = requests.get(remote_url, verify=False)
    return HttpResponse(response.content, content_type="application/pdf")
