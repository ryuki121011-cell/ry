"""公開の外部確認。「終了コード0=成功」とみなさず、公開URLが実際に見えるかを確かめる。

使い方: python verify_publish.py <記事slug> [<記事slug> ...] [--wait 分]
Zennの反映には数分かかることがあるため、既定で最大10分、60秒間隔で再確認する。
すべて確認できたら終了コード0、確認できなければ1。
"""
import argparse
import sys
import time
import urllib.error
import urllib.request

USER = "ryu7865"


def is_live(slug):
    url = f"https://zenn.dev/{USER}/articles/{slug}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ops-verify)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:  # noqa: BLE001
        return False


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="+")
    ap.add_argument("--wait", type=int, default=10, help="最大待機(分)")
    a = ap.parse_args()
    deadline = time.time() + a.wait * 60
    pending = set(a.slugs)
    while pending:
        for s in list(pending):
            if is_live(s):
                print(f"OK  公開を確認: {s}", flush=True)
                pending.discard(s)
        if not pending or time.time() >= deadline:
            break
        time.sleep(60)
    for s in sorted(pending):
        print(f"NG  公開を確認できない: {s}")
    if pending:
        print("    Zennは投稿数の制限やデプロイの待ち行列で、公開が数時間〜数日遅れることがある。"
              "本文の `$`、フロントマター、slugも確認すること。追加の記事は出さない。")
    return 1 if pending else 0


if __name__ == "__main__":
    sys.exit(main())
