"""エージェント配線とDeferred Tool承認フローのテスト（APIキー不要）。"""

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent, run_with_approval

BASE_TOOLS = {"search_glossary", "get_lecture_summary", "make_quiz", "save_learning_log"}


def _parts(result, kind):
    return [p for m in result.all_messages() for p in m.parts if isinstance(p, kind)]


class _SaveCallTestModel(TestModel):
    """実際のTestModelを使い、保存ツールに既知のテスト引数を渡す。"""

    def gen_tool_args(self, tool_def):
        if tool_def.name == "save_learning_log":
            return {"filename": "day3-test", "content": "承認された学習記録\n"}
        return super().gen_tool_args(tool_def)


def _use_temp_learning_log(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", tmp_path / "learning_log")


def test_base_tools_are_registered_and_called():
    model = TestModel()
    with agent.override(model=model):
        result = agent.run_sync("LoRAとは？")

    offered = {t.name for t in model.last_model_request_parameters.function_tools}
    assert BASE_TOOLS <= offered

    called = {p.tool_name for p in _parts(result, ToolCallPart)}
    assert BASE_TOOLS <= called
    # 承認待ちツールには、結果を返す代わりにDeferredToolRequestsが含まれる。
    waiting = len(result.output.approvals) if isinstance(result.output, DeferredToolRequests) else 0
    assert len(_parts(result, ToolReturnPart)) + waiting == len(_parts(result, ToolCallPart))
    assert result.output


def test_glossary_result_reaches_the_model():
    model = TestModel(call_tools=["search_glossary"])
    with agent.override(model=model):
        result = agent.run_sync("RAGとは？")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "search_glossary"


def test_unapproved_save_request_is_deferred_and_creates_no_file(monkeypatch, tmp_path):
    _use_temp_learning_log(monkeypatch, tmp_path)
    model = _SaveCallTestModel(call_tools=["save_learning_log"])

    with agent.override(model=model):
        result = agent.run_sync("学習記録を保存して", model=model)

    assert isinstance(result.output, DeferredToolRequests)
    assert [call.tool_name for call in result.output.approvals] == ["save_learning_log"]
    assert not (tmp_path / "learning_log" / "day3-test.md").exists()


def test_cli_approval_resumes_history_and_saves_file(monkeypatch, tmp_path):
    _use_temp_learning_log(monkeypatch, tmp_path)
    model = _SaveCallTestModel(call_tools=["save_learning_log"])

    result = run_with_approval(
        agent,
        "学習記録を保存して",
        model=model,
        input_fn=lambda _prompt: "yes",
    )

    saved = tmp_path / "learning_log" / "day3-test.md"
    assert saved.read_text(encoding="utf-8") == "承認された学習記録\n"
    assert "保存しました" in str(result.output)
    assert isinstance(result.output, str)


def test_cli_rejection_resumes_without_creating_file(monkeypatch, tmp_path):
    _use_temp_learning_log(monkeypatch, tmp_path)
    model = _SaveCallTestModel(call_tools=["save_learning_log"])

    result = run_with_approval(
        agent,
        "学習記録を保存して",
        model=model,
        input_fn=lambda _prompt: "no",
    )

    assert isinstance(result.output, str)
    assert not (tmp_path / "learning_log" / "day3-test.md").exists()
