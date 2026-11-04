"""Offline tests for deterministic tools (no API key needed). Run: python -m tests.test_tools"""
import tools

def test_filter_normal():
    r = tools.filter_laptops(max_price_inr=60000, use_case="student")
    assert r["count"] == 3 and {m["id"] for m in r["matches"]} == {"L01", "L02", "L08"}

def test_filter_impossible():
    r = tools.filter_laptops(max_price_inr=30000, needs_dedicated_gpu=True)
    assert r["count"] == 0 and r["diagnostics"][0]["matches_if_dropped"] > 0

def test_score_deterministic():
    a = tools.score_laptops(["L03", "L07"], {"battery": 3, "price": 1})
    b = tools.score_laptops(["L03", "L07"], {"battery": 3, "price": 1})
    assert a == b and a["ranking"][0]["id"] == "L07"

def test_unknown_id():
    r = tools.score_laptops(["ZZZ"])
    assert "error" in r

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("PASS", n)
