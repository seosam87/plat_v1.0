"""Tests for cannibalization resolver: suggestion, action plans."""
from app.services.cannibalization_service import generate_action_plan, suggest_resolution_type


def test_suggest_merge_for_same_prefix():
    urls = ["https://e.com/seo/audit/", "https://e.com/seo/proverka/"]
    assert suggest_resolution_type(urls, "seo аудит") == "merge_content"


def test_suggest_canonical_default():
    urls = ["https://e.com/page-a/", "https://other.com/page-b/"]
    assert suggest_resolution_type(urls, "keyword") == "set_canonical"


def test_suggest_split_single_url():
    assert suggest_resolution_type(["https://e.com/only/"], "kw") == "split_keywords"


def test_action_plan_merge():
    plan = generate_action_plan("merge_content", "seo", ["https://a.com/", "https://b.com/"], "https://a.com/")
    assert "Объединить" in plan
    assert "https://a.com/" in plan
    assert "301" in plan


def test_action_plan_canonical():
    plan = generate_action_plan("set_canonical", "seo", ["https://a.com/", "https://b.com/"], "https://a.com/")
    assert "canonical" in plan
    assert "https://a.com/" in plan


def test_action_plan_redirect():
    plan = generate_action_plan("redirect_301", "seo", ["https://a.com/", "https://b.com/"], "https://a.com/")
    assert "301" in plan


def test_action_plan_split():
    plan = generate_action_plan("split_keywords", "seo", ["https://a.com/", "https://b.com/"], "https://a.com/")
    assert "Разнести" in plan
    assert "seo" in plan
