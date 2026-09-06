"""Verify live OpenAI-compatible streaming and message persistence."""
import json
import os
import httpx

api = os.getenv("STORYWEAVE_API", "http://localhost:8000/api").rstrip("/")

with httpx.Client(timeout=httpx.Timeout(240, connect=10)) as client:
    project_id = None
    try:
        project = client.post(f"{api}/projects", json={"title": "LLM smoke", "systemPrompt": "日本語で短く回答してください。"}).raise_for_status().json()
        project_id = project["id"]
        thread = client.post(f"{api}/projects/{project_id}/threads", json={"title": "Context check"}).raise_for_status().json()
        session = client.post(f"{api}/threads/{thread['id']}/sessions", json={"title": "確定コード", "status": "considering"}).raise_for_status().json()
        adopted = client.put(f"{api}/sessions/{session['id']}/summary", json={"summary": "- 確定済みコードは KAGARI_731"}).raise_for_status().json()
        assert adopted["status"] == "adopted" and adopted["adoptionSummary"].strip()
        current = client.post(f"{api}/threads/{thread['id']}/sessions", json={"title": "継承確認"}).raise_for_status().json()

        tokens: list[str] = []
        with client.stream("POST", f"{api}/sessions/{current['id']}/chat", json={"content": "確定済みコードをそのまま一つだけ答えてください。"}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                payload = json.loads(data)
                if payload.get("token"):
                    tokens.append(payload["token"])
        answer = "".join(tokens)
        assert answer.strip(), "The LLM stream returned no tokens"
        assert "KAGARI_731" in answer, f"Confirmed context was not reflected: {answer[:300]}"
        messages = client.get(f"{api}/sessions/{current['id']}/messages").raise_for_status().json()
        assert [item["role"] for item in messages] == ["user", "assistant"]
        assert messages[-1]["content"] == answer
        print(f"llm smoke: streamed {len(answer)} characters, inherited context, and persisted the assistant message")
    finally:
        if project_id:
            client.delete(f"{api}/projects/{project_id}").raise_for_status()
