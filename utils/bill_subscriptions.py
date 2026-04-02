from django.db.models import Prefetch
from openstates.data.models import Bill, BillAction

# in django session, tracked_bills is a structure like
# {
#     'tracked_bills': {
#         'billid1' : { 'last_viewed_bill_action_id': 'actionid1'}
#         'billid2' : { 'last_viewed_bill_action_id': 'actionid2'}
#         'billid3' : { 'last_viewed_bill_action_id': 'actionid3'}
#     }
# }


def get_bill_subscriptions(request, get_related_fields=True):
    tracked_bills = request.session.get("tracked_bills", {})
    bill_ids = list(tracked_bills.keys())

    # fetch bills and related fields from DB
    if get_related_fields:
        # select related legislative session, jurisdiction, organization; prefetch actions sorted in descending order
        bill_actions = Prefetch(
            "actions",
            BillAction.objects.select_related("organization").order_by(
                "-date", "-order"
            ),
        )
        bills = (
            Bill.objects.filter(id__in=bill_ids)
            .select_related(
                "legislative_session__jurisdiction",
                "from_organization",
            )
            .prefetch_related(bill_actions)
            .order_by("id")
        )
    else:
        # just get bill objects
        bills = Bill.objects.filter(id__in=bill_ids).order_by("id")

    # reattach last viewed bill action id
    for bill in bills:
        bill.last_viewed_bill_action_id = tracked_bills.get(bill.id, {}).get(
            "last_viewed_bill_action_id"
        )

    return bills


def follow_bill(request, bill_id, latest_action_id):
    tracked_bills = request.session.get("tracked_bills", {})
    if bill_id not in tracked_bills:
        tracked_bills[bill_id] = {"last_viewed_bill_action_id": str(latest_action_id)}
    request.session["tracked_bills"] = tracked_bills
    request.session.modified = True


def unfollow_bill(request, bill_id):
    tracked_bills = request.session.get("tracked_bills", {})
    tracked_bills.pop(bill_id, None)
    request.session["tracked_bills"] = tracked_bills
    request.session.modified = True


def is_bill_followed(request, bill_id):
    tracked_bills = request.session.get("tracked_bills", {})
    return bill_id in tracked_bills


def update_last_viewed_bill_action(request, bill_id, latest_bill_action_id):
    """
    checks if bill is in tracked bills and updates last viewed bill action if so
    (do not need to make a separate call to get bill subscriptions)

    returns true if the last viewed bill action was updated and false otherwise,
    including false if the bill id was found but the last viewed bill action remains unchanged
    """
    tracked_bills = request.session.get("tracked_bills", {})
    latest_bill_action_id = str(latest_bill_action_id)

    if (
        bill_id in tracked_bills
        and tracked_bills[bill_id]["last_viewed_bill_action_id"]
        != latest_bill_action_id
    ):  # update last viewed bill action id with latest action
        tracked_bills[bill_id]["last_viewed_bill_action_id"] = latest_bill_action_id
        request.session["tracked_bills"] = tracked_bills
        request.session.modified = True
        return True
    else:
        return False
