# AI Laptop Decision Assistant (#evn-lf26-ai11)

Streamlit assistant where an LLM interprets the request and calls deterministic Python tools. The LLM never computes facts: filtering and scoring happen in plain Python, and the UI shows facts and the AI recommendation separately.

## Architecture
- `data/laptops.json` – 10 illustrative laptops (price in INR, specs, ratings, use cases)
- `tools.py` – `filter_laptops`, `score_laptops`, `get_laptop_details` (pure Python, no LLM) + tool schemas
- `agent.py` – tool-calling loop; validates the LLM's pick against tool results
- `app.py` – UI: **Facts (code)** column vs **AI recommendation** column, plus tool-call log
- `tests/test_tools.py` – offline tests for the deterministic tools
- `tests/run_scenarios.py` – runs the 6 scenarios through the LLM and writes `tests/results.md`

## Run
```
pip install -r requirements.txt
copy .env.example .env          # Windows (use cp on Mac/Linux), then add your key
python -m streamlit run app.py
python -m tests.test_tools      # offline tool tests
python -m tests.run_scenarios   # 6 LLM scenarios -> tests/results.md
```
Provider settings (`.env`): `LLM_API_KEY`, optional `LLM_BASE_URL` and `LLM_MODEL`. Tested with Groq (`openai/gpt-oss-20b`).

## Test scenarios (2 normal, 2 ambiguous, 2 impossible)
| # | Type | Query | Expected | Result |
|---|------|-------|----------|--------|
| 1 | Normal | Business laptop under ₹70k with at least 12h battery | 2 matches (L01, L07), one picked | ok, pick L07 |
| 2 | Normal | Programming laptop under ₹110k with at least 32GB RAM | 1 match (L09) | ok, pick L09 |
| 3 | Ambiguous | "I need a good laptop." | Clarifying question, no tools | clarify, no pick |
| 4 | Ambiguous | "Something powerful but also very light and cheap." | Clarifying question or stated trade-off | clarify, no pick |
| 5 | Impossible | Gaming laptop with dedicated GPU under ₹30k | 0 matches; nearest feasible price ₹72,000 | no_match, no pick |
| 6 | Impossible | Under ₹100k, 32GB RAM, under 1.2 kg | 0 matches; relax RAM to 16GB (3 options) | no_match, no pick |

Full responses and the tool calls made for each scenario are in [`tests/results.md`](tests/results.md).

## Obstacle log
1. **LLM quoting specs from memory** → system prompt forbids it; the app only displays numbers from tool results.
2. **LLM recommending an option not in the data** → LLM must end with `PICK: <id>`; code checks it exists in `score_laptops` output and withholds it otherwise.
3. **Empty results gave an unhelpful "no laptops found"** → `filter_laptops` returns diagnostics (matches if each constraint is dropped) so the explanation is factual.
4. **Vague queries triggered filters with guessed values** → rule: only pass stated constraints; ask one question if there is no budget or use case.
5. **Scores unstable across runs** → scoring is pure min-max normalisation with normalised weights; temperature 0; unit tests assert determinism.
6. **Groq rejected tool calls because the model sent `null` for unused filters** → made all schema fields nullable and made the tools ignore `null` values.
7. **LLM invented a ₹35,000 threshold in the impossible scenario** (real nearest price is ₹72,000) → diagnostics now include `nearest_feasible_value`, and the prompt says to quote numbers only from diagnostics.
8. **Test script failed with "Missing credentials"** because only `app.py` loaded `.env` → moved `load_dotenv()` into `agent.py` so the app and tests both use it.