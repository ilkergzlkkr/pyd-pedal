import logging
import logging.config
import sys
import colorama
import colouredlogs
import dotenv
import os
import yaml

from .pedal import options
from .server import app

uvicorn_log = logging.getLogger("uvicorn")
del uvicorn_log.handlers[0]

dotenv.load_dotenv()
colorama.init()
colouredlogs.install(stream=sys.stdout, reconfigure=False)


@app.on_event("startup")
async def setup():
    options.__init__()
    with open("logging.yml", "rt") as f:
        config = yaml.safe_load(f.read())

    os.makedirs("logs", exist_ok=True)
    logging.config.dictConfig(config)
