"""Runs 6 scenarios through the real LLM and writes tests/results.md. Run: python -m tests.run_scenarios"""
import agent


SCENARIOS = [
    ("1 Normal", "Business laptop under 70000 rupees with at least 12 hours of battery."),
    ("2 Normal", "Programming laptop under 110000 rupees with at least 32GB RAM."),
    ("3 Ambiguous", "I need a good laptop."),
    ("4 Ambiguous", "Something powerful but also very light and cheap."),
    ("5 Impossible", "Gaming laptop with dedicated GPU under 30000 rupees."),
    ("6 Impossible", "Laptop under 100000 rupees with 32GB RAM that weighs under 1.2 kg."),
]


if __name__ == "__main__":
    out = ["# Test results\n"]
    for name, q in SCENARIOS:
        r = agent.run_turn([], q)
        out.append(f"## {name}\n**Query:** {q}\n\n**Status:** {r['status']} | **Pick:** {r['pick']} | **Validated:** {r['validated']}\n")
        for t in r["trace"]:
            out.append(f"- `{t['tool']}({t['args']})`")
        out.append(f"\n**Response:** {r['text']}\n")
        print(name, "->", r["status"], r["pick"])
    open("tests/results.md", "w", encoding="utf-8").write("\n".join(out))
