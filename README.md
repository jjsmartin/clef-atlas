# Clef Atlas

A local GeoGuessr-style presentation demo: humans guess locations, Clef returns country probabilities, and an optional vision LLM chooses from the same candidates. Python + FastAPI; no Node or GPU required.

## Run on macOS / VS Code

Requires Python 3.11 or newer. Extract this folder, open it in VS Code, then in its terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1
```

Open http://localhost:8000. Offline practice works without credentials. Select your virtual environment with VS Code's “Python: Select Interpreter”; the included launch configuration also runs the app.

For live inference, edit `.env` with your existing `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_AUTH_TOKEN`, restart the server, then select **Live API**. Shell environment variables take precedence over `.env`. Optional: set `OPENAI_API_KEY` for the conventional LLM comparison; `OPENAI_MODEL` defaults to `gpt-4o-mini` and can be changed to a compatible vision model.

## Implementation walkthrough

Open `clef_walkthrough.ipynb` in VS Code with the Jupyter extension. With the project virtual environment active, run `python -m pip install -r requirements-notebook.txt`, then select that environment as the notebook kernel. Run all cells in order. The walkthrough uses the actual application functions, explains Clef versus generative LLMs, and covers schemas, probabilities, photo preprocessing, hierarchy, routing policy and evaluation. Network calls are disabled by default; set the explicit live switches to use your credentials.

## Play / present

1. Try the four text practice rounds in offline mode. These use invented fixtures, not real model predictions or captured replays.
2. Run a text round live to confirm your credentials.
3. Upload a PNG, JPEG or WebP photo under 4 MiB / 16 megapixels, preferably one you own. Enter its known country and optional GPS coordinates for reveal. These answers never enter the prediction request. Supply only visible clues in the optional clue field.
4. Choose your country and optionally click the map. Run Clef, then reveal.
5. Compare direct vs hierarchical selection. Change candidate countries and the automation threshold. Compare all three models for end-to-end timing and correctness.
6. Export session JSON for later analysis. Exports contain prediction results, not photos or credentials.

No real photo dataset is included. Bring 10–30 photos with known countries and GPS coordinates for a team session. Bundled countries are a 17-country demo shortlist, not global coverage. Add candidates in `app/main.py`'s `COUNTRIES` mapping if needed. Candidate pins use capitals, NOT inferred photo coordinates. Only human map guesses get a distance score.

## How to interpret results

- Clef receives the same photo/clue and candidates as the LLM. Image re-encoding removes metadata and reduces size.
- Hierarchical mode greedily selects continent, region, then country. An early error excludes later alternatives. Its final country probabilities are conditional on that branch; a forced one-country branch shows 100% by construction, not certainty about the original image. The slider is a teaching policy, not a reliable production safety gate.
- API latency includes network, server and (for hierarchy) multiple sequential calls. It is not model-only latency.
- Clef estimated costs use provider input token counts and October 2026 documented input rates: $0.240/M (Clef), $0.038/M (Clef-flash). Update `RATES` as prices change. No LLM cost is estimated. Missing LLM credentials give a per-model error while retaining successful Clef results.
- Offline fixtures give no meaningful model comparison, timing or cost. The application does not silently substitute fixtures when live APIs fail.
- Basemap/Leaflet assets need internet. Offline play and coordinate entry still work without them; map tiles may be unavailable.
- Tokens remain server-side. Keep `.env` uncommitted. Bind to localhost; this demo has no authentication and is not designed as a public service. Live uploaded photos are sent to the selected model provider.

## Verification

```bash
python -m pip install pytest
python -m pytest -q
```

Tests mock provider calls and cover request schemas, image metadata removal, candidate validation, reveal handling, hierarchy and API failure paths. Real provider calls need your credentials and were not executed during project creation.

## Sources

- Clef API, image limits and prices: https://developers.cloudflare.com/workers-ai/models/clef/
- Multimodal data URL example / pricing update: https://developers.cloudflare.com/changelog/post/2026-10-09-clef-omni-workers-ai/
- REST setup: https://developers.cloudflare.com/workers-ai/get-started/rest-api/

This is an independent demonstration, not the GeoGuessr service.
# clef-atlas
