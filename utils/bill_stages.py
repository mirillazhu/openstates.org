from .common import jid_to_abbr
from .orgs import get_chambers_from_abbr


def get_bill_chambers(bill, actions):
    """
    returns first_chamber, second_chamber for bicameral bills, or "Legislature", None for unicameral bills.

    chambers used as parameters for compute_bill_stages.
    """

    # check if bill is unicameral: bill (a) originates from legislature or (b) may originate from house or senate, but all bill actions are from organization with legislature/executive classification
    has_non_leg_exec_action = any(
        action.organization.classification not in ["legislature", "executive"]
        for action in actions
    )
    is_unicameral = (
        bill.from_organization.classification == "legislature"
        or not has_non_leg_exec_action
    )

    if is_unicameral:
        first_chamber = "Legislature"
        second_chamber = None

    else:  # bicameral
        first_chamber = bill.from_organization.name
        # get second chamber name (if exists)
        second_chamber = None
        state = jid_to_abbr(bill.legislative_session.jurisdiction.id)
        chambers = {c.classification: c.name for c in get_chambers_from_abbr(state)}
        if len(chambers) > 1:
            second_chamber = {"upper": chambers["lower"], "lower": chambers["upper"]}[
                bill.from_organization.classification
            ]

    return first_chamber, second_chamber


def _set_stage(stages, stage_index, date, text, current_latest_stage):
    """
    helper function to set stage for compute_bill_stages and keep track of latest stage.

    returns latest stage by bill action order, where stage is as defined in compute_bill_stages.
    """
    if stages[stage_index]["date"] is None:
        stages[stage_index]["date"] = date
        stages[stage_index]["text"] = text
        return (
            current_latest_stage
            if current_latest_stage is not None
            else stages[stage_index]
        )
    return current_latest_stage


def compute_bill_stages(actions, first_chamber, second_chamber, state):
    """
    computes bill stages from bill actions sorted in descending order (most recent action first);
    actions must be sorted in this way for stages to be computed correctly.

    returns stages, latest_stage

    where stages is a structure with four entries which are each like
        stage: Introduced
        text: Introduced in House
        date: 2018-01-01
    or, if empty
        stage: Senate
        text: None
        date: None

    and latest_stage is the latest stage a bill has reached (by bill action order, must be computed concurrently with stages).
    """
    EXECUTIVE_TITLES = {
        "us": "President",
        "dc": "Mayor",
        # default: Governor (for all states and Puerto Rico)
    }

    executive_title = EXECUTIVE_TITLES.get(state, "Governor")

    stages = [
        {"stage": "Introduced", "text": None, "date": None},
        {"stage": first_chamber, "text": None, "date": None},
        {"stage": second_chamber, "text": None, "date": None},
        {"stage": executive_title, "text": None, "date": None},
    ]

    latest_stage = None

    for action in actions:
        if "introduction" in action.classification:
            text = f"Introduced in {first_chamber}"
            latest_stage = _set_stage(stages, 0, action.date, text, latest_stage)

        # for passage and failure, latest action takes precedence
        # exclude override passage/failures, since these are handled below
        elif (
            "passage" in action.classification
            and "veto-override-passage" not in action.classification
        ):
            if (
                action.organization.name == first_chamber
                or first_chamber == "Legislature"  # unicameral
            ):
                text = f"Passed {first_chamber}"
                latest_stage = _set_stage(stages, 1, action.date, text, latest_stage)
            elif action.organization.name == second_chamber:
                text = f"Passed {second_chamber}"
                latest_stage = _set_stage(stages, 2, action.date, text, latest_stage)
        elif (
            "failure" in action.classification
            and "veto-override-failure" not in action.classification
        ):
            if (
                action.organization.name == first_chamber
                or first_chamber == "Legislature"  # unicameral
            ):
                text = f"Failed in {first_chamber}"
                latest_stage = _set_stage(stages, 1, action.date, text, latest_stage)
            elif action.organization.name == second_chamber:
                text = f"Failed in {second_chamber}"
                latest_stage = _set_stage(stages, 2, action.date, text, latest_stage)

        elif "executive-signature" in action.classification:
            text = f"Signed by {executive_title}"
            latest_stage = _set_stage(stages, 3, action.date, text, latest_stage)
        elif "became-law" in action.classification:
            text = "Became Law"
            latest_stage = _set_stage(stages, 3, action.date, text, latest_stage)
        elif "executive-veto" in action.classification:
            text = f"Vetoed by {executive_title}"
            latest_stage = _set_stage(stages, 3, action.date, text, latest_stage)

        # successful override does not necessarily mean bill became law because override needs to pass in both chambers
        elif "veto-override-passage" in action.classification:
            if (
                action.organization.name == first_chamber
                or first_chamber == "Legislature"  # unicameral
            ):
                text = f"Override Passed {first_chamber}"
                latest_stage = _set_stage(stages, 1, action.date, text, latest_stage)
            elif action.organization.name == second_chamber:
                text = f"Override Passed {second_chamber}"
                latest_stage = _set_stage(stages, 2, action.date, text, latest_stage)
        elif "veto-override-failure" in action.classification:
            if (
                action.organization.name == first_chamber
                or first_chamber == "Legislature"  # unicameral
            ):
                text = f"Override Failed {first_chamber}"
                latest_stage = _set_stage(stages, 1, action.date, text, latest_stage)
            elif action.organization.name == second_chamber:
                text = f"Override Failed {second_chamber}"
                latest_stage = _set_stage(stages, 2, action.date, text, latest_stage)

    # if we're unicameral, remove second stage and make first stage name simpler
    if second_chamber is None:
        stages.pop(2)
        stages[1]["stage"] = "Legislature"

    return stages, latest_stage
