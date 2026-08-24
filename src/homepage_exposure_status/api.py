import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from homepage_exposure_status.checks import run_checks, close_all, clear_cache

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_all()

app = FastAPI(lifespan=lifespan)

@app.get("/check")
async def check(url: str):
    logger.info("Checking host: %s", url)
    result = await run_checks(url)
    logger.info("Check result: %s", result)
    # Stringified rather than real JSON booleans: Docker labels have no
    # boolean type, homepage.widget.mappings[0].remap[0].value=true always
    # sets a string, and a string never matches a real boolean in Homepage's
    # remap comparison. Keeping the response type consistent (always a
    # string) makes it work the same way in both services.yaml and labels.
    stringified = {name: str(value).lower() for name, value in result.items()}
    return {"url": url, **stringified}

@app.delete("/cache")
async def cache(url: str | None = None):
    cleared = clear_cache(url)
    logger.info("Cleared %d cached entries%s", cleared, f" for {url}" if url else "")
    return {"cleared": cleared}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)