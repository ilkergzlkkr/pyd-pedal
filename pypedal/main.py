import logging
import logging.config
import sys
import colorama
import colouredlogs
import dotenv
import os
import yaml
import uvicorn

from pypedal.pedal import options
from pypedal.server import app
from pypedal.server.models import ProductionConfig

uvicorn_log = logging.getLogger("uvicorn")
try:
    uvicorn_log.handlers[0]
except IndexError:
    pass

dotenv.load_dotenv()
colorama.init()
colouredlogs.install()


@app.on_event("startup")
async def setup():
    config = app.extra["config"] = ProductionConfig()
    uvicorn_log.info(f"started app with {config.PRODUCTION_ENV=}")
    options.__init__(os.getenv("TEMP_DIR", ""))
    with open("logging.yml", "rt") as f:
        config = yaml.safe_load(f.read())

    os.makedirs("logs", exist_ok=True)
    logging.config.dictConfig(config)


if __name__ == "__main__":
    uvicorn.run("pypedal.main:app", host="0.0.0.0", port=int(os.getenv("PORT") or 8000))
