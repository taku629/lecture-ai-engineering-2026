"""Day2の実測結果を検算し、比較表を生成する。モデル/APIは呼ばない。"""

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_evaluation(path: Path, expected: dict) -> dict:
    evaluation = load_json(path)
    rows = evaluation["rows"]
    assert len(rows) == expected["n"] == evaluation["summary"]["n"]
    counts = {}
    for metric, flag in [("format_rate", "format_ok"), ("content_rate", "content_ok"), ("both_rate", "both_ok")]:
        assert all(type(row[flag]) is bool for row in rows)
        counts[flag] = sum(row[flag] for row in rows)
        measured = counts[flag] / len(rows)
        assert math.isclose(measured, expected[metric], abs_tol=1e-12)
        assert math.isclose(measured, evaluation["summary"][metric], abs_tol=1e-12)
    return {"counts": counts, "rows": rows}


def compare(results_dir: Path) -> dict:
    runs = {}
    for epochs in [20, 10]:
        folder = results_dir / f"epochs{epochs}"
        result = load_json(folder / "result.json")
        assert result["config"]["num_train_epochs"] == epochs
        assert result["executed_training_myself"] is False
        assert result["execution_actor"].startswith("AI assistant")
        assert result["user_reviewed_results"] is False
        before = check_evaluation(folder / "eval_before.json", result["before"])
        after = check_evaluation(folder / "eval_after.json", result["after"])
        assert math.isfinite(result["final_logged_loss"])
        assert result["training_runtime_seconds"] > 0
        runs[epochs] = {"result": result, "before": before, "after": after}

    base, changed = runs[20], runs[10]
    config20, config10 = base["result"]["config"], changed["result"]["config"]
    differences = {key: [config20.get(key), config10.get(key)] for key in config20.keys() | config10.keys() if config20.get(key) != config10.get(key)}
    assert differences == {"num_train_epochs": [20, 10]}, differences
    assert base["result"]["versions"] == changed["result"]["versions"]
    hashes = {}
    for name in ["test.jsonl", "gold.json"]:
        a = sha256(results_dir / "epochs20" / name)
        b = sha256(results_dir / "epochs10" / name)
        assert a == b, f"{name} differs between conditions"
        hashes[name] = a

    before20, before10 = base["before"]["rows"], changed["before"]["rows"]
    assert [r["question"] for r in before20] == [r["question"] for r in before10]
    output = {
        "source": "Official AIE2026 synthetic FAQ exercise; actual AI-assisted Colab runs",
        "execution_actor": "AI assistant (on behalf of the submitter)",
        "user_reviewed_results": False,
        "config_differences": differences,
        "dataset_sha256": hashes,
        "before_predictions_identical": [r["raw"] for r in before20] == [r["raw"] for r in before10],
        "conditions": {},
    }
    for epochs, run in runs.items():
        result = run["result"]
        output["conditions"][str(epochs)] = {
            "n": result["after"]["n"],
            "before": result["before"],
            "after": result["after"],
            "before_counts": run["before"]["counts"],
            "after_counts": run["after"]["counts"],
            "final_logged_loss": result["final_logged_loss"],
            "mean_training_loss": result["training_metrics"]["train_loss"],
            "training_runtime_seconds": result["training_runtime_seconds"],
            "training_steps": result["training_metrics"]["step"],
            "remaining_failures": [row for row in run["after"]["rows"] if not row["both_ok"]],
            "knowledge": result["knowledge"],
        }
    t20 = base["result"]["training_runtime_seconds"]
    t10 = changed["result"]["training_runtime_seconds"]
    output["training_time_reduction_percent"] = (1 - t10 / t20) * 100
    return output


def markdown(comparison: dict) -> str:
    lines = [
        "# Day2 実測結果の比較",
        "",
        "実行者はAIアシスタントです。提出者本人の独力実行を表すものではなく、本人レビューは未確認です。",
        "",
        "| 条件 | 学習前 形式 | 学習前 内容 | 学習後 形式 | 学習後 内容 | 最後に記録された損失 | 学習時間（秒） | ステップ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for epochs in [20, 10]:
        run = comparison["conditions"][str(epochs)]
        before, after = run["before"], run["after"]
        lines.append(
            f"| {epochs}エポック | {before['format_rate']:.2%} | {before['content_rate']:.2%} | "
            f"{after['format_rate']:.2%} | {after['content_rate']:.2%} | "
            f"{run['final_logged_loss']:.6f} | {run['training_runtime_seconds']:.2f} | {run['training_steps']} |"
        )
    lines += [
        "",
        "形式・内容の評価対象は各21問です。最終損失は最後のログ区間のlossであり、全学習の平均train_lossとは別の値です。学習時間はtrainerのtrain_runtimeで、導入・モデル取得・推論時間は含みません。",
        "",
        f"10エポック条件の学習時間短縮率は {comparison['training_time_reduction_percent']:.2f}% でした。単一GPU・単一seedの小規模な架空FAQ実験であり、一般の回答品質や再現時の所要時間を保証しません。",
        "",
        "設定差分はnum_train_epochsのみ、test.jsonlとgold.jsonのSHA-256は条件間で一致しています。",
        f"学習前の生の生成結果が条件間で完全一致: {comparison['before_predictions_identical']}",
        "",
        "## 学習後に残った失敗",
    ]
    for epochs in [20, 10]:
        run = comparison["conditions"][str(epochs)]
        lines += ["", f"### {epochs}エポック"]
        for row in run["remaining_failures"]:
            lines += ["", f"- 質問: {row['question']}", f"  - 出力: `{row['raw']}`", f"  - 正解のneeds_review: `{str(row['gold_needs_review']).lower()}`、形式合格: `{row['format_ok']}`、内容合格: `{row['content_ok']}`"]
        if not run["remaining_failures"]:
            lines.append("この21問では失敗はありませんでした。未知の質問での安全性を保証する意味ではありません。")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "lectures" / "02" / "results")
    args = parser.parse_args()
    comparison = compare(args.results_dir)
    (args.results_dir / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = markdown(comparison)
    (args.results_dir / "comparison.md").write_text(report, encoding="utf-8")
    print(report)
    print("PASS: 設定差分・データ同一性・評価率の再計算・実行主体を確認しました。")


if __name__ == "__main__":
    main()
