"""Gemini web adapter. Selectors live here; when Gemini changes its DOM, fix them here only."""
import re
from pathlib import Path

from . import ProviderError, wait_reply

URL = "https://gemini.google.com/app?hl=en"
BOX = 'rich-textarea .ql-editor, div[role="textbox"]'
RESP = "model-response"
STOP = 'button[aria-label*="Stop" i], button.stop'
QUOTA_RE = re.compile(r"reached (your|the) .{0,40}limit|try again (later|tomorrow)|quota", re.I)


async def _open(page):
    await page.goto(URL, wait_until="domcontentloaded")
    try:
        await page.locator(BOX).first.wait_for(timeout=20_000)
    except Exception:
        if await page.get_by_role("link", name="Sign in").count():
            raise ProviderError("NOT_LOGGED_IN", "run: call the `login` tool with provider=gemini")
        raise ProviderError("SELECTOR_CHANGED", "prompt box not found")


async def is_logged_in(page) -> bool:
    await _open(page)  # raises NOT_LOGGED_IN / SELECTOR_CHANGED
    return await page.get_by_role("link", name="Sign in").count() == 0


async def _state(page):
    last = page.locator(RESP).last
    body = last.locator("message-content")  # skips the "Gemini said" heading
    text = await (body.first if await body.count() else last).inner_text()
    return (text, await last.locator("img").count())


async def _send_and_wait(page, prompt: str, timeout: float):
    await _open(page)
    if await page.get_by_role("link", name="Sign in").count():
        raise ProviderError("NOT_LOGGED_IN", "run: call the `login` tool with provider=gemini")
    before = await page.locator(RESP).count()
    await page.locator(BOX).first.click()
    await page.keyboard.insert_text(prompt)  # insert_text: newlines don't submit
    await page.keyboard.press("Enter")

    return await wait_reply(page, RESP, STOP, lambda: _state(page), before, timeout, QUOTA_RE)


async def ask(page, prompt: str, timeout: float = 120) -> str:
    return await _send_and_wait(page, prompt, timeout)


async def generate_image(page, prompt: str, dest, timeout: float = 180) -> str:
    text = await _send_and_wait(page, "Create an image: " + prompt, timeout)
    btn = page.locator(RESP).last.get_by_role("button", name="Download full size image")
    if not await btn.count():
        raise ProviderError("NO_RESPONSE", f"no image in reply: {text[:200]}")
    async with page.expect_download(timeout=60_000) as dl:
        await btn.first.click()
    d = await dl.value
    dest = dest.with_suffix(Path(d.suggested_filename).suffix or ".png")
    await d.save_as(dest)
    return str(dest)
