from public.templatetags.custom_tags import (
    state_name,
    titlecase_caps,
    titlecase_votes,
)


def test_state_name():
    assert state_name("ct") == "Connecticut"
    assert state_name("CT") == "Connecticut"
    assert state_name("DC") == "District of Columbia"
    assert state_name("US") == "Federal"
    assert state_name("rainbow cow") == ""
    assert state_name("") == ""


def test_titlecase_caps():
    assert titlecase_caps("This is a Bill Title") == "This is a Bill Title"
    assert titlecase_caps("THIS IS A BILL TITLE") == "This Is A Bill Title"
    assert titlecase_caps("THIS IS A BILL'S TITLE") == "This Is A Bill's Title"
    assert titlecase_caps("THIS IS A BILL’S TITLE") == "This Is A Bill's Title"


def test_titlecase_votes():
    assert titlecase_votes("This is a vote description") == "This Is A Vote Description"
    assert titlecase_votes("THIS IS A VOTE DESCRIPTION") == "This Is A Vote Description"
    assert (
        titlecase_votes("THIS IS A VOTE'S DESCRIPTION")
        == "This Is A Vote's Description"
    )
    assert (
        titlecase_votes("THIS IS A VOTE’S DESCRIPTION")
        == "This Is A Vote's Description"
    )
    assert (
        titlecase_votes("hb123 passed on the 3RD reading")
        == "HB123 Passed On The 3rd Reading"
    )
    assert (
        titlecase_votes("hb 123 passed on the 3RD reading")
        == "HB 123 Passed On The 3rd Reading"
    )
    assert (
        titlecase_votes("ab123 passed on the 3RD reading")
        == "AB123 Passed On The 3rd Reading"
    )
    assert (
        titlecase_votes("ab 123 passed on the 3RD reading")
        == "AB 123 Passed On The 3rd Reading"
    )
