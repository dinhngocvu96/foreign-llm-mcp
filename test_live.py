"""Live smoke tests (need `python server.py --login` done once). Run: python test_live.py"""
import asyncio
import re
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from providers import chatgpt, gemini

PROVIDERS = ("gemini", "chatgpt")


def txt(r):
    return r.content[0].text


async def via_mcp():
    p = StdioServerParameters(command="python", args=["server.py"])
    async with stdio_client(p) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        call = s.call_tool

        res = await call("list_providers", {})
        print("list_providers:", " ".join(txt(res).split()))
        assert not res.is_error and txt(res).lower().count("true") == len(PROVIDERS)

        res = await call("ask", {"prompt": "hi", "provider": "nope"})
        assert res.is_error and "unknown provider" in txt(res); print("unknown provider: ok")

        for pv in PROVIDERS:
            res = await call("ask", {"prompt": "Write a 500 word story", "timeout": 1, "provider": pv})
            assert res.is_error and "TIMEOUT" in txt(res), txt(res); print(pv, "TIMEOUT: ok")

            res = await call("ask", {"prompt": "Line one\nLine two\nReply with only the word: MULTI", "provider": pv})
            assert not res.is_error and "MULTI" in txt(res), txt(res); print(pv, "multiline: ok")

            t = time.monotonic()
            a, b = await asyncio.gather(
                call("ask", {"prompt": "Reply with only: A1", "provider": pv}),
                call("ask", {"prompt": "Reply with only: B2", "provider": pv}))
            assert "A1" in txt(a) and "B2" in txt(b), (txt(a), txt(b))
            print(f"{pv} concurrent (serialized): ok in {time.monotonic() - t:.0f}s")

            res = await call("generate_image", {"prompt": "a small green circle on white", "provider": pv})
            if res.is_error and "QUOTA" in txt(res):  # free image limit is tiny; the error path is the pass
                print(pv, "generate_image: QUOTA reported correctly:", txt(res)[:90])
                continue
            assert not res.is_error and Path(txt(res)).stat().st_size > 10_000, txt(res)
            print(pv, "generate_image: ok", txt(res))


async def relaunch():
    import server
    assert "ok" in (await server._run("gemini", lambda m, p: _ask(m, p)))
    await server._ctx.close()  # simulate user closing the browser window
    assert "ok" in (await server._run("gemini", lambda m, p: _ask(m, p)))
    print("browser relaunch after close: ok")
    await server._ctx.close()


async def _ask(m, p):
    return await m.ask(p, "Reply with only: ok")


def quota_regex():
    for s in ("You've reached your limit for today", "Please try again later", "quota exceeded"):
        assert gemini.QUOTA_RE.search(s), s
    assert not gemini.QUOTA_RE.search("PONG")
    assert chatgpt.QUOTA_RE.search("You've reached your daily limit") and not chatgpt.QUOTA_RE.search("PONG")
    print("QUOTA regex: ok")


if __name__ == "__main__":
    quota_regex()
    asyncio.run(via_mcp())
    asyncio.run(relaunch())
    print("ALL PASSED")
