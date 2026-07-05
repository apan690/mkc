# DevMesh — How to Run the Full Skeleton (Pre-Orientation)

> Covers all three pieces together: Hardik's LLM review pipeline, Vatsal's
> mobile app + WebSocket server, and Dhruv's git hook / webhook listener /
> setup script. If you only need one piece in isolation, see the
> per-component notes inline below — but running the whole thing together
> is the actual demo, so that's what this doc walks through.
>
> Status as of July 5, 2026: all three pieces individually verified
> end-to-end on real hardware. This is the first pass at combining them
> into one script-by-script walkthrough. Update after orientation (July 6)
> once hardware/AI Hub specifics are confirmed — see Section 13 of the
> knowledge file.

---

## 0. What you're setting up

```
git commit  ──┐
              ├──> diff extracted ──> LLM review (per hunk) ──> findings ──┬──> WebSocket ──> Mobile app
GitHub PR ────┘                                                            └──> devmesh_report.txt
(webhook)
```

Two trigger paths feed the same pipeline:
- **Local commit** → `hooks/post-commit` → `backend/run_review.py`
- **Simulated/real PR** → `backend/webhook_server.py` (`POST /webhook`)

Both paths broadcast findings over the same WebSocket (`ws://<your-ip>:8765`) that the mobile app listens on, and both write the same plain-text report to `backend/devmesh_report.txt`.

---

## 1. Prerequisites (install once)

| Tool | Why | Check it's installed |
|---|---|---|
| Python 3.10+ | Backend pipeline, webhook listener | `python3 --version` |
| [Ollama](https://ollama.com) | Local LLM (Phi-3 Mini) for now — swapped for Qualcomm AI Hub post-orientation | `ollama --version` |
| Node.js + npm | Mobile app (Expo/React Native) | `node --version` |
| Expo Go app | Run the mobile app on your actual phone | Install from App Store / Play Store |
| Git | Obviously | `git --version` |

Pull the model once:
```bash
ollama pull phi3
```

---

## 2. Get the repo and install dependencies

```bash
git clone <repo-url> devmesh
cd devmesh
```

**Backend:**
```bash
cd backend
pip install -r requirements.txt
```
(If you hit `externally-managed-environment` on Linux/some Mac setups: `pip install -r requirements.txt --break-system-packages`, or use a virtualenv.)

**Mobile:**
```bash
cd ../mobile
npm install
```

---

## 3. The one-command path (recommended)

From the repo root:
```bash
chmod +x setup.sh    # first time only
./setup.sh
```

This does three things:
1. Installs backend Python deps (non-fatal if it fails — see terminal output, you may need `--break-system-packages` or a venv; the script continues to the hook install either way)
2. Installs `hooks/post-commit` into `.git/hooks/post-commit` and makes it executable
3. Starts the FastAPI webhook listener in the background on port **8000** (logs: `/tmp/devmesh_webhook.log`)

You'll see:
```
Next steps:
  - Make a commit ... to trigger a review automatically via the post-commit hook.
  - Or simulate a GitHub PR event: curl -X POST http://localhost:8000/webhook ...
  - Check webhook listener health: curl http://localhost:8000/health
```

Safe to re-run `./setup.sh` anytime — it won't double-start the webhook listener (checks `/health` first) and re-installing the hook is harmless.

**Note:** `setup.sh` does *not* separately start the WebSocket broadcaster. It doesn't need to — `ws_broadcaster.py` starts its server (`ws://0.0.0.0:8765`) automatically the moment it's imported, which happens as soon as either a commit triggers `run_review.py` or the webhook listener handles a request.

---

## 4. Start the mobile app

In a separate terminal:
```bash
cd mobile
npx expo start
```
Scan the QR code with Expo Go on your phone. **Phone and laptop must be on the same WiFi**, and your laptop's LAN IP must be set correctly in `mobile/App.js`:
```js
const SERVER_IP = "192.168.x.x";  // <-- your laptop's LAN IP, not the phone's
```
Find your laptop's IP with `ipconfig` (Windows) or `ifconfig` / `ip addr` (Mac/Linux). If the app shows "Waiting for AI PC" indefinitely, this is the first thing to check — a typo'd IP was the actual root cause of a real connection failure during Vatsal's testing (Section 16 of the knowledge file), not a firewall issue.

The app will show a **"Waiting for AI PC"** status with a live retry counter until a review actually runs. There's a **"Show Demo Data"** button for offline UI demoing — it's clearly banner-labeled as sample data and force-clears the moment real findings arrive, so it can't be mistaken for a live result.

---

## 5. Trigger a review — three ways

### A. Automatic: make a real commit
```bash
git add samples/buggy_auth.py
git commit -m "test commit"
```
The hook fires in the background — `git commit` returns immediately, you don't wait for the LLM. Check `/tmp/devmesh_post_commit.log` if you want to see what happened without watching the mobile app.

### B. Simulate a GitHub PR via the webhook
```bash
curl -X POST http://localhost:8000/webhook \
  -H "X-GitHub-Event: pull_request" \
  -H "Content-Type: application/json" \
  -d '{"action": "opened", "pull_request": {"number": 1}}'
```
**Current scope note:** real GitHub PR diff fetching isn't built yet — this reviews the local repo's last commit as a stand-in, same diff source as path A. Swap in real PR-diff fetching post-orientation once that's prioritized.

### C. Manual, for debugging one component at a time
```bash
cd backend
python run_review.py              # reviews last commit
python run_review.py --staged     # reviews staged changes instead
python run_review.py --repo /path/to/other/repo
```

All three paths converge on the same output:
- Findings pushed over the WebSocket to any connected mobile client
- `backend/devmesh_report.txt` written/overwritten

---

## 6. Verify each piece independently (if something's not working)

| Check | Command | Expect |
|---|---|---|
| Ollama is running | `ollama list` | Lists pulled models, no connection error |
| Webhook listener is up | `curl http://localhost:8000/health` | `{"status":"ok",...}` |
| Backend parses without Ollama | `python response_parser.py` (in `backend/`) | Prints 3 `Finding(...)` objects |
| Full pipeline without a real LLM | `DEVMESH_MOCK_LLM=1 python run_review.py` | Runs instantly with canned findings — use this to test mobile/webhook/report wiring without waiting on Ollama |
| Mobile app reachable | Phone shows "Live" status after a review runs | If stuck on "Waiting", check `SERVER_IP` and that both devices share WiFi |

`DEVMESH_MOCK_LLM=1` is genuinely useful beyond debugging — keep it in your back pocket any time you want to test report/WebSocket/webhook changes without burning time on real inference.

---

## 7. Try all three sample bugs

```bash
git add samples/buggy_auth.py    && git commit -m "sql injection sample"
git add samples/buggy_api.js     && git commit -m "unhandled promise sample"
git add samples/buggy_models.py  && git commit -m "n+1 query sample"
```
Each commit triggers its own review; check the phone or `backend/devmesh_report.txt` after each.

---

## 8. Known limitations right now (don't be surprised by these)

- **Report is plain text**, not the real Jinja2/PDF version yet (Vatsal's next task).
- **Approve/Dismiss in the mobile app is UI-only** — nothing is sent back to the AI PC yet.
- **WebSocket server dies when the triggering process exits.** If you ran a review via `python run_review.py` directly (not through the webhook listener), it stays alive on a keep-alive prompt (`input()`) until you press Enter — close it and the phone will show "Waiting" again until the next review. The webhook listener path doesn't have this issue since it stays running as a server.
- **No message backlog** — a mobile client that connects *after* a review already ran will simply miss those findings. Connect the phone first, then trigger the review.
- **Real GitHub PR payload parsing isn't built** — webhook path B above uses your local repo's last commit as a stand-in (see Section 5B note).
- **Venue WiFi is untested** — this all depends on phone and laptop sharing a network with no AP/client isolation. Test venue WiFi early on July 11; have a personal hotspot as fallback.
- **Model occasionally hallucinates a finding** (e.g. flagging `sqlite3.connect()` as "deprecated"). Not a pipeline bug — known quantized-model limitation, worth acknowledging honestly if a judge asks rather than claiming 100% accuracy.

---

## 9. Quick troubleshooting table

| Symptom | Likely cause |
|---|---|
| `Could not reach Ollama at http://localhost:11434` | `ollama serve` isn't running — start it in another terminal |
| `git diff failed` | Not inside a git repo, or no commit exists yet |
| Model output has no `[SEVERITY]` lines | Model ignored the format — save raw output, iterate on the prompt |
| Very slow (30s+ per hunk) | Normal on CPU-only laptops — log the number for the benchmark harness, it's the "why NPU matters" pitch data |
| Phone stuck on "Waiting for AI PC" | Check `SERVER_IP` in `mobile/App.js`, confirm same WiFi, check for AP isolation |
| `externally-managed-environment` on pip install | Use `--break-system-packages` or a virtualenv; `setup.sh` continues past this automatically |
| Webhook `/health` doesn't respond | Listener didn't start — check `/tmp/devmesh_webhook.log` |
| `curl .../webhook` returns 400 | Missing `X-GitHub-Event: pull_request` header and no `pull_request` key in the JSON body |

---

*This doc reflects the pre-orientation skeleton (July 5, 2026). Update after July 6 orientation once hardware, AI Hub setup, and network specifics are confirmed — see Section 13 of the project knowledge file.*
