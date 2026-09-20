"""週次の指標収集。認証情報は環境変数から名前で読み、値は出力しない。

集めるもの:
  - Gumroad: 商品ごとの公開状態・販売数・売上(環境変数 GUMROAD_TOKEN があれば)
  - Zenn: 記事のいいね数・コメント数・公開状態(公開API)、本の公開状態
結果は ops/ledger/metrics_YYYY-MM-DD.json に保存し、ops/ledger/LEDGER.md に1行追記する。
失敗は握りつぶさず、"errors" に残して終了コード1で終わる(サイレント失敗を避ける)。
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ZENN_USER = "ryu7865"
ROOT = pathlib.Path(__file__).resolve().parent
LEDGER = ROOT / "ledger"
UA = {"User-Agent": "Mozilla/5.0 (ops-metrics)"}


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def zenn_articles(errors):
    out = []
    art_dir = ROOT.parent / "articles"
    for f in sorted(art_dir.glob("*.md")):
        slug = f.stem
        row = {"slug": slug}
        try:
            j = get_json(f"https://zenn.dev/api/articles/{slug}")["article"]
            row.update(live=True, liked=j.get("liked_count"), comments=j.get("comments_count"),
                       letters=j.get("body_letters_count"))
        except urllib.error.HTTPError as ex:
            row.update(live=False, http=ex.code)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"zenn:{slug}:{type(ex).__name__}")
        out.append(row)
    return out


def zenn_books(errors):
    out = []
    books_dir = ROOT.parent / "books"
    for d in sorted(p for p in books_dir.iterdir() if p.is_dir()):
        row = {"slug": d.name}
        try:
            j = get_json(f"https://zenn.dev/api/books/{d.name}")["book"]
            row.update(live=True, price=j.get("price"), liked=j.get("liked_count"))
        except urllib.error.HTTPError as ex:
            row.update(live=False, http=ex.code)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"zennbook:{d.name}:{type(ex).__name__}")
        out.append(row)
    return out


def gumroad(errors):
    tok = os.environ.get("GUMROAD_TOKEN")
    if not tok:
        errors.append("gumroad:GUMROAD_TOKENが未設定")
        return None
    try:
        j = get_json("https://api.gumroad.com/v2/products", {"Authorization": f"Bearer {tok}"})
        return [{"name": p.get("name"), "published": p.get("published"), "price": p.get("formatted_price"),
                 "sales_count": p.get("sales_count"), "sales_usd_cents": p.get("sales_usd_cents"),
                 "url": p.get("short_url")} for p in j.get("products", [])]
    except Exception as ex:  # noqa: BLE001
        errors.append(f"gumroad:{type(ex).__name__}")
        return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    errors = []
    today = datetime.date.today().isoformat()
    data = {"date": today, "zenn_articles": zenn_articles(errors), "zenn_books": zenn_books(errors),
            "gumroad": gumroad(errors), "errors": errors}
    LEDGER.mkdir(exist_ok=True)
    (LEDGER / f"metrics_{today}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    arts = data["zenn_articles"]
    live = sum(1 for a in arts if a.get("live"))
    likes = sum((a.get("liked") or 0) for a in arts)
    gr = data["gumroad"] or []
    sales = sum((p.get("sales_count") or 0) for p in gr)
    line = (f"| {today} | 記事 公開{live}/{len(arts)} いいね{likes} | 本 "
            f"{sum(1 for b in data['zenn_books'] if b.get('live'))}冊公開 | Gumroad 販売{sales}件 | "
            f"{'エラー: ' + ', '.join(errors) if errors else 'OK'} |\n")
    ledger_md = LEDGER / "LEDGER.md"
    if not ledger_md.exists():
        ledger_md.write_text("# 運用台帳(週次)\n\n| 日付 | Zenn記事 | Zenn本 | Gumroad | 状態 |\n|---|---|---|---|---|\n",
                             encoding="utf-8")
    with ledger_md.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
