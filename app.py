import pandas as pd
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
import agent

st.set_page_config(page_title="AI Laptop Decision Assistant", page_icon="💻", layout="wide")
st.title("💻 AI Laptop Decision Assistant")
st.caption("The LLM understands your request. Filtering and scoring are deterministic Python.")

if "history" not in st.session_state:
    st.session_state.history = []
    st.session_state.turns = []

def render(r):
    if r["status"] == "clarify":
        st.info(r["text"])
        return
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📊 Facts (deterministic code)")
        if r["status"] == "no_match":
            st.error("No laptop satisfies all constraints.")
            if r["diagnostics"]:
                st.dataframe(pd.DataFrame(r["diagnostics"]), hide_index=True)
        elif r["ranking"]:
            rows = [{"Rank": x["rank"], "Name": x["name"], "Score": x["score"],
                     "Price ₹": x["specs"]["price_inr"], "RAM": x["specs"]["ram_gb"],
                     "Storage": x["specs"]["storage_gb"], "Battery h": x["specs"]["battery_hours"],
                     "Weight kg": x["specs"]["weight_kg"], "Rating": x["specs"]["rating"]}
                    for x in r["ranking"]]
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            if r["pick_row"]:
                st.markdown(f"**Selected: {r['pick_row']['name']}** — score {r['pick_row']['score']}/100")
                st.json(r["pick_row"]["breakdown"], expanded=False)
    with c2:
        st.subheader("🤖 AI recommendation")
        st.write(r["text"])
    with st.expander("🔧 Tool calls"):
        for t in r["trace"]:
            st.code(f"{t['tool']}({t['args']})")

for user_msg, r in st.session_state.turns:
    with st.chat_message("user"):
        st.write(user_msg)
    with st.chat_message("assistant"):
        render(r)

if prompt := st.chat_input("e.g. Laptop for programming under ₹90,000 with good battery"):
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            r = agent.run_turn(st.session_state.history, prompt)
        render(r)
    st.session_state.history += [{"role": "user", "content": prompt},
                                 {"role": "assistant", "content": r["text"]}]
    st.session_state.turns.append((prompt, r))
