"""公式ノートブックからDay2の再現用ソースを作る。GPU学習は実行しない。

生成物のoutputsは空にする。実行済みノートブックを偽装せず、実測の証拠は
lectures/02/results/ のJSONと区別する。学習・評価ロジックは公式と同じ。
"""

import ast
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "fae899a409e2c99feee9d44a3789f936f5fc64ee"

RESULT_CODE = '''result = {
    "config": {k: v for k, v in CONFIG.items() if k not in ("work_dir", "drive_dir")},
    "versions": {m.__name__: m.__version__ for m in [transformers, peft, trl, torch]},
    "method": "LoRA（量子化なし）",
    "before": before_summary, "after": after_summary,
    "regressed": regressed,
    "knowledge": knowledge_rows,
    "executed_training_myself": False,
    "execution_actor": "AI assistant (on behalf of the submitter)",
    "user_reviewed_results": False,
}
(WORK / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "knowledge"}, ensure_ascii=False, indent=2))
'''

EXPORT_CODE = '''# AI-assisted export. Optional 4bit experiment is not run.
import zipfile
from datetime import datetime, timezone
result["executed_training_myself"] = False
result["execution_actor"] = "AI assistant (on behalf of the submitter)"
result["user_reviewed_results"] = False
result["executed_at_utc"] = datetime.now(timezone.utc).isoformat()
result["upstream_commit"] = "fae899a409e2c99feee9d44a3789f936f5fc64ee"
result["training_metrics"] = trainer.state.log_history[-1]
result["loss_history"] = [r for r in trainer.state.log_history if "loss" in r]
result["final_logged_loss"] = next((r["loss"] for r in reversed(trainer.state.log_history) if "loss" in r), None)
result["training_runtime_seconds"] = trainer.state.log_history[-1].get("train_runtime")
result["notes"] = "New run for this task. Earlier private experiments are not included. The submitter has not yet reviewed these results."
(WORK / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
(WORK / "trainer_state.json").write_text(json.dumps(trainer.state.log_history, ensure_ascii=False, indent=2), encoding="utf-8")
(WORK / "gpu.txt").write_text(gpu_info, encoding="utf-8")
ZIP_PATH = f"/content/day2_epochs_{CONFIG['num_train_epochs']}.zip"
with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for name in ["result.json", "eval_before.json", "eval_after.json", "test.jsonl", "gold.json", "trainer_state.json", "gpu.txt"]:
        z.write(WORK / name, arcname=name)
print("AI_EXPORT_READY", ZIP_PATH)
print(json.dumps({"epochs": CONFIG["num_train_epochs"], "before": before_summary, "after": after_summary, "final_logged_loss": result["final_logged_loss"], "training_runtime_seconds": result["training_runtime_seconds"]}, ensure_ascii=False, indent=2))
'''

LINK_CODE = '''import base64
from IPython.display import HTML, display
name = Path(ZIP_PATH).name
display(HTML('<a download="' + name + '" href="data:application/zip;base64,' + base64.b64encode(open(ZIP_PATH, "rb").read()).decode() + '">Save Day2 experiment ZIP</a>'))
'''


def config_literal(source: str) -> dict:
    for statement in ast.parse(source).body:
        if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CONFIG" for t in statement.targets):
            return ast.literal_eval(statement.value)
    raise AssertionError("CONFIG assignment not found")


def main() -> None:
    original = json.loads((ROOT / "notebooks" / "lora_format_tuning.ipynb").read_text(encoding="utf-8"))
    prepared = {}
    for epochs in [20, 10]:
        notebook = copy.deepcopy(original)
        intro = (
            f"# Day2 {epochs}エポック条件：再現用ソース\n\n"
            "このファイルは再現用に整形したソースです。実行済みノートブックの書き出しではありません。"
            "実測結果は `lectures/02/results/` のJSONを参照してください。"
            "元の実験操作はAIアシスタントが実施し、提出者本人の独力実行ではありません。\n\n"
            "20エポック条件を実行・結果保存後、Colabのセッションを再起動して10エポック条件を実行します。"
            "両方とも最初のセルから順番に実行します。任意の4bit実験は含めません。"
            "保存用の補助セルは読みやすく整形していますが、学習・評価ロジックは公式教材と同じです。\n\n---\n\n"
        )
        notebook["cells"][0]["source"] = (intro + "".join(notebook["cells"][0]["source"])).splitlines(keepends=True)
        config = "".join(notebook["cells"][5]["source"])
        config = config.replace('"num_train_epochs": 20,  # 学習データ（14 件）を何周学習するか。1 周 2 ステップなので合計 40 ステップ（T4 で 4〜5 分）', f'"num_train_epochs": {epochs},  # 比較で変更する唯一の設定')
        assert config_literal(config)["num_train_epochs"] == epochs
        notebook["cells"][5]["source"] = config.splitlines(keepends=True)
        notebook["cells"][19]["source"] = RESULT_CODE.splitlines(keepends=True)
        notebook["cells"][20]["source"] = ["## 8. 実行主体・学習指標・実測JSONの保存\n", "\n", "次のセルは任意の4bit比較ではなく、実行主体の記録とZIP生成のための補助セルです。\n"]
        notebook["cells"][21]["source"] = EXPORT_CODE.splitlines(keepends=True)
        notebook["cells"].append({"cell_type": "code", "metadata": {}, "source": LINK_CODE.splitlines(keepends=True), "outputs": [], "execution_count": None})
        for i, cell in enumerate(notebook["cells"]):
            cell["metadata"] = {}
            cell["id"] = f"day2-cell-{i}"
            if cell["cell_type"] == "code":
                cell["outputs"] = []
                cell["execution_count"] = None
                source = "".join(cell["source"])
                python_source = "\n".join("pass" if line.lstrip().startswith("%") else line for line in source.splitlines())
                ast.parse(python_source)
        notebook["metadata"] = {
            "accelerator": "GPU",
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "provenance": {"purpose": "Reproduction source, not an exported executed notebook", "upstream_commit": UPSTREAM_COMMIT, "original_execution_actor": "AI assistant", "submitter_reviewed_results": False},
        }
        prepared[epochs] = notebook
        destination = ROOT / "notebooks" / f"day2_epochs{epochs}_reproduce.ipynb"
        destination.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(destination.relative_to(ROOT))
    configs = {e: config_literal("".join(n["cells"][5]["source"])) for e, n in prepared.items()}
    differences = {k for k in configs[20] if configs[20][k] != configs[10][k]}
    assert differences == {"num_train_epochs"}
    for i in range(len(prepared[20]["cells"])):
        if i not in {0, 5}:
            assert prepared[20]["cells"][i]["source"] == prepared[10]["cells"][i]["source"]
    print("PASS: Python構文・条件差分・未実行ソースであることを確認しました。")


if __name__ == "__main__":
    main()
