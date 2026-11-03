# 第3回 解答（レビュー用下書き）

> コードの実装、テスト、以下の動作確認はAIアシスタントが実施しました。提出者本人によるレビュー・実行は未確認です。実モデルのAPIを使った結果と、API不要のTestModelによる確認を区別しています。

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：未比較です。実モデルによる質問を実行していません。
- `--trace` で見えたツール呼び出し：実モデルのtraceは未実行です。`--list-tools` では `search_glossary`、`get_lecture_summary`、`make_quiz`、`save_learning_log` の4ツールの登録を確認しました。
- 1つの質問でのLLM呼び出し回数（`requests`）：実APIは未計測です。下記デモのTestModelの値を、実APIの呼び出し回数としては扱いません。
- 追加したツールとdocstring：`make_quiz(lecture: int) -> str` を追加しました。指定回の用語集から1語を選び、用語の意味を尋ねる問題と定義をJSON文字列で返します。該当回に用語がない場合は、問題を作れない旨を返します。docstringには、確認問題を頼まれたときに使うことを記述しました。

## 宿題

### 取り組んだレベル：実装

`save_learning_log(filename, content)` を追加し、`requires_approval=True` で登録しました。出力型に `DeferredToolRequests` を含め、CLIで承認／拒否を受けてから `DeferredToolResults` と `message_history=result.all_messages()` を渡し、処理を再開します。

ファイル名を英数字・ハイフン・アンダースコアに制限し、空本文と保存先以外への書き込みを拒否します。`learning_log/` の下に排他的に新規作成するため、既存ファイルは上書きしません。このフォルダは `.gitignore` で除外しています。

### テストで確認できたこと

`uv run --frozen pytest -q` は **20 passed** でした。未承認時の保留、承認後の履歴付き再開と保存、拒否後の未保存をTestModelで確認しています。クイズ生成、用語なし応答、空本文、パストラバーサル、上書き拒否も検証しました。[テスト・ツール一覧の実行記録](../../verification/day3-checks.txt) を添付しています。

さらに、[API不要の対話デモ](../../scripts/demo_day3_approval.py) を端末で実行しました。入力を `n` としたケースでは `learning_log/ai-demo-reject.md` が存在せず、`y` としたケースでは `learning_log/ai-demo-approve.md` が作成されることを確認しました。これはAIアシスタントによる動作確認であり、提出者本人が行った承認操作ではありません。保存本文も検証用サンプルです。[拒否・承認のtrace](../../verification/day3-approval-demo.txt) に記録しています。

```bash
uv run --frozen python -m scripts.demo_day3_approval --name my-day3-check --trace
```

このデモはAPIを呼ばないTestModelを使います。実モデルが適切に保存ツールを選ぶか、回答が正確か、という検証を代替するものではありません。

### 残る確認事項

実モデルを使った `--trace`、素のLLMとの同一質問での比較、実APIの呼び出し回数は未確認です。ユーザー本人によるコード・結果のレビューも未確認です。

## 本人から共有された感想

> AIが楽しかった

本人の具体的な実験経験や理解について、これ以外の主張は加えていません。
