from django.contrib.postgres.search import SearchVector
from openstates.data.models import (
    Division,
    Jurisdiction,
    Organization,
    Bill,
    VoteEvent,
    SearchableBill,
)
from openstates.importers.computed_fields import update_bill_fields
from .factories import make_person, make_random_bill


def populate_db():
    for abbr, state in (("ak", "Alaska"), ("wy", "Wyoming")):
        d = Division.objects.create(
            id="ocd-division/country:us/state:" + abbr, name=state
        )
        j = Jurisdiction.objects.create(
            id="ocd-jurisdiction/country:us/state:" + abbr + "/government",
            name=state,
            division=d,
        )
        j.legislative_sessions.create(
            identifier="2017", name="2017", start_date="2017-01-01"
        )
        j.legislative_sessions.create(
            identifier="2018", name="2018", start_date="2018-01-01"
        )

        leg = Organization.objects.create(
            jurisdiction=j, classification="legislature", name=state + " Legislature"
        )
        Organization.objects.create(
            jurisdiction=j, parent=leg, classification="lower", name=state + " House"
        )
        Organization.objects.create(
            jurisdiction=j, parent=leg, classification="upper", name=state + " Senate"
        )
        Organization.objects.create(
            jurisdiction=j,
            parent=leg,
            classification="executive",
            name="Office of the Governor",
        )

    alaska = Jurisdiction.objects.get(name="Alaska")
    legislature = alaska.organizations.get(classification="legislature")
    house = alaska.organizations.get(classification="lower")

    # AK House
    amanda_links = [
        {"url": "https://amandaadamsforstaterep.com", "note": "campaign website"},
        {"url": "https://linkedin.com/adams", "note": "linkedin page"},
        {"url": "https://alaskalegislature.gov/amanda-adams/bio", "note": ""},
    ]
    amanda = make_person(
        "Amanda Adams", "Alaska", "lower", "1", "Republican", amanda_links
    )
    birch = make_person("Bob Birch", "Alaska", "lower", "2", "Republican")
    carrie = make_person("Carrie Carr", "Alaska", "lower", "3", "Democratic")
    don = make_person("Don Dingle", "Alaska", "lower", "4", "Republican")
    # AK Senate
    ellen = make_person("Ellen Evil", "Alaska", "upper", "A", "Independent")
    make_person("Frank Fur", "Alaska", "upper", "B", "Democratic")
    # Ellen used to be a house member
    post = house.posts.create(label="5", role="Representative")
    ellen.memberships.create(post=post, organization=house, end_date="2017-01-01")

    # retired house member
    rhonda = make_person("Rhonda Retired", "Alaska", "upper", "B", "Democratic")
    for m in rhonda.memberships.all():
        m.end_date = "2017-01-01"
        m.save()
    rhonda.current_role = None
    rhonda.save()

    # WY House (multi-member districts)
    make_person("Greta Gonzalez", "Wyoming", "lower", "1", "Democratic")
    make_person("Hank Horn", "Wyoming", "lower", "1", "Republican")

    session = alaska.legislative_sessions.get(identifier="2018")
    b1 = Bill.objects.create(
        id="ocd-bill/1",
        title="Moose Freedom Act",
        identifier="HB 1",
        legislative_session=session,
        from_organization=house,
        classification=["bill", "constitutional amendment"],
        subject=["nature", "moose not meese"],
    )
    b1.abstracts.create(abstract="Grants all moose equal rights under the law.")
    b1.abstracts.create(abstract="Ensure moose freedom.")
    b1.other_titles.create(title="Moosemendment")
    b1.other_titles.create(title="Moose & Reindeer Freedom Act")
    b1.other_titles.create(title="M.O.O.S.E.")
    b1.other_identifiers.create(identifier="HCA 1")
    b1.other_identifiers.create(identifier="SB 1")
    a = b1.actions.create(
        description="Introduced",
        order=10,
        organization=house,
        date="2018-01-01",
        classification=["introduction"],
    )
    a.related_entities.create(name="Amanda Adams", entity_type="person", person=amanda)
    b1.actions.create(
        description="Amended", order=20, organization=house, date="2018-02-01"
    )
    a = b1.actions.create(
        description="Passed House",
        order=30,
        organization=house,
        date="2018-03-01",
        classification=["passage"],
    )
    a.related_entities.create(
        name="House", entity_type="organization", organization=house
    )

    b1.sponsorships.create(primary=True, classification="sponsor", name="Adam One")
    b1.sponsorships.create(
        primary=False, classification="cosponsor", name="Beth Two", person=amanda
    )

    d = b1.documents.create(note="Fiscal Note")
    d.links.create(url="https://example.com/fn")
    d = b1.documents.create(note="Legal Justification")
    d.links.create(url="https://example.com/lj")
    d = b1.versions.create(note="First Draft", date="2017-01-01")
    dlink = d.links.create(url="https://example.com/1.txt", media_type="text/plain")
    d.links.create(url="https://example.com/1.pdf", media_type="application/pdf")
    d = b1.versions.create(note="Final Draft", date="2017-06-01")
    d.links.create(url="https://example.com/f.txt", media_type="text/plain")
    d.links.create(url="https://example.com/f.pdf", media_type="application/pdf")
    b1.sources.create(url="https://example.com/s1")
    b1.sources.create(url="https://example.com/s2")
    b1.sources.create(url="https://example.com/s3")

    SearchableBill.objects.create(
        bill=b1,
        version_link=dlink,
        all_titles=b1.title,
        raw_text="shove some text in here and include a weird word like gorgonzola",
        is_error=False,
        search_vector="",
    )
    SearchableBill.objects.update(
        search_vector=(
            SearchVector("all_titles", weight="A", config="english")
            + SearchVector("raw_text", weight="B", config="english")
        )
    )

    ve = VoteEvent.objects.create(
        bill=b1,
        legislative_session=session,
        motion_text="Vote on House Passage",
        organization=house,
        result="failed",
    )
    ve.counts.create(option="yes", value=1)
    ve.counts.create(option="no", value=4)
    ve.votes.create(option="yes", voter_name="Amanda Adams", voter=amanda)
    ve.votes.create(option="no", voter_name="Birch", voter=birch)
    ve.votes.create(option="no", voter_name="Carr", voter=carrie)
    ve.votes.create(option="no", voter_name="Dingle", voter=don)
    ve.votes.create(option="no", voter_name="Speaker")

    rb = Bill.objects.create(
        id="ocd-bill/3",
        title="Alces alces Freedom Act",
        identifier="SB 9",
        legislative_session=session,
        from_organization=alaska.organizations.get(classification="upper"),
        classification=["bill", "constitutional amendment"],
        subject=["nature"],
    )
    b1.related_bills.create(
        related_bill=rb,
        identifier="SB 9",
        legislative_session="2018",
        relation_type="companion",
    )
    rb.sponsorships.create(
        primary=False, classification="cosponsor", name="Beth Two", person=amanda
    )

    b2 = Bill.objects.create(
        id="ocd-bill/2",
        title="Aurora Borealis Act",
        identifier="HB 2",
        legislative_session=session,
        from_organization=house,
        classification=["bill"],
        subject=["nature"],
    )
    a = b2.actions.create(
        description="Introduced", order=10, organization=legislature, date="2018-01-01"
    )
    b2.actions.create(
        description="Amended", order=20, organization=legislature, date="2018-02-01"
    )
    a = b2.actions.create(
        description="Passed Legislature",
        order=30,
        organization=legislature,
        date="2018-03-01",
        classification=["passage"],
    )
    a.related_entities.create(
        name="Legislature", entity_type="organization", organization=legislature
    )

    for x in range(10):
        make_random_bill("Alaska")
    for x in range(14):
        make_random_bill("Wyoming")

    # populate bill computed data
    for bill in Bill.objects.all().filter(
        legislative_session__jurisdiction__name__in=["Alaska", "Wyoming"]
    ):
        update_bill_fields(bill)


def populate_unicam():
    d = Division.objects.create(id="ocd-division/country:us/state:ne", name="Nebraska")
    j = Jurisdiction.objects.create(
        id="ocd-jurisdiction/country:us/state:ne/government",
        name="Nebraska",
        division=d,
    )
    j.legislative_sessions.create(
        identifier="2017", name="2017", start_date="2017-01-01"
    )
    j.legislative_sessions.create(
        identifier="2018", name="2018", start_date="2018-01-01"
    )

    leg = Organization.objects.create(
        jurisdiction=j, classification="legislature", name="Nebraska Legislature"
    )
    Organization.objects.create(
        jurisdiction=j,
        parent=leg,
        classification="executive",
        name="Office of the Governor",
    )

    make_person("Quincy Quip", "Nebraska", "legislature", "1", "Nonpartisan")
    make_person("Wendy Wind", "Nebraska", "legislature", "2", "Nonpartisan")

    nebraska = Jurisdiction.objects.get(name="Nebraska")
    legislature = nebraska.organizations.get(classification="legislature")
    session = nebraska.legislative_sessions.get(identifier="2018")

    b1 = Bill.objects.create(
        id="ocd-bill/42",
        title="Rainbow Cows Act",
        identifier="LB 42",
        legislative_session=session,
        from_organization=legislature,
        classification=["bill"],
        subject=["farms"],
    )
    a = b1.actions.create(
        description="Introduced",
        order=10,
        organization=legislature,
        date="2018-01-01",
        classification=["introduction"],
    )
    b1.actions.create(
        description="Amended", order=20, organization=legislature, date="2018-02-01"
    )
    a = b1.actions.create(
        description="Passed Legislature",
        order=30,
        organization=legislature,
        date="2018-03-01",
        classification=["passage"],
    )
    a.related_entities.create(
        name="Nebraska Legislature",
        entity_type="organization",
        organization=legislature,
    )
