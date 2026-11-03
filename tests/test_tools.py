"""ツールのテスト（LLMもAPIキーも使わない）。"""

import json

from app import tools


def test_glossary_ids_are_unique_and_related_links_exist():
    terms = tools.load_glossary()
    ids = [t["id"] for t in terms]
    assert len(ids) == len(set(ids))
    for t in terms:
        for r in t["related"]:
            assert r in ids, f"{t['id']} の related に存在しない id: {r}"


def test_search_finds_term_by_name_and_alias():
    for query in ["LoRA", "lora", "Low-Rank Adaptation"]:
        hits = json.loads(tools.search_glossary(query))
        assert hits[0]["term"] == "LoRA", query


def test_search_finds_course_specific_term():
    hits = json.loads(tools.search_glossary("lecNN-start"))
    assert hits[0]["term"] == "lecNN-start タグ"


def test_search_limits_number_of_results():
    hits = json.loads(tools.search_glossary("エージェント"))
    assert 1 <= len(hits) <= tools.MAX_RESULTS


def test_search_reports_not_found():
    assert "見つかりませんでした" in tools.search_glossary("存在しない用語xyz")


def test_lecture_summary():
    assert "エージェント" in tools.get_lecture_summary(3)
    assert "まだありません" in tools.get_lecture_summary(99)


def test_make_quiz_returns_question_and_definition(monkeypatch):
    term = {"term": "test term", "lecture": 2, "definition": "test definition"}
    monkeypatch.setattr(tools, "load_glossary", lambda: [term])
    monkeypatch.setattr(tools.random, "choice", lambda terms: terms[0])

    result = json.loads(tools.make_quiz(2))

    assert result == {"question": "「test term」の意味は？", "answer": "test definition"}


def test_make_quiz_reports_missing_lecture_terms(monkeypatch):
    monkeypatch.setattr(tools, "load_glossary", lambda: [])
    assert "用語がない" in tools.make_quiz(0)


def _set_log_dir(monkeypatch, root):
    monkeypatch.setattr(tools, "PROJECT_DIR", root)
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", root / "learning_log")


def test_save_learning_log_writes_exact_content_to_learning_log(monkeypatch, tmp_path):
    _set_log_dir(monkeypatch, tmp_path)
    content = "# 学習記録\nAIが楽しかった。\n"

    result = tools.save_learning_log("day3", content)

    assert "learning_log/day3.md" in result
    assert (tmp_path / "learning_log" / "day3.md").read_text(encoding="utf-8") == content


def test_save_learning_log_rejects_empty_content_without_creating_file(monkeypatch, tmp_path):
    _set_log_dir(monkeypatch, tmp_path)

    result = tools.save_learning_log("empty", " \n\t")

    assert "本文が空" in result
    assert not (tmp_path / "learning_log").exists()


def test_save_learning_log_rejects_path_traversal(monkeypatch, tmp_path):
    _set_log_dir(monkeypatch, tmp_path)

    result = tools.save_learning_log("../outside", "content")

    assert "ファイル名" in result
    assert not (tmp_path / "learning_log").exists()
    assert not (tmp_path / "outside.md").exists()


def test_save_learning_log_does_not_overwrite(monkeypatch, tmp_path):
    _set_log_dir(monkeypatch, tmp_path)
    destination = tmp_path / "learning_log" / "existing.md"
    destination.parent.mkdir()
    destination.write_text("original", encoding="utf-8")

    result = tools.save_learning_log("existing", "replacement")

    assert "上書きしません" in result
    assert destination.read_text(encoding="utf-8") == "original"


def test_default_question_of_lecture1_is_answerable_from_glossary():
    """第1回の既定の質問（app.ask）は、第3回のエージェントが用語集で正しく答えられること。"""
    from app.ask import DEFAULT_QUESTION

    assert "3レベル" in DEFAULT_QUESTION
    hits = json.loads(tools.search_glossary("3レベル"))
    assert hits[0]["term"] == "宿題の3レベル"
