# foreign-llm-mcp

A Claude Code plugin (MCP server) that hands simple, one-shot tasks to **free web LLMs** —
Gemini and ChatGPT — by driving their websites in a real Chrome window. Use it to save
Claude tokens on things like summarizing, translating, small code snippets, a second opinion,
web lookups, and image generation.

> **Heads-up.** This automates consumer chat UIs, which may violate their terms of service and
> can break whenever the site changes its markup. Use it for personal use, at low volume, with
> your own accounts. No warranty.

## Tools

| Tool | What it does |
|---|---|
| `ask(prompt, provider="gemini", timeout=120)` | New chat, send prompt, return the reply text. |
| `generate_image(prompt, provider="gemini", timeout=180)` | Generate an image, return the saved file path. |
| `list_providers()` | Which providers are logged in. |
| `login(provider)` | Open the site so you can sign in; returns when you close that tab. |

Providers: `gemini`, `chatgpt`. Every call is a fresh one-shot chat (no history carried over),
calls are serialized, with a 5 s gap between them.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- [uv](https://docs.astral.sh/uv/) (installs the Python dependencies on first run)
- Google Chrome (Playwright drives the installed Chrome, not a bundled browser)

## Install

```
/plugin marketplace add dinhngocvu96/foreign-llm-mcp
/plugin install foreign-llm@foreign-llm-mcp
```

Restart Claude Code, then ask Claude to call the `login` tool for each provider you want
(`login(provider="gemini")`), sign in in the window that opens, and close the tab.
Sessions persist in the browser profile.

## Where data lives

`~/.foreign-llm-mcp/` (override with the `FOREIGN_LLM_HOME` env var):

- `profile/` — Chrome profile with your logged-in sessions. **Keep it private.**
- `out/` — generated images.

## Errors

Tools fail with a code Claude can act on: `NOT_LOGGED_IN`, `QUOTA`, `TIMEOUT`,
`NO_RESPONSE`, `SELECTOR_CHANGED`.

## Notes per provider

- **Gemini** — image generation downloads the full-size file.
- **ChatGPT** — `ask` uses a temporary chat (nothing saved). Image generation is blocked in
  temporary chats, so `generate_image` uses a normal chat that stays in your history. Free-plan
  image quota is small.

## Development

Selectors live at the top of each `providers/<name>.py`; when a site changes, fix them there.
To add a provider, create a module exposing `URL`, `ask`, `generate_image`, `is_logged_in` and
register it in `PROVIDERS` in `server.py`.

Live smoke test (needs logins, uses real quota): `uv run python test_live.py`

## License

MIT
