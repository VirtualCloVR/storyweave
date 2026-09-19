"""Idempotently seed the v0.2 structured-context field-test fixtures.

Local development helper. Not required for normal installs.
This script intentionally uses only the Python standard library so it can be
run from a plain Python installation on the machine hosting Storyweave.
Set --api-base or STORYWEAVE_API to point at your backend.
"""
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_TITLE = "MyGO ワンライト"
THREAD_A_TITLE = "Structured Context フィールドテスト"
THREAD_B_TITLE = "Structured Context スコープ対照"
SOURCE = "BanG Dream! It's MyGO!!!!!"
SUMMARY = "- 愛音は自転車事故に遭う\n- 意識は失わない"


class ApiError(RuntimeError):
    pass


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def request(self, method: str, path: str, payload=None):
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(self.base + path, data=body, method=method, headers={"Accept": "application/json"})
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=15) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except (ValueError, AttributeError):
                pass
            raise ApiError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
        except URLError as exc:
            raise ApiError(f"接続失敗 {method} {path}: {exc.reason}") from exc
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, payload):
        return self.request("POST", path, payload)

    def patch(self, path, payload):
        return self.request("PATCH", path, payload)

    def put(self, path, payload):
        return self.request("PUT", path, payload)


def first(rows, title):
    return next((row for row in rows if row.get("title") == title), None)


def main():
    parser = argparse.ArgumentParser(description="Seed Storyweave structured-context field-test data")
    parser.add_argument("--api-base", default="http://localhost:8000/api")
    args = parser.parse_args()
    api = Api(args.api_base)

    projects = api.get("/projects")
    project = first(projects, PROJECT_TITLE)
    if project is None:
        project = api.post("/projects", {"title": PROJECT_TITLE})

    threads = api.get(f"/projects/{project['id']}/threads")
    thread_a = first(threads, THREAD_A_TITLE) or api.post(f"/projects/{project['id']}/threads", {"title": THREAD_A_TITLE})
    thread_b = first(threads, THREAD_B_TITLE) or api.post(f"/projects/{project['id']}/threads", {"title": THREAD_B_TITLE})

    characters = api.get("/characters")
    def character(name, aliases, facts):
        existing = next((c for c in characters if c.get("name") == name and c.get("sourceTitle") == SOURCE), None)
        if existing is not None:
            return existing
        return api.post("/characters", {"name": name, "sourceTitle": SOURCE, "aliases": aliases, "facts": facts})

    anon = character("千早愛音", ["愛音", "あのんちゃん", "Anon Chihaya"], [
        {"key": "身長", "value": "160cm"}, {"key": "誕生日", "value": "9/8"}, {"key": "学年", "value": "高等部1年A組"},
    ])
    tomori = character("高松燈", ["燈", "ともり", "Tomori Takamatsu"], [])

    api.put(f"/threads/{thread_a['id']}/characters", [{"characterId": anon["id"], "alwaysInclude": False}, {"characterId": tomori["id"], "alwaysInclude": False}])
    api.put(f"/threads/{thread_b['id']}/characters", [{"characterId": anon["id"], "alwaysInclude": False}])
    api.put(f"/threads/{thread_a['id']}/scene-facts", [{"key": "舞台", "value": "無人島"}, {"key": "半球", "value": "北半球"}, {"key": "季節", "value": "夏"}])
    api.put(f"/threads/{thread_b['id']}/scene-facts", [{"key": "舞台", "value": "箱根"}, {"key": "季節", "value": "冬"}, {"key": "時刻", "value": "夜"}])

    def session(thread, title, status="considering", summary=None):
        sessions = api.get(f"/threads/{thread['id']}/sessions")
        item = first(sessions, title)
        if item is None:
            item = api.post(f"/threads/{thread['id']}/sessions", {"title": title, "status": "considering"})
        if summary is not None:
            item = api.put(f"/sessions/{item['id']}/summary", {"summary": summary})
        elif item.get("status") != status:
            item = api.patch(f"/sessions/{item['id']}", {"status": status})
        return item

    canon_session = session(thread_a, "事故要素（フィールドテスト）", "adopted", SUMMARY)
    session_a = session(thread_a, "Structured Context 動作確認")
    session_b = session(thread_b, "スコープ確認")
    preview_text = "愛音が夏の無人島で自転車事故に遭ったが、意識は失わなかった。燈も同じ場にいる。"
    result = {"projectId": project["id"], "threadAId": thread_a["id"], "threadBId": thread_b["id"], "characterIds": {"千早愛音": anon["id"], "高松燈": tomori["id"]}, "canonSessionId": canon_session["id"], "sessionAId": session_a["id"], "sessionBId": session_b["id"], "previewRecommendation": preview_text}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ApiError, KeyError, ValueError) as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
