import time


class ProviderError(Exception):
    """code: NOT_LOGGED_IN | QUOTA | TIMEOUT | NO_RESPONSE | SELECTOR_CHANGED"""

    def __init__(self, code: str, msg: str = ""):
        super().__init__(f"{code}: {msg}" if msg else code)
        self.code = code


async def wait_reply(page, resp, stop, state, before, timeout, quota_re):
    """Wait for a new `resp` element past `before`, then until the stop button is gone and
    state() = (text, n_images) has been stable for 2s. Returns the reply text."""
    start = time.monotonic()
    last, since = None, start
    while time.monotonic() - start < timeout:
        if await page.locator(resp).count() > before:
            cur = await state()
            busy = await page.locator(stop).count() > 0
            if cur != last:
                last, since = cur, time.monotonic()
            elif not busy and (cur[0].strip() or cur[1]) and time.monotonic() - since >= 2:
                if cur[0] and len(cur[0]) < 400 and quota_re.search(cur[0]):
                    raise ProviderError("QUOTA", cur[0].strip())
                return cur[0].strip()
        elif time.monotonic() - start > 45:
            body = (await page.locator("body").inner_text())[:300]
            raise ProviderError("NO_RESPONSE", body)
        await page.wait_for_timeout(500)
    raise ProviderError("TIMEOUT", f"no complete reply after {timeout}s")
