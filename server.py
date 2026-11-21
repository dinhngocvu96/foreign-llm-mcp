"""MCP server: drive free LLM web UIs (Gemini, ChatGPT) through a persistent Chrome profile.
Log in once with the `login` tool. Data (browser profile, images) lives in ~/.foreign-llm-mcp.
"""
import asyncio
import os
import time
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from playwright.async_api import async_playwright

from providers import ProviderError, chatgpt, gemini

HOME = Path(os.environ.get("FOREIGN_LLM_HOME", Path.home() / ".foreign-llm-mcp"))
PROVIDERS = {"gemini": gemini, "chatgpt": chatgpt}
MIN_GAP = 5  # seconds between calls, be gentle with the accounts
mcp = MCPServer("foreign-llm")
_lock = asyncio.Lock()  # ponytail: one browser, serial calls; per-provider pages if throughput matters
_ctx = None
_last = 0.0


async def _context():
    global _ctx
    if _ctx is None:
        pw = await async_playwright().start()
        _ctx = await pw.chromium.launch_persistent_context(
            HOME / "profile", channel="chrome", headless=False, viewport=None,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
    return _ctx


async def _run(provider: str, fn):
    """fn(module, page) -> result. Serial, rate-limited, always closes its tab."""
    global _ctx, _last
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}; have {list(PROVIDERS)}")
    async with _lock:
        await asyncio.sleep(max(0, MIN_GAP - (time.monotonic() - _last)))
        try:
            page = await (await _context()).new_page()
        except Exception:  # user closed the browser window -> relaunch once
            _ctx = None
            page = await (await _context()).new_page()
        try:
            return await fn(PROVIDERS[provider], page)
        except ProviderError as e:
            raise RuntimeError(str(e)) from None
        finally:
            _last = time.monotonic()
            await page.close()


@mcp.tool()
async def ask(prompt: str, provider: str = "gemini", timeout: int = 120) -> str:
    """One-shot question to a free web LLM (new chat each call). Good for summarize/translate/
    small code/second opinion/web lookup. Returns the reply text."""
    return await _run(provider, lambda m, p: m.ask(p, prompt, timeout))


@mcp.tool()
async def generate_image(prompt: str, provider: str = "gemini", timeout: int = 180) -> str:
    """Generate an image on the web LLM; returns the saved file path under ./out/."""
    out = HOME / "out"
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{provider}-{int(time.time())}.png"
    return await _run(provider, lambda m, p: m.generate_image(p, prompt, dest, timeout))


@mcp.tool()
async def list_providers() -> dict:
    """Providers and whether each is logged in (error code if not)."""
    res = {}
    for name in PROVIDERS:
        try:
            res[name] = await _run(name, lambda m, p: m.is_logged_in(p))
        except RuntimeError as e:
            res[name] = str(e)
    return res


async def _wait_close(_module, page):
    await page.goto(_module.URL)
    await page.wait_for_event("close", timeout=0)


@mcp.tool()
async def login(provider: str = "gemini") -> str:
    """Open the provider's site in the browser so the user can sign in. Blocks until the user
    closes that tab (ask the user to do so when finished), then use list_providers to verify."""
    await _run(provider, _wait_close)
    return "Tab closed. Call list_providers to confirm the login worked."


if __name__ == "__main__":
    mcp.run()
