import uuid

from app.models.gap import GapGroup, GapKeyword, GapProposal, ProposalStatus


def test_proposal_status_enum():
    assert ProposalStatus.pending.value == "pending"
    assert ProposalStatus.approved.value == "approved"
    assert ProposalStatus.rejected.value == "rejected"


def test_gap_keyword_fields():
    gk = GapKeyword(
        site_id=uuid.uuid4(),
        competitor_domain="comp.ru",
        phrase="seo продвижение",
        frequency=1000,
        competitor_position=3,
        potential_score=1000.0,
        source="serp",
    )
    assert gk.phrase == "seo продвижение"
    assert gk.source == "serp"


def test_gap_group_fields():
    g = GapGroup(site_id=uuid.uuid4(), name="Коммерческие ключи")
    assert g.name == "Коммерческие ключи"


def test_gap_proposal_fields():
    p = GapProposal(
        site_id=uuid.uuid4(),
        title="Написать текст: SEO",
        target_phrase="seo продвижение",
        frequency=1000,
        potential_score=700.0,
    )
    assert p.title == "Написать текст: SEO"
    assert p.potential_score == 700.0
