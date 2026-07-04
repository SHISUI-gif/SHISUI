# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

`my-genspark` is 志粋(Shisui) — a fully local AI assistant built on Ollama (Qwen models), with one deliberate exception: the "夜間修行" (autonomous study loop) calls the Gemini API as an external "mentor." Every other feature runs with zero cloud dependency except Tavily (web search) and Gemini (study loop only, requires `GEMINI_API_KEY`).

The production frontend is Next.js (`frontend/`) talking to the FastAPI backend (`src/api/main.py`, port 8000). `shisui_app.py` (Gradio, port 7860) was the original prototype UI — it still works and shares the exact same brain (`src/chat/shisui_chat.py:stream_shisui_events()`), but is retired from normal use and should NOT be run alongside FastAPI: both processes independently touch the same on-disk ChromaDB stores (`NEOCORTEX_DB_DIR`, `LITERARY_CHROMA_DIR`) via `PersistentClient`, which does not support concurrent multi-process access and throws intermittent `chromadb.errors.InternalError: ... Error finding id`. Only run one of the two at a time. Never duplicate chat logic across the two surfaces either way; extend `stream_shisui_events()` and let both frontends adapt its output.

## Commands

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/              # full suite, ~50 tests, all mocked (no live Ollama/network needed)
python -m pytest tests/test_foo.py -v -k test_name   # single test

python app.py <subcommand>           # research/minutes/voicechat/debate/memory/corpus/study/
                                      # debate-autonomous/api — see app.py's module docstring for the full list
python shisui_app.py                 # Gradio UI
cd frontend && npm run dev           # Next.js dev server (port 3000), needs `python app.py api` running separately
```

Node/npm are symlinked at `~/.local/bin/node`/`npm`/`npx` (installed via nvm, not Homebrew — Homebrew requires interactive sudo and isn't installed). Ollama CLI is symlinked at `~/.local/bin/ollama` (same reason: the official installer's PATH step needs sudo).

## Architecture: the layering that matters

- `src/common/` — shared primitives every other package depends on: `llm_client.py` (Ollama wrapper), `persona.py` (`SHISUI_SYSTEM_PROMPT`, the "掟" — the only place Shisui's personality is defined), `tools.py` (function-calling registry), `embeddings.py` (`OllamaEmbeddingFunction`, shared by every ChromaDB collection in the project — memory, literary corpus).
- `src/chat/shisui_chat.py` — the brain. `stream_shisui_events()` yields structured `ChatEvent(type, text)` where type is `thinking`/`content`/`tool_status`. `stream_shisui_reply()` (Gradio) and `src/api/main.py` (NDJSON) are both thin formatting layers over this — never add chat logic anywhere else.
- `src/memory/` — hippocampus (SQLite, raw episodic log) → sleep.py (nightly consolidation into) → neocortex (ChromaDB, long-term). `src/memory/scheduler.py:maybe_run_daily_sleep()` triggers this once/day, lazily, on first app launch of the day (not real idle detection).
- `src/corpus/` — two independent pipelines sharing one ChromaDB collection (`literary_corpus`) and one core function (`ingest.ingest_one_work()`): (1) `curated_list.py` — 5 hand-picked authors, run via `corpus ingest`, and (2) `full_archive.py` — a checkpointed crawler over *all* ~2000 Aozora Bunko authors, advancing a few works/day via `corpus.scheduler.maybe_run_daily_archive_crawl()`. **Neither pipeline ever stores raw scraped text in the vector DB** — only a 2-sentence-max, LLM-generated, anti-verbatim-guarded "style descriptor" (`ingest._generate_style_descriptor` + `_contains_verbatim_excerpt`). Keep this invariant if you touch either pipeline; it's a deliberate copyright-safety design, not an oversight.
- `src/debate/` — LangGraph 3-agent debate (`graph.py`). Round termination isn't just `max_rounds`: `_should_continue` also checks embedding-similarity convergence between consecutive facilitator rounds (ASAL-inspired early stopping, see `debate_min_rounds_before_novelty_check`/`debate_novelty_similarity_threshold` in settings). `autonomous.py` reuses this + `src/study/weakness_finder.py` to let Shisui debate its own weak topics unattended (no `input()` calls — verify this if you touch it, since `debate_agent.collect_feedback()` does call `input()` and must never be invoked from an unattended path).
- `src/study/` — the Gemini-backed study loop. `weakness_finder.py` (shared with `debate/autonomous.py`) mines `⚠️`-flagged hippocampus episodes + `feedback_store` "incorrect" verdicts for topics. `report.py`'s `append_session()`/`get_unread_report()`/`mark_report_read()` is the shared "morning briefing" mechanism used by *both* the study loop and autonomous debate — don't build a second one.
- `src/chat/model_router.py` — classifies each user message (CODING/REASONING/CHAT) with a small model and routes to a bigger specialized one. Fails open to `settings.ollama_model` on any error (missing model, classifier down) — preserve this fallback if you touch it, it's what keeps routing from ever taking down the main chat path.
- `src/core/error_log.py` + `src/core/evolution.py` — the self-repair protocol. Any uncaught exception in `stream_shisui_events()` is logged (full traceback) via `error_log.log_error()`. `evolution.generate_fix_proposals()` reads unreviewed errors, extracts the in-project file from the traceback, and asks `settings.evolution_fix_model` (a local coding model, not Gemini — keeps self-repair fully local) for a unified diff. Proposals land in `output/evolution/pending/*.json` — **never written to real source files automatically**. `python app.py evolution {scan,list,show,apply,reject}` is the human-in-the-loop review flow; `apply` refuses if the git working tree isn't clean, then commits the applied patch so it's revertable via `git revert`. Do not remove the clean-tree check or the apply/no-auto-apply boundary — this was an explicit safety decision, not a placeholder to relax later. **Verify generated diffs before applying** — in practice the coding model has produced syntactically broken patches (a duplicated line, a truncated argument) when it lacked the real root cause; `apply` will happily `git apply` a diff that doesn't actually fix anything or doesn't even parse as valid Python.
- `src/core/feedback_log.py` — a second, narrower input to the same self-repair effort: `error_log` only catches Python exceptions, so a user saying "that's wrong" with no crash involved was invisible to it. `_maybe_log_correction_feedback()` in `shisui_chat.py` runs a keyword regex (`looks_like_correction`) against every new user message; a hit logs the prior user question + prior assistant reply + the correction itself to `output/evolution/feedback_log.json`. Deliberately keyword-only (no LLM call, no added latency) and deliberately over-inclusive — false positives just sit in the log for a human to dismiss, they never trigger any automatic code change. `python app.py evolution {feedback-list,feedback-dismiss}` reviews it; unlike `error_log`, there's no `generate_fix_proposals()`-equivalent for this yet (no traceback means no reliable file to anchor a diff to), so it's read-only review for now.

## Known gotchas (found the hard way tonight — don't rediscover these)

- **PID-based process checks only, never `pgrep -f "python ..."`.** On this Mac, a venv's Python resolves through `/Library/Frameworks/Python.framework/.../MacOS/Python` — capitalized `Python`, not `python`. A lowercase pattern silently matches nothing and a wait-loop exits instantly, falsely reporting "done." Capture `$!` at launch and poll with `kill -0 $PID`.
- **Background schedulers must run in a thread, not inline in `__main__`.** `maybe_run_daily_sleep()`/`maybe_run_daily_archive_crawl()` can take minutes (network + LLM calls). Calling them synchronously before `demo.queue().launch()` blocks the whole Gradio server from ever binding to its port. Always `threading.Thread(target=..., daemon=True).start()`.
- **Gradio 6.x history can hand you `content` as a list-of-parts** (`[{"type": "text", "text": "..."}]`) instead of a plain string, which crashes Ollama's `Message` Pydantic validation. `_normalize_history()` in `shisui_chat.py` exists specifically for this — don't bypass it.
- **`theme=`/`css=` go on `demo.queue().launch(...)`, not `gr.Blocks(...)`** in this Gradio version. Getting this backwards produces a UserWarning, not an error, so it's easy to miss.
- **chromadb's `EmbeddingFunction` must be a real subclass**, not duck-typed — and `name()` must stay a `@staticmethod` with no dynamic per-instance data (chromadb calls it unbound during collection-config serialization). Dynamic info (e.g. model name) goes in `get_config()`/`build_from_config()` instead. See `src/common/embeddings.py`.
- **Qwen3's actual lineup is 0.6b/1.7b/4b/8b/14b/30b/32b/235b** — there is no `1.5b` or `7b` tag (that's Qwen2.5's lineup). `ollama pull qwen3:1.5b` fails with a manifest error, not a helpful "did you mean" message.
- **`Settings` is a frozen dataclass.** You can't `monkeypatch.setattr(settings, "field", ...)` in tests — it raises `FrozenInstanceError`. Swap the whole `settings` object reference in the *consuming* module instead (see `tests/test_model_router.py`'s `_fake_settings()` pattern), or monkeypatch the module-level path/constant directly (see how every other test isolates `HIPPOCAMPUS_DB_PATH`, `LITERARY_CHROMA_DIR`, etc.).
- **This Next.js version may differ from your training data.** `frontend/AGENTS.md` (auto-generated by `create-next-app`) explicitly says to check `frontend/node_modules/next/dist/docs/` before assuming App Router conventions you already know still apply.

## Testing conventions

Every test mocks the network/LLM boundary and nothing else — no test in this repo talks to a real Ollama server, Gemini, or aozora.gr.jp. The universal pattern: a `FakeLLM`/`FakeMentor` class with a `.chat()`/`.ask()` method matching the real client's signature, `monkeypatch.setattr(ollama, "embeddings", <deterministic hash-based fake>)` for anything touching ChromaDB, and `monkeypatch.setattr(some_module, "SOME_PATH_CONSTANT", tmp_path / "...")` for storage isolation. Follow this shape for new tests rather than inventing a new mocking style.

## Safety boundaries (established with the user, don't cross without asking)

- Never flip `AUTO_APPROVE`-style flags that let self-modifying code (`src/core/evolution.py`, currently a stub) apply changes without human review. The agreed design: propose + sandbox-test automatically, but a human approves before anything lands on real files.
- Don't run `launchctl load` on the plists in `scripts/` (they're pre-written and correct; activating them as persistent system services needs the user present).
- Don't install new system-level toolchains (Homebrew, etc.) or run `sudo`-requiring installers non-interactively — they'll hang waiting for a password that can't be supplied here. Tell the user to run it themselves via `!<command>`.
