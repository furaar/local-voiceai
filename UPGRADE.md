# Upgrading to GUI / Web

The same bot and pipeline work for CLI and web; only the transport and client change.

## Steps

1. **Transport swap**  
   Keep the same `run_bot(transport)` and pipeline. For web, use the development runner with a network transport instead of local:
   - **Web (same machine or LAN)**: Run `python bot.py -t webrtc`. The runner serves the built-in client at http://localhost:7860/client. No code change; the `bot(runner_args)` entrypoint already uses `create_transport` with webrtc params.
   - **Production / hosted**: Run `python bot.py -t daily`. Set `DAILY_API_KEY` and use Pipecat client SDK or Daily’s web client to connect.

2. **Runner**  
   No code change. Use the same runner with `-t webrtc` or `-t daily`. The `bot()` function in `bot.py` already supports both via `create_transport(runner_args, transport_params)`.

3. **Custom GUI**  
   Build a web or desktop app that uses Pipecat’s client SDK (e.g. `@pipecat-ai/client-js`) and your runner’s endpoint:
   - For Daily: POST to `/start` to get room/token, then connect with the client SDK.
   - For WebRTC: use the runner’s WebRTC endpoint (e.g. POST to `/api/offer` with SDP).
   Connect with mic/speaker in the client; the server pipeline stays the same.

4. **Pipecat Cloud (optional)**  
   Add `pcc-deploy.toml` and a Dockerfile later to deploy the same bot to Pipecat Cloud. The bot code is already compatible with the runner pattern used there.

## Summary

| Mode    | Command                  | Client / access                          |
|---------|--------------------------|------------------------------------------|
| CLI     | `python bot.py --local`  | Mic and speaker on this machine          |
| Web     | `python bot.py -t webrtc` | Browser at http://localhost:7860/client |
| Daily   | `python bot.py -t daily` | Pipecat client SDK or Daily web client   |

Pipeline (Silero VAD, smart-turn, Whisper, LM Studio, Piper/XTTS) is unchanged; only the transport and how the user connects change.
