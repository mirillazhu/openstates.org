from django.core.cache import cache
from utils.bill_subscriptions import get_bill_subscriptions


# add unread bills count to bill dashboard link in header
def unread_bills_count(request):

    # cache for 30 minutes per user; only fetch from DB if value not cached
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key

    cache_key = f"unread_bills_{session_key}"
    count = cache.get(cache_key)

    if count is None:
        # compute count
        count = 0
        bill_subscriptions = get_bill_subscriptions(request, get_related_fields=False)

        for bill in bill_subscriptions:
            latest_action = bill.actions.order_by("-date", "-order").first()

            if latest_action:
                if bill.last_viewed_bill_action_id != str(
                    latest_action.id
                ):  # last viewed action is not latest action
                    count += 1
                elif (
                    not bill.last_viewed_bill_action_id
                ):  # never viewed but has actions
                    count += 1

        cache.set(cache_key, count, 1800)  # cache for 30 minutes

    return {"unread_bills_count": count}
