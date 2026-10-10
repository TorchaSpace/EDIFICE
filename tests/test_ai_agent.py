import json

from edifice.ai.agent import Toolbox, run_chat
from edifice.service import Project


def _fake_stream(rounds):
    """Her çağrıda bir tur olay üretir (gerçek SSE olaylarının biçiminde)."""
    it = iter(rounds)

    def stream(key, model, system, messages, tools, cancel):
        yield from next(it)
    return stream


def test_tools_return_json_for_all_tools():
    p = Project.mock()
    t = Toolbox({1: p}, 1)
    for name, args in (("list_buildings", {}), ("get_building", {}), ("get_opportunities", {}),
                       ("simulate_scenario", {"codes": ["LED"]}), ("best_package", {"budget": 2e6}),
                       ("get_monthly", {"utility": "gas"}), ("get_equipment", {}), ("search_evidence", {"query": "emisyon"})):
        assert json.loads(t.run(name, args)) is not None
    assert "hata" in json.loads(t.run("get_building", {"building_id": 99}))


def test_agent_runs_tool_then_answers():
    p = Project.mock()
    tool_round = [
        ("content_block_start", {"index": 0, "content_block": {"type": "tool_use", "id": "t1", "name": "get_building"}}),
        ("content_block_delta", {"index": 0, "delta": {"type": "input_json_delta", "partial_json": "{}"}}),
        ("message_delta", {"delta": {"stop_reason": "tool_use"}}),
    ]
    text_round = [
        ("content_block_start", {"index": 0, "content_block": {"type": "text"}}),
        ("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": "Skor "}}),
        ("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": "40"}}),
        ("message_delta", {"delta": {"stop_reason": "end_turn"}}),
    ]
    msgs = [{"role": "user", "content": "Sağlık skorum kaç?"}]
    got, tools = [], []
    run_chat("k", "m", msgs, Toolbox({1: p}, 1), p.building.name, got.append, tools.append, lambda: False,
             stream=_fake_stream([tool_round, text_round]))
    assert "".join(got).strip() == "Skor 40" and tools == ["get_building"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[2]["content"][0]["type"] == "tool_result" and "saglik_skoru" in msgs[2]["content"][0]["content"]


def test_sse_parser_handles_split_chunks():
    from edifice.ai.agent import _sse_events
    buf = bytearray(b'event: content_block_delta\ndata: {"a": 1}\n\nevent: message_delta\ndata: {"b"')
    assert list(_sse_events(buf)) == [("content_block_delta", {"a": 1})]
    buf += b': 2}\n\n'
    assert list(_sse_events(buf)) == [("message_delta", {"b": 2})] and not buf


def test_http_error_message_is_readable():
    from edifice.ai.agent import _error_text
    msg = _error_text(401, json.dumps({"error": {"message": "invalid x-api-key"}}))
    assert "geçersiz" in msg and "invalid x-api-key" in msg
