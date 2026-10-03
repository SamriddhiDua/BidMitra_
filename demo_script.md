# BidMitra Demo Script – 2-Minute Walkthrough

Use this script when doing a live demo (hackathon, video, or screen recording).

---

## Setup (before the demo)

1. `python scripts/make_sample_data.py` – generate fresh sample data
2. `streamlit run app.py` – start the app
3. Have Ollama running with your model: `ollama run phi3:mini`
4. Set `OPEN_LLM_MODEL=phi3:mini` in `.env`

---

## Minute 1: Dashboard + Profiles

**[Show: top of screen]**
- Point out the snapshot date banner: *"This is all local data from our CSV. No GeM login needed."*
- Point out the SAMPLE DATA banner: *"These are synthetic bids for demo purposes."*
- Show the profile dropdown: *"Switch between three demo profiles — Panipat spares, Mohali furniture, Ludhiana safety."*

**[Switch to Ludhiana safety profile]**
- Show the Dashboard: *"This is the Ludhiana safety equipment supplier's view."*
- Point out the profile card with completeness bar and self-declared chips.
- Hover over the "MSE (Self-declared)" chip: *"All of this is self-reported. We never claim to verify it."*
- Show the top 5 matches with reason chips.

**[Switch back to Panipat industrial spares]**
- Show the metrics row: *"X bids shortlisted out of 117 in the snapshot, Y are 'Bid', Z are 'Maybe'."*

---

## Minute 2: Shortlist + AI + What-If

**[Go to Shortlist tab]**
- Point at the AI engine badge: *"This shows the open-weight model running locally via Ollama."*
- Type in the Hinglish box: *"Panipat ke paas valve, EMD 30 hazaar tak"*
- Click Search.
- **Point at the Raw model output expander**: *"Here's what the model returned — raw JSON."*
- Show the "AI ne ye samjha" panel: *"We validated and displayed what the model understood, BEFORE applying it."*
- Click Apply AI filter: *"Now the shortlist updates — but the AI didn't rank anything. The scoring code did."*
- Read aloud: *"AI sirf aapki baat samajhta hai. Matching code karta hai."*

**[Show a bid card]**
- Point at the reason chips: *"This is the star feature — it tells you WHY this bid was shown."*
- Click "Mark bid" → click "Saved": *"This goes into the Bid Diary, session-only."*

**[Go to What-If tab]**
- Show the table: *"If you extend your radius by 100 km, you unlock N more bids."*
- Show the bar chart.
- *"No new logic — same scorer, different profile numbers."*

**[Go back to Dashboard]**
- Show the Bid Diary table with the saved bid.

---

## Key talking points

- Open-weight model (≤ 10B params, local, no API key)
- Model's only job: text → JSON. Never sees bids.
- All data is local CSV. No scraping, no credentials.
- Works fully offline (only the Hinglish box needs the model)
- MIT licensed, open source repo

---

## If something goes wrong

| Problem | Fix |
|---------|-----|
| No bids shown | Run `python scripts/make_sample_data.py`, reload |
| AI unavailable | Expected — sidebar form still works |
| Wrong profile showing | Use the profile dropdown in the sidebar |
| App won't start | Check `pip install -r requirements.txt` |
