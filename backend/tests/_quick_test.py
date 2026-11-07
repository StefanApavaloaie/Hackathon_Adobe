"""Minimal smoke test to verify complete_json works at all."""
import sys, asyncio, tempfile
from pathlib import Path

sys.path.insert(0, ".")

from pydantic import BaseModel, ConfigDict
from app.config import Settings
from app.services.llm_client import LLMUnavailable, _cache_key, complete_json
import app.services.llm_client as mod

class D(BaseModel):
    model_config = ConfigDict(extra="forbid")
    greeting: str

tmp = Path(tempfile.mkdtemp())
mod.CACHE_DIR = tmp

settings = Settings(_env_file=None, frontend_origin="x", groq_api_key="k", groq_model="m", llm_mode="saved")

# Test 1: no cache → LLMUnavailable
loop = asyncio.new_event_loop()
try:
    loop.run_until_complete(
        complete_json("t", [{"role": "user", "content": "hi"}], D, None, settings=settings)
    )
    print("FAIL test 1")
except LLMUnavailable:
    print("PASS test 1: LLMUnavailable on cache miss")
finally:
    loop.close()

# Test 2: with cache → success
key = _cache_key("m", [{"role": "user", "content": "hi"}], "D")
(tmp / f"{key}.json").write_text('{"greeting": "hello"}', encoding="utf-8")

loop2 = asyncio.new_event_loop()
try:
    result = loop2.run_until_complete(
        complete_json("t", [{"role": "user", "content": "hi"}], D, None, settings=settings)
    )
    print(f"PASS test 2: greeting={result.greeting}")
except Exception as e:
    print(f"FAIL test 2: {e}")
finally:
    loop2.close()

