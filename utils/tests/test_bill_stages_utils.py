import pytest
from openstates.data.models import Bill, Organization
from testutils.populators import populate_db, populate_unicam
from utils.bill_stages import get_bill_chambers, compute_bill_stages


@pytest.mark.django_db
def setup():
    populate_db()


@pytest.mark.django_db
def test_get_bill_chambers():
    bill = Bill.objects.get(identifier="HB 1")
    actions = list(bill.actions.all().order_by("-date", "-order"))

    first_chamber, second_chamber = get_bill_chambers(bill, actions)
    assert first_chamber == "Alaska House"
    assert second_chamber == "Alaska Senate"


@pytest.mark.django_db
def test_get_bill_chambers_unicameral_state():
    populate_unicam()
    bill = Bill.objects.get(identifier="LB 42")
    actions = list(bill.actions.all().order_by("-date", "-order"))

    first_chamber, second_chamber = get_bill_chambers(bill, actions)
    assert first_chamber == "Legislature"
    assert second_chamber is None


@pytest.mark.django_db
def test_get_bill_chambers_unicameral_special_case():
    bill = Bill.objects.get(identifier="HB 2")
    actions = list(bill.actions.all().order_by("-date", "-order"))

    first_chamber, second_chamber = get_bill_chambers(bill, actions)
    assert first_chamber == "Legislature"
    assert second_chamber is None


@pytest.mark.django_db
def test_compute_bill_stages_introduction_only():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )

    # get only introduction action
    actions = bill.actions.filter(classification__contains=["introduction"]).order_by(
        "-order"
    )

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    assert len(stages) == 4
    assert stages[0]["stage"] == "Introduced"
    assert stages[0]["text"] == f"Introduced in {house.name}"
    assert stages[0]["date"] == "2018-01-01"
    assert stages[1]["text"] is None  # house not reached
    assert stages[2]["text"] is None  # senate not reached
    assert stages[3]["stage"] == "Governor"
    assert stages[3]["text"] is None  # executive not reached
    assert latest_stage["stage"] == "Introduced"


@pytest.mark.django_db
def test_compute_bill_stages_passed_first_chamber():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )

    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    assert len(stages) == 4
    assert stages[0]["stage"] == "Introduced"
    assert stages[0]["text"] == f"Introduced in {house.name}"
    assert stages[1]["stage"] == house.name
    assert stages[1]["text"] == f"Passed {house.name}"
    assert stages[1]["date"] is not None
    assert stages[2]["text"] is None  # senate not reached
    assert stages[3]["text"] is None  # executive not reached
    assert latest_stage["stage"] == house.name


@pytest.mark.django_db
def test_compute_bill_stages_failed_first_chamber():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )

    # add failure action
    bill.actions.create(
        description="Failed in House",
        order=40,
        organization=house,
        date="2018-04-01",
        classification=["failure"],
    )

    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    assert stages[1]["text"] == f"Failed in {house.name}"
    assert latest_stage["stage"] == house.name


@pytest.mark.django_db
def test_compute_bill_stages_passed_second_chamber():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )

    # add senate passage
    bill.actions.create(
        description="Passed Senate",
        order=40,
        organization=senate,
        date="2018-04-01",
        classification=["passage"],
    )

    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    assert stages[1]["text"] == f"Passed {house.name}"
    assert stages[2]["stage"] == senate.name
    assert stages[2]["text"] == f"Passed {senate.name}"
    assert stages[2]["date"] == "2018-04-01"
    assert latest_stage["stage"] == senate.name


@pytest.mark.django_db
def test_compute_bill_stages_executive_signature():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )
    executive = Organization.objects.get(
        jurisdiction__name="Alaska", classification="executive"
    )

    # add senate passage and governor signature
    bill.actions.create(
        description="Passed Senate",
        order=40,
        organization=senate,
        date="2018-04-01",
        classification=["passage"],
    )
    bill.actions.create(
        description="Signed by Governor",
        order=50,
        organization=executive,
        date="2018-05-01",
        classification=["executive-signature"],
    )

    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    assert stages[3]["stage"] == "Governor"
    assert stages[3]["text"] == "Signed by Governor"
    assert stages[3]["date"] == "2018-05-01"
    assert latest_stage["stage"] == "Governor"


@pytest.mark.django_db
def test_compute_bill_stages_executive_veto():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )
    executive = Organization.objects.get(
        jurisdiction__name="Alaska", classification="executive"
    )

    # add senate passage and governor veto
    bill.actions.create(
        description="Passed Senate",
        order=40,
        organization=senate,
        date="2018-04-01",
        classification=["passage"],
    )
    bill.actions.create(
        description="Vetoed",
        order=50,
        organization=executive,
        date="2018-05-01",
        classification=["executive-veto"],
    )

    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    assert stages[3]["text"] == "Vetoed by Governor"
    assert stages[3]["date"] == "2018-05-01"
    assert latest_stage["stage"] == "Governor"


@pytest.mark.django_db
def test_compute_bill_stages_became_law():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )
    executive = Organization.objects.get(
        jurisdiction__name="Alaska", classification="executive"
    )

    # add senate passage and became law
    bill.actions.create(
        description="Passed Senate",
        order=40,
        organization=senate,
        date="2018-04-01",
        classification=["passage"],
    )
    bill.actions.create(
        description="Became Law",
        order=50,
        organization=executive,
        date="2018-05-01",
        classification=["became-law"],
    )

    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    assert stages[3]["text"] == "Became Law"
    assert latest_stage["stage"] == "Governor"


@pytest.mark.django_db
def test_compute_bill_stages_veto_override_passage():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )
    executive = Organization.objects.get(
        jurisdiction__name="Alaska", classification="executive"
    )

    # add full legislative process with veto and override
    bill.actions.create(
        description="Passed Senate",
        order=40,
        organization=senate,
        date="2018-04-01",
        classification=["passage"],
    )
    bill.actions.create(
        description="Vetoed",
        order=50,
        organization=executive,
        date="2018-05-01",
        classification=["executive-veto"],
    )
    bill.actions.create(
        description="Override Passed in House",
        order=60,
        organization=house,
        date="2018-06-01",
        classification=["veto-override-passage"],
    )
    bill.actions.create(
        description="Override Passed in Senate",
        order=70,
        organization=senate,
        date="2018-06-15",
        classification=["veto-override-passage"],
    )

    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    # most recent override action should be reflected
    assert stages[2]["text"] == f"Override Passed {senate.name}"
    assert stages[2]["date"] == "2018-06-15"
    assert latest_stage["stage"] == senate.name


@pytest.mark.django_db
def test_compute_bill_stages_veto_override_failure():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )
    executive = Organization.objects.get(
        jurisdiction__name="Alaska", classification="executive"
    )

    # add veto and failed override
    bill.actions.create(
        description="Passed Senate",
        order=40,
        organization=senate,
        date="2018-04-01",
        classification=["passage"],
    )
    bill.actions.create(
        description="Vetoed",
        order=50,
        organization=executive,
        date="2018-05-01",
        classification=["executive-veto"],
    )
    bill.actions.create(
        description="Override Failed in House",
        order=60,
        organization=house,
        date="2018-06-01",
        classification=["veto-override-failure"],
    )

    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    assert stages[1]["text"] == f"Override Failed {house.name}"
    assert stages[3]["text"] == "Vetoed by Governor"
    assert latest_stage["stage"] == house.name


# unicameral legislature tests -- nebraska
@pytest.mark.django_db
def test_compute_bill_stages_unicameral_introduction():
    populate_unicam()
    bill = Bill.objects.get(identifier="LB 42")  # nebraska bill

    # get only introduction action
    actions = bill.actions.filter(order=10).order_by("-order")

    stages, latest_stage = compute_bill_stages(
        actions, "Legislature", None, "ne"  # no second chamber
    )

    # should only have 3 stages (no second chamber)
    assert len(stages) == 3
    assert stages[0]["stage"] == "Introduced"
    assert stages[0]["text"] == "Introduced in Legislature"
    assert stages[1]["stage"] == "Legislature"
    assert stages[1]["text"] is None
    assert stages[2]["stage"] == "Governor"
    assert stages[2]["text"] is None
    assert latest_stage["stage"] == "Introduced"


@pytest.mark.django_db
def test_compute_bill_stages_unicameral_passed():
    populate_unicam()
    bill = Bill.objects.get(identifier="LB 42")
    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, "Legislature", None, "ne")

    assert len(stages) == 3
    assert stages[1]["stage"] == "Legislature"
    assert stages[1]["text"] == "Passed Legislature"
    assert stages[1]["date"] == "2018-03-01"
    assert latest_stage["stage"] == "Legislature"


@pytest.mark.django_db
def test_compute_bill_stages_unicameral_signed():
    populate_unicam()
    bill = Bill.objects.get(identifier="LB 42")
    executive = Organization.objects.get(
        jurisdiction__name="Nebraska", classification="executive"
    )

    # add governor signature
    bill.actions.create(
        description="Signed by Governor",
        order=40,
        organization=executive,
        date="2018-04-01",
        classification=["executive-signature"],
    )

    actions = bill.actions.all().order_by("-order")

    stages, latest_stage = compute_bill_stages(actions, "Legislature", None, "ne")

    assert stages[2]["stage"] == "Governor"
    assert stages[2]["text"] == "Signed by Governor"
    assert stages[2]["date"] == "2018-04-01"
    assert latest_stage["stage"] == "Governor"


@pytest.mark.django_db
def test_compute_bill_stages_no_actions():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )

    # empty queryset
    actions = bill.actions.none()

    stages, latest_stage = compute_bill_stages(actions, house.name, senate.name, "ak")

    # all stages should be empty
    assert all(stage["text"] is None for stage in stages)
    assert all(stage["date"] is None for stage in stages)
    assert latest_stage is None


@pytest.mark.django_db
def test_compute_bill_stages_action_order():
    bill = Bill.objects.get(identifier="HB 1")
    house = Organization.objects.get(
        jurisdiction__name="Alaska", classification="lower"
    )
    senate = Organization.objects.get(
        jurisdiction__name="Alaska", classification="upper"
    )

    # add multiple passage actions with different dates
    bill.actions.create(
        description="Passed House - First",
        order=40,
        organization=house,
        date="2018-04-01",
        classification=["passage"],
    )
    bill.actions.create(
        description="Passed House - Second",
        order=50,
        organization=house,
        date="2018-05-01",
        classification=["passage"],
    )

    # sort descending by order (most recent first)
    actions = bill.actions.all().order_by("-order")

    stages, _ = compute_bill_stages(actions, house.name, senate.name, "ak")

    # should reflect the most recent action
    assert stages[1]["date"] == "2018-05-01"
