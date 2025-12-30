from django.core.cache import cache


# Add unread bills count to "My Bills" link in header if user is logged in
def unread_bills_count(request):
    if not request.user.is_authenticated:
        return {"unread_bills_count": 0}

    # Cache for 15 minutes per user; only fetch from DB if value not cached
    cache_key = f"unread_bills_{request.user.id}"
    count = cache.get(cache_key)

    if count is None:
        # Compute count
        count = 0
        active_subscriptions = request.user.subscriptions.filter(
            bill_id__isnull=False,
            active=True,
        ).select_related("bill")

        for sub in active_subscriptions:

            latest_action = sub.bill.actions.order_by("-date", "-order").first()

            if latest_action:
                if (
                    sub.last_viewed_bill_action_id != latest_action.id
                ):  # Last viewed action is not latest action
                    count += 1
                elif not sub.last_viewed_bill_action_id:  # Never viewed but has actions
                    count += 1

        cache.set(cache_key, count, 900)  # Cache for 15 minutes

    return {"unread_bills_count": count}
