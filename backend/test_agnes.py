import asyncio
import json
import httpx

BASE = "http://127.0.0.1:8000"


async def test_ask():
    async with httpx.AsyncClient(timeout=90) as client:
        body = {
            "question": "美国站儿童玩具需要CPC认证吗？上架前注意什么？",
            "knowledge_base": "compliance"
        }
        resp = await client.post(
            f"{BASE}/api/ask",
            json=body,
            follow_redirects=True,
        )
        print(f"=== Status: {resp.status_code} ===")

        current_event = None
        current_data_str = None
        raw_lines = []
        for line in resp.text.split("\n"):
            if not line.strip():
                continue

            # Accumulate raw for debugging
            raw_lines.append(line.strip())

            if line.startswith("event: "):
                # Flush previous event
                if current_event and current_data_str:
                    await _flush_event(current_event, current_data_str)
                current_event = line[7:].strip()
                current_data_str = ""
            elif line.startswith("data: "):
                if current_data_str:
                    current_data_str += "\n" + line[6:]
                else:
                    current_data_str = line[6:]
            elif line.startswith(":"):
                # Comment
                pass

        # Flush last event
        if current_event and current_data_str:
            await _flush_event(current_event, current_data_str)

        print(f"\n\n{'='*50}")
        print(f"Raw output lines ({len(raw_lines)}):")
        for rl in raw_lines:
            print(f"  {rl[:120]}")


async def _flush_event(event_type: str, data_str: str):
    """Parse and print SSE event.

    Real payload shapes from /api/ask:
      sources -> data is a JSON array (list of source objects)
      delta   -> data is {"content": "..."}
      done     -> data is {"messageId", "citations": [...], "sessionId"}
    """
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        if event_type == "delta":
            print(f"[delta] {data_str[:100]}", end="", flush=True)
        else:
            print(f"\n[{event_type}] (parse error: {data_str[:60]})")
        return

    if event_type == "delta":
        content = data.get("content", "") if isinstance(data, dict) else ""
        print(f"[delta] {content}", end="", flush=True)
    elif event_type == "error":
        print(f"\n\n[ERROR] {json.dumps(data, ensure_ascii=False)[:300]}")
    elif event_type == "sources":
        sources = data if isinstance(data, list) else data.get("sources", [])
        print(f"\n\n--- Sources ({len(sources)}) ---")
        for s in sources[:5]:
            print(f"  [{s.get('id')}] {s.get('title', '')} (conf={s.get('confidence')})")
    elif event_type == "done":
        print(f"\n\n[Done] citations={data.get('citations', [])}, sessionId={data.get('sessionId', 'N/A')}")
    elif event_type == "ping":
        pass


if __name__ == "__main__":
    asyncio.run(test_ask())
