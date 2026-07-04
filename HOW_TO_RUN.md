# How to Run the DevMesh Skeleton — Step by Step

This walks through getting the pipeline running on your machine and testing
it against the sample buggy files. Do this before orientation so we know the
Phi-3 Mini + prompt format loop actually works.

---

## Step 1 — Install Ollama

1. Go to https://ollama.com and download the installer for your OS (Windows/Mac/Linux).
2. Install it like any normal app.
3. Confirm it installed correctly by opening a terminal and running:
   ```bash
   ollama --version
   ```
   You should see a version number, not an error.

## Step 2 — Pull the Phi-3 Mini model

```bash
ollama pull phi3
```

This downloads the model (a few GB — do this on decent wifi, it'll take a
few minutes). You only need to do this once.

## Step 3 — Start the Ollama server

Usually Ollama auto-starts a background server after install. To check, run:

```bash
ollama list
```

If that works without error, the server is running. If you get a connection
error, start it manually in its own terminal window (leave it running):

```bash
ollama serve
```

## Step 4 — Get the DevMesh folder onto your machine

1. Download the files I gave you.
2. Unzip them so you end up with a `devmesh/` folder somewhere on your machine, e.g.:
   ```
   C:\Users\you\projects\devmesh\        (Windows)
   ~/projects/devmesh/                    (Mac/Linux)
   ```

## Step 5 — Install Python dependencies

Open a terminal, navigate into the `backend` folder, and run:

```bash
cd devmesh/backend
pip install -r requirements.txt
```

(If you have both Python 2 and 3 on your system, use `pip3` instead of `pip`.)

## Step 6 — Quick sanity checks (no LLM needed yet)

These confirm the non-LLM parts work before you involve Ollama at all.

```bash
python response_parser.py
```
Expected: prints 3 `Finding(...)` objects to the console.

```bash
python prompt_builder.py
```
Expected: prints the full prompt template with a fake SQL injection line
filled in.

If either of these errors out, something's wrong with the Python setup
itself (wrong Python version, missing file) — fix that before moving on.

## Step 7 — Test the LLM connection directly

```bash
python llm_client.py
```

Expected: after a short pause (Phi-3 "thinking"), it prints a latency number
and the model's raw text output, which should look roughly like:
```
[CRITICAL] auth.py:LINE — SQL injection... Fix: ...
```

**If you get a connection error here:** Ollama isn't running — go back to
Step 3 and run `ollama serve` in another terminal window, then try again.

**If the model's output looks messy / doesn't follow the format:** that's
useful information, not a failure — tell me exactly what it printed and
we'll iterate on the prompt wording in `prompt_builder.py`.

## Step 8 — Run the full pipeline against a real git commit

The pipeline reads from an actual git repository, so we need one with at
least one commit containing a bug.

```bash
# from inside the devmesh folder
git init
git add samples/buggy_auth.py
git commit -m "add buggy auth sample"
```

Now run the orchestrator:

```bash
cd backend
python run_review.py
```

Expected output, roughly:
```
[run_review] Extracting diff from: .
[run_review] Found 1 hunk(s) to review

[run_review] Reviewing hunk 1/1: auth.py (line X)
    -> N finding(s), X.XXs

[run_review] Total LLM latency: X.XXs across 1 call(s)
[run_review] Average per hunk: X.XXs

[ws_broadcaster STUB] Would send to mobile app:
{ ... JSON printout of findings ... }

[run_review] Report written to: /full/path/to/devmesh_report.txt
```

Open `devmesh_report.txt` (it'll be created in the `backend` folder) and
check it lists the SQL injection finding.

## Step 9 — Try the other two sample bugs

Repeat Step 8's git commands for the other samples to see how the model
handles different bug types:

```bash
git add samples/buggy_api.js
git commit -m "add buggy api sample"
python run_review.py
```

```bash
git add samples/buggy_models.py
git commit -m "add buggy models sample"
python run_review.py
```

## Step 10 — Report back

Whatever you see — clean output, garbled output, wrong severity, missed
bugs, crashes — bring it back here. That's exactly the feedback loop we
need before orientation: confirm the Phi-3 + prompt format combo is usable,
or figure out it needs tuning (or a different model) before July 6.

---

### Common issues

| Symptom | Likely cause |
|---|---|
| `Could not reach Ollama at http://localhost:11434` | `ollama serve` isn't running — start it in another terminal |
| `git diff failed` | You're not inside a git repo, or haven't made a commit yet |
| Model output has no `[SEVERITY]` lines at all | Model ignored the format — save the raw output and share it, we'll adjust the prompt |
| Very slow (30s+ per hunk) | Normal for small hunks on a CPU-only laptop; make a note of the number for the benchmark harness — this is exactly why the NPU matters for the pitch |
