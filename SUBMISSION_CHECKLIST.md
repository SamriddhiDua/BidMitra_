# Submission Checklist – BidMitra

Complete all items below before submitting to the MLH hackathon.

## Repository

- [ ] Repo is **public** on GitHub
- [ ] **License shows** in the GitHub sidebar (GitHub detects it automatically when `LICENSE` file is at repo root with standard MIT text)
- [ ] Open the repo in a **private/incognito window** and follow the README as an outsider — verify you can:
  - [ ] Find the license
  - [ ] Understand the AI contribution
  - [ ] Follow the README to run the project

## Pre-submission script

Run this and fix all ❌ failures:
```bash
python scripts/check_submission.py
```

## Placeholders to replace

Search for `<FILL_` in all files and replace each one:

| Placeholder | Where | What to put |
|-------------|-------|-------------|
| `<FILL_NAME>` | `LICENSE` | Your full name or team name |
| `<FILL_MODEL_LICENSE_URL>` | `README.md`, `THIRD_PARTY.md`, `.env.example` | URL for the model license (e.g., https://huggingface.co/microsoft/Phi-3-mini-4k-instruct) |
| `<FILL_DEMO_URL>` | `README.md` | Streamlit Cloud URL, or remove if not deployed |
| `<FILL_WHAT_WE_WROTE_OURSELVES>` | `README.md` section 7 | Describe original work: scoring formula, profile model, domain input from real user, etc. |

## OrganizerHQ Submission

1. Go to the event's OrganizerHQ Challenges page
2. Click **Submit Project**
3. Fill in:
   - **Repo link:** your GitHub URL
   - **Project name:** BidMitra
   - **Description:** One-paragraph pitch (use the README intro)
   - **Technologies:** Python, Streamlit, pandas, Ollama, `<your model name>` (e.g., Phi-3 Mini)
   - **Demo URL:** your Streamlit Cloud link (or local screenshot/GIF)
4. Select **Best Open-Source AI Project** and any other eligible challenge
5. Submit before the host's deadline

## Note on Streamlit Community Cloud deployment

The deployed link will **not** have the local model running, so the Hinglish AI box shows its fallback message ("AI unavailable — use the sidebar form"). All other features (shortlist, what-if, profiles, diary) work normally. This is expected and documented in the README.

Deploy steps:
1. Push the repo to GitHub (public)
2. Go to https://share.streamlit.io → New app → your repo → `bidmitra/app.py`
3. No secrets needed for the AI-free version (the app degrades gracefully)
4. Set `OPEN_LLM_MODEL` in Streamlit secrets if you have a hosted endpoint

## Live demo readiness

- [ ] Run `python scripts/make_sample_data.py` to regenerate fresh data
- [ ] Have Ollama running with your model before the demo
- [ ] Follow `docs/demo_script.md` (2-minute walkthrough)
- [ ] Know the top 5 things that can go wrong: see README section 4 (Limits)
