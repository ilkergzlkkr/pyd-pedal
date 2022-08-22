import logging
import sys
import colorama
import colouredlogs
import dotenv

from .pedal import setup as pedal_setup, options
from .server import app

uvicorn_log = logging.getLogger("uvicorn")
del uvicorn_log.handlers[0]

dotenv.load_dotenv()
colorama.init()
colouredlogs.install(logging.DEBUG, stream=sys.stdout, reconfigure=False)


@app.on_event("startup")
async def setup():
    options.__init__(f"temp/{options.FOLDER}")
    pedal_setup()
