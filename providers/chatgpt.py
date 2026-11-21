"""ChatGPT web adapter. Selectors live here; when chatgpt.com changes its DOM, fix them here only."""
import base64
import re
import time

from . import ProviderError, wait_reply

URL = "https://chatgpt.com/?temporary-chat=true"  # temporary chat: nothing saved to history
BOX = '#prompt-textarea, div[contenteditable="true"][role="textbox"]'
# new "dil" renderer first, old markup as fallback
RESP = '[data-dil-response], [data-message-author-role="assistant"]'
STOP = 'button[aria-label="Stop"], button[aria-label="Stop streaming"], button[data-testid="stop-button"]'
LOGIN = 'a:has-text("Log in"), button:has-text("Log in")'
QUOTA_RE = re.compile(r"reached (your|the) .{0,40}limit|hit (your|the) .{0,30}limit|try again (later|in)|come back (later|after)", re.I)


async def _open(page, url=URL):
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.locator(BOX).first.wait_for(timeout=25_000)
    except Exception:
        if await page.locator(LOGIN).count() or "auth" in page.url:
            raise ProviderError("NOT_LOGGED_IN", "run: call the `login` tool with provider=chatgpt")
        raise ProviderError("SELECTOR_CHANGED", "prompt box not found")
    if await page.locator(LOGIN).count():  # guest mode still shows a box
        raise ProviderError("NOT_LOGGED_IN", "run: call the `login` tool with provider=chatgpt")


async def is_logged_in(page) -> bool:
    await _open(page)
    return True


async def _state(page):
    last = page.locator(RESP).last
    return (await last.inner_text(), await last.locator("img").count())


async def _send(page, prompt: str, url=URL) -> int:
    """Open a fresh chat, send the prompt, return the reply count before sending."""
    await _open(page, url)
    before = await page.locator(RESP).count()
    await page.locator(BOX).first.click()
    await page.keyboard.insert_text(prompt)  # insert_text: newlines don't submit
    await page.keyboard.press("Enter")
    return before


async def _send_and_wait(page, prompt: str, timeout: float):
    before = await _send(page, prompt)
    return await wait_reply(page, RESP, STOP, lambda: _state(page), before, timeout, QUOTA_RE)


async def ask(page, prompt: str, timeout: float = 120) -> str:
    return await _send_and_wait(page, prompt, timeout)


GALLERY = '[data-testid="generated-image-gallery"] img'
# blob: src can't be fetched from outside, so draw it on a canvas (same-origin, not tainted)
TO_PNG = "i => { const c = document.createElement('canvas'); c.width = i.naturalWidth; "          "c.height = i.naturalHeight; c.getContext('2d').drawImage(i, 0, 0); "          "return c.toDataURL('image/png').split(',')[1]; }"


async def generate_image(page, prompt: str, dest, timeout: float = 180) -> str:
    # temporary chat blocks image generation, so use a normal chat (it stays in history)
    before = await _send(page, "Create an image: " + prompt, "https://chatgpt.com/")
    start, text_only = time.monotonic(), 0
    while time.monotonic() - start < timeout:
        await page.wait_for_timeout(1000)
        if await page.locator(STOP).count():
            text_only = 0
        elif await page.locator(GALLERY).count():
            await page.wait_for_timeout(2000)  # let the full-res image settle
            break
        elif await page.locator(RESP).count() > before:  # text reply, no image: refusal / limit
            text_only += 1
            if text_only >= 4:
                text = (await page.locator(RESP).last.inner_text()).strip()
                raise ProviderError("QUOTA" if QUOTA_RE.search(text) else "NO_RESPONSE", text[:300])
    else:
        raise ProviderError("TIMEOUT", f"no image after {timeout}s")
    b64 = await page.locator(GALLERY).first.evaluate(TO_PNG)
    dest.write_bytes(base64.b64decode(b64))
    return str(dest)
