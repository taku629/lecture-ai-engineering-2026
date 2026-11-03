"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import os
import random
import re
from functools import cache
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
LEARNING_LOG_DIR = PROJECT_DIR / "learning_log"
MAX_RESULTS = 3


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def make_quiz(lecture: int) -> str:
    """指定回の用語集から1語を選び、学習内容の確認問題と答えを作る。

    講座の特定回について確認問題を1問出すよう頼まれたときに使う。
    """
    terms = [entry for entry in load_glossary() if entry.get("lecture") == lecture]
    if not terms:
        return f"第{lecture}回の用語集に登録された用語がないため、確認問題を作れません。"
    term = random.choice(terms)
    return json.dumps(
        {"question": f"「{term['term']}」の意味は？", "answer": term["definition"]},
        ensure_ascii=False,
    )


def save_learning_log(filename: str, content: str) -> str:
    """利用者の承認後に学習記録を learning_log/ へ新規保存する。

    利用者が学習内容や振り返りをファイルに残したいと明示したときに使う。
    filename は英数字・ハイフン・アンダースコアだけの拡張子なし名にし、
    content には保存する本文を入れる。既存ファイルは上書きしない。
    """
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", filename):
        return "保存できません。ファイル名は英数字で始まる英数字・ハイフン・アンダースコア最大64文字にしてください。"
    if not isinstance(content, str) or not content.strip():
        return "保存できません。学習記録の本文が空です。"

    log_dir = LEARNING_LOG_DIR
    if log_dir.is_symlink():
        return "保存できません。learning_log/ がシンボリックリンクです。"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        expected_dir = PROJECT_DIR / "learning_log"
        if log_dir.resolve() != expected_dir.resolve():
            return "保存できません。保存先が許可された learning_log/ ではありません。"
        destination = log_dir / f"{filename}.md"
        # Exclusive creation makes an existing file (or symlink) impossible to overwrite.
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    except FileExistsError:
        return f"保存できません。{filename}.md は既に存在します（上書きしません）。"
    except OSError as exc:
        return f"学習記録を保存できませんでした: {exc.strerror or 'ファイル操作に失敗しました'}"
    return f"学習記録を learning_log/{filename}.md に保存しました。"
