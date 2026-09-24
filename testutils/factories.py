import random
import uuid
from openstates.data.models import (
    Bill,
    Division,
    Jurisdiction,
    LegislativeSession,
    Organization,
    Person,
    VoteEvent,
)


def make_specific_bill(
    session,
    chamber,
    *,
    sponsors=0,
    actions=0,
    votes=0,
    versions=0,
    documents=0,
    sources=0,
    subjects=None,
    identifier=None,
):
    chamber = Organization.objects.get(classification=chamber)
    session = LegislativeSession.objects.get(identifier=session)
    b = Bill.objects.create(
        identifier=identifier or ("Bill " + str(random.randint(1000, 9000))),
        title="Bill Title",
        legislative_session=session,
        from_organization=chamber,
        subject=subjects or [],
    )
    for n in range(sponsors):
        b.sponsorships.create(name="Someone")
    for n in range(actions):
        b.actions.create(
            description="Something", order=n, organization=chamber, date="2020-06-01"
        )
    for n in range(votes):
        b.votes.create(
            identifier="A Vote Occurred",
            organization=chamber,
            legislative_session=session,
        )
    for n in range(versions):
        b.versions.create(note="Version")
    for n in range(documents):
        b.documents.create(note="Document")
    for n in range(sources):
        b.sources.create(url="http://example.com")
    return b


def make_random_bill(name):
    state = Jurisdiction.objects.get(name=name)
    session = random.choice(state.legislative_sessions.all())
    org = state.organizations.get(classification=random.choice(("upper", "lower")))
    b = Bill.objects.create(
        id="ocd-bill/" + str(uuid.uuid4()),
        title="Bill Title",
        identifier=(
            random.choice(("HB", "SB", "HR", "SR")) + str(random.randint(1000, 3000))
        ),
        legislative_session=session,
        from_organization=org,
        classification=[random.choice(["bill", "resolution"])],
        subject=[random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(10)],
    )
    b.actions.create(
        description="Introduced", order=10, organization=org, date="2018-01-01"
    )

    for n in range(random.randint(1, 2)):
        ve = VoteEvent.objects.create(
            bill=b,
            legislative_session=session,
            motion_text="Motion Text",
            organization=org,
            result=random.choice(("failed", "passed")),
        )
        ve.counts.create(option="yes", value=random.randint(0, 10))
        ve.counts.create(option="no", value=random.randint(0, 10))
        for m in range(random.randint(1, 5)):
            ve.votes.create(option=random.choice(("yes", "no")), voter_name="Voter")
    return b


def make_person(name, state, chamber, district, party, person_links=None):
    org = Organization.objects.get(jurisdiction__name=state, classification=chamber)
    # not currently using memberships table for party
    # party, _ = Organization.objects.get_or_create(classification="party", name=party)
    jurisdiction = Jurisdiction.objects.get(name=state)
    chamber_letter = chamber[0]
    if state == "Alaska":
        state = "ak"
    elif state == "Wyoming":
        state = "wy"
    elif state == "Nebraska":
        state = "ne"
        chamber_letter = "u"
    div, _ = Division.objects.get_or_create(
        id="ocd-division/country:us/state:{}/sld{}:{}".format(
            state, chamber_letter, district.lower()
        ),
        name="Division " + district,
    )
    post = org.posts.create(
        label=district,
        division=div,
        role="Representative" if chamber == "lower" else "Senator",
    )
    try:
        district = int(district)
    except ValueError:
        pass
    p = Person.objects.create(
        name=name,
        primary_party=party,
        current_jurisdiction=jurisdiction,
        current_role={
            "org_classification": chamber,
            "district": district,
            "division_id": div.id,
            "title": post.role,
        },
    )
    p.memberships.create(post=post, organization=org)
    # not currently using memberships table for party
    # p.memberships.create(organization=party)
    if person_links:
        for link in person_links:
            p.links.create(url=link["url"], note=link.get("note", ""))
    return p


def make_vote(bill, *, yes_count=0, no_count=0, yes_votes=None, no_votes=None):
    vote = bill.votes.create(
        identifier="test vote",
        organization=bill.from_organization,
        legislative_session=bill.legislative_session,
    )
    vote.counts.create(option="yes", value=yes_count)
    vote.counts.create(option="no", value=no_count)
    for name in yes_votes or []:
        vote.votes.create(option="yes", voter_name=name)
    for name in no_votes or []:
        vote.votes.create(option="no", voter_name=name)
