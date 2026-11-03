"""APIを呼ばずに、保存前の確認と拒否・承認の動きを試すデモ。

実モデルのツール選択や回答品質を検証するものではありません。
実行例: uv run --frozen python -m scripts.demo_day3_approval --name day3-demo --trace
"""

import argparse

from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent, print_trace, run_with_approval


class ApprovalDemoModel(TestModel):
    """既知の引数で保存を要求する、API不要のテスト用モデル。"""

    def __init__(self, filename: str):
        super().__init__(call_tools=["save_learning_log"])
        self.demo_filename = filename

    def gen_tool_args(self, tool_def):
        if tool_def.name == "save_learning_log":
            return {
                "filename": self.demo_filename,
                "content": "保存承認フローの動作確認用サンプルです。本人の学習実績を表す記録ではありません。\n",
            }
        return super().gen_tool_args(tool_def)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="day3-demo", help="拡張子なしの保存名（既存ファイルは上書きしません）")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    print("[demo] APIを呼ばないTestModelです。承認した場合のファイル保存は実際に行います。")
    print("[demo] y / yes / はい だけが承認です。空入力やその他の入力は拒否です。")
    model = ApprovalDemoModel(args.name)
    result = run_with_approval(agent, "動作確認用サンプルを保存して", model=model)
    print(result.output)
    if args.trace:
        print_trace(result)
        print("[demo] このrequestsはTestModelの往復数であり、実API呼び出し回数ではありません。")
    destination = tools.LEARNING_LOG_DIR / f"{args.name}.md"
    print(f"[demo] 保存先: {destination.relative_to(tools.PROJECT_DIR)}")
    print(f"[demo] ファイルの存在: {destination.exists()}")


if __name__ == "__main__":
    main()
