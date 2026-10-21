# Sample outputs

These artifacts come from a **real Finviz capture** (`https://www.finviz.com`, headed Chromium,
Playwright web backend, run on 2026-10-21).

**Provider note:** No Anthropic/OpenAI API key was available in the environment this was
generated in, so the **`mock` provider** was used for the description step (clearly visible in
`capture_20261021_061908.json` as `"provider": "mock"` and in the caption text itself). The
screenshot capture, branding, and artifact pipeline are real; only the vision-LLM description is
a deterministic placeholder. See the main README's "Known limitations / unverified" section.

Files:
- `capture_20261021_061908.png` - original, unmodified screenshot.
- `capture_20261021_061908_branded.png` - branded copy (logo + caption band).
- `capture_20261021_061908.txt` - full description text.
- `capture_20261021_061908.json` - run metadata.
- `log_excerpt.txt` - tail of the rotating log file for this run.
