"""LLM layer: interprets intent and calls tools. Never computes facts itself."""
import json, os, re
from dotenv import load_dotenv
from openai import OpenAI
import tools
load_dotenv()
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
MAX_STEPS = 6

SYSTEM = """You are a laptop decision assistant. Budget is in INR.
RULES:
1. Never state specs, prices or scores from your own knowledge. Use ONLY tool results.
2. Interpret the request, call filter_laptops with ONLY constraints the user stated, then score_laptops on the returned ids with weights reflecting their priorities.
3. If the request has neither a budget nor a use case (too vague), do NOT call tools: ask ONE short clarifying question.
4. If filter_laptops returns 0 matches, do not invent options. Explain which constraint blocks it using the diagnostics and suggest the single best constraint to relax. Quote numbers ONLY from the diagnostics (use nearest_feasible_value); never guess a threshold.
5. Final message format: 2-4 sentences of recommendation referencing tool numbers, then a last line exactly `PICK: <id>` (or `PICK: NONE` if no recommendation / asking a question)."""

def _client():
    return OpenAI(api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
                  base_url=os.getenv("LLM_BASE_URL") or None)

def run_turn(history, user_text, client=None):
    client = client or _client()
    msgs = [{"role": "system", "content": SYSTEM}] + history + [{"role": "user", "content": user_text}]
    trace, reply = [], ""
    for _ in range(MAX_STEPS):
        resp = client.chat.completions.create(model=MODEL, messages=msgs,
                                              tools=tools.TOOL_SCHEMAS, temperature=0)
        m = resp.choices[0].message
        if not m.tool_calls:
            reply = m.content or ""
            break
        msgs.append(m.model_dump(exclude_none=True))
        for tc in m.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.dispatch(tc.function.name, args)
            trace.append({"tool": tc.function.name, "args": args, "result": result})
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
    else:
        reply = "I couldn't finish reasoning about this. Please rephrase your request.\nPICK: NONE"

    match = re.search(r"PICK:\s*([A-Za-z0-9_]+)", reply)
    pick = match.group(1) if match else "NONE"
    text = re.sub(r"\n?\s*PICK:.*$", "", reply, flags=re.S).strip()

    scored = [t["result"] for t in trace if t["tool"] == "score_laptops" and "ranking" in t["result"]]
    filters = [t["result"] for t in trace if t["tool"] == "filter_laptops"]
    pick_row, validated = None, True
    if pick != "NONE":
        rows = [r for s in scored for r in s["ranking"] if r["id"] == pick]
        if rows:
            pick_row = rows[0]
        else:  # LLM named something the tools never returned -> reject
            validated, pick = False, "NONE"
            text += "\n\n(Warning: the model named an option not found in tool results; recommendation withheld.)"

    if not trace:
        status = "clarify"
    elif filters and filters[-1]["count"] == 0:
        status = "no_match"
    else:
        status = "ok"
    return {"status": status, "text": text, "pick": pick, "pick_row": pick_row,
            "ranking": scored[-1]["ranking"] if scored else [],
            "diagnostics": filters[-1].get("diagnostics") if filters else None,
            "trace": trace, "validated": validated}