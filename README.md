# ⚡ ProxAI

**API key proxy gateway for AI providers — keep your keys out of your AI agent's reach.**

ProxAI sits between your AI client (like OpenClaw) and AI API providers. Your client uses a dummy key; ProxAI injects the real key from a secure `.env` file. Your API keys never appear in config files your agent can read.

```
OpenClaw / any client  →  ProxAI (injects key)  →  Anthropic / OpenAI / DeepSeek / NVIDIA
        apiKey: "proxied"              ↑
                              real key lives here only
```

---

## Why ProxAI?

When you run an AI agent (like OpenClaw), the agent needs API keys to call LLM providers. Normally these keys sit in a config file the agent can read — meaning a jailbreak or prompt injection attack could expose them.

ProxAI breaks that chain:
- ✅ Agent config has `apiKey: "proxied"` — useless to an attacker
- ✅ Real keys live in `.env` — owned by root, never read by the agent
- ✅ Full streaming support — works transparently with all models
- ✅ Request logging and cost tracking built in
- ✅ Web dashboard to monitor usage

---

## Quick Start (Docker)

```bash
git clone https://github.com/HuyNguyenUTA/proxai
cd proxai
cp .env.example .env
# Edit .env with your real API keys
nano .env

docker-compose up -d
```

Proxy runs on `http://localhost:8090`
Dashboard at `http://localhost:8091`

---

## Installation (pip)

```bash
pip install proxai

# Create config
cp .env.example .env
nano .env

# Start
proxai start

# Or run in background
proxai start --daemon
```

## Running from source

```bash
git clone https://github.com/HuyNguyenUTA/proxai
cd proxai

# Requires Python 3.10+
python3.10 -m pip install -e .

# Create config and fill in your real API keys
cp .env.example .env
nano .env

# Start (foreground)
python3.10 -m proxai.cli start

# Or start in background
python3.10 -m proxai.cli start --daemon

# Check status / stop
python3.10 -m proxai.cli status
python3.10 -m proxai.cli stop
```

### CLI Commands

```bash
proxai start              # Start proxy (foreground)
proxai start --daemon     # Start in background
proxai stop               # Stop background server
proxai status             # Check if running
proxai logs --tail 100    # View recent logs
proxai stats              # Show usage statistics
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your keys:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXAI_HOST` | `127.0.0.1` | Bind address (`0.0.0.0` for Docker) |
| `PROXAI_PORT` | `8090` | Proxy port |
| `PROXAI_LOG_LEVEL` | `INFO` | Log level |
| `PROXAI_RATE_LIMIT_RPM` | `60` | Max requests/min per provider |
| `PROXAI_DASHBOARD_ENABLED` | `true` | Enable web dashboard |
| `PROXAI_DASHBOARD_PORT` | `8091` | Dashboard port |
| `ANTHROPIC_API_KEY` | — | Your Anthropic API key |
| `OPENAI_API_KEY` | — | Your OpenAI API key |
| `DEEPSEEK_API_KEY` | — | Your DeepSeek API key |
| `NVIDIA_API_KEY` | — | Your NVIDIA NIM API key |

---

## Supported Providers

| Provider | Route | Upstream |
|----------|-------|----------|
| Anthropic | `/anthropic/*` | `api.anthropic.com` |
| OpenAI | `/openai/*` | `api.openai.com/v1` |
| DeepSeek | `/deepseek/*` | `api.deepseek.com/v1` |
| NVIDIA NIM | `/nvidia/*` | `integrate.api.nvidia.com/v1` |

---

## OpenClaw Integration

Update your `openclaw.json` to point at ProxAI instead of the real providers:

```json
{
  "providers": {
    "anthropic": {
      "baseUrl": "http://127.0.0.1:8090/anthropic",
      "apiKey": "proxied"
    },
    "openai": {
      "baseUrl": "http://127.0.0.1:8090/openai",
      "apiKey": "proxied"
    },
    "deepseek": {
      "baseUrl": "http://127.0.0.1:8090/deepseek",
      "apiKey": "proxied",
      "api": "openai-completions"
    }
  }
}
```

Your real keys stay in `.env` — root-owned, never touched by the agent.

---

## Dashboard

Visit `http://localhost:8091` to see:

- 📊 Requests and token usage by provider
- 💰 Cost estimates (based on known model pricing)
- 🟢 Provider health status (key configured or not)
- 📋 Recent request log with latency and status

---

## Health Check

```bash
curl http://localhost:8090/health
# {"status":"ok","providers":{"anthropic":true,"openai":false,"deepseek":true,"nvidia":false}}
```

---

## Security Model

```
Attack surface BEFORE ProxAI:
  openclaw.json → apiKey: "sk-ant-real-key"  ← agent can read this

Attack surface WITH ProxAI:
  openclaw.json → apiKey: "proxied"          ← useless
  .env          → ANTHROPIC_API_KEY=sk-...   ← root-owned, agent has no access
```

Even if an attacker gains control of the AI agent, they cannot extract real API keys because the agent never has them.

---

## Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE)
