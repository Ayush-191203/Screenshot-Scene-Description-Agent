# Sample outputs

These artifacts come from a **real Finviz capture with a real NVIDIA vision-LLM call**
(`https://www.finviz.com`, headed Chromium, Playwright web backend, provider `nvidia`, model
`nvidia/nemotron-3.5-super-vl-120b-a12b`, run on 2026-10-21). This is a fully live run - no
mocking anywhere in the pipeline.

**Measured performance** (from `capture_20261021_074500.json` `durations_ms`):
- Capture (Playwright, headed Chromium): 8.05s
- LLM description (NVIDIA Nemotron 3.5 Super VL): 10.52s
- Branding (logo + caption): 0.15s
- **Total: 19.21s** (the LLM call alone is comfortably under a 15s budget)

**Honest note on description accuracy:** the model correctly identifies the site, layout,
market sentiment, and overall structure, but can hallucinate precise numeric values from the
small, downscaled chart text (e.g. it states "S&P 500 closed at 4,420.68" while the real chart
in the image shows ~7712). Treat generated numbers as illustrative, not authoritative - this is
a known limitation of vision LLMs reading dense, small text in a downscaled screenshot.

Files:
- `capture_20261021_074500.png` - original, unmodified screenshot.
- `capture_20261021_074500_branded.png` - branded copy (logo + caption band).
- `capture_20261021_074500.txt` - full description text.
- `capture_20261021_074500.json` - run metadata (provider, model, durations, token usage).
- `log_excerpt.txt` - tail of the rotating log file for this run.

