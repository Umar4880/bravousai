import logging
import logging.config
import logging.handlers
from queue import Queue
import yaml, os
import atexit
from pathlib import Path
import sys
from pythonjsonlogger.json import JsonFormatter

log_queue = Queue(-1)
listener = None  

def setup_logging():
    global listener

    os.makedirs("logs", exist_ok=True)

    cfg_path = Path(__file__).with_name("log_config.yaml")
    with open(cfg_path, 'r', encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 1. dictConfig FIRST — wires up QueueHandler to all loggers
    logging.config.dictConfig(cfg)

    # 2. Build formatters
    default_cfg = cfg["formatters"]["default"]
    default_fmt = logging.Formatter(
        fmt=default_cfg["format"],
        datefmt=default_cfg["datefmt"]
    )
    json_fmt = JsonFormatter(fmt=cfg["formatters"]["json"]["format"])

    # 3. Build real handlers
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(default_fmt)
    console_handler.setLevel(logging.INFO)

    file_handler = logging.handlers.RotatingFileHandler(
        filename="logs/app.log",
        maxBytes=10_485_760,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(json_fmt)
    file_handler.setLevel(logging.DEBUG)

    # 4. Start listener AFTER dictConfig
    listener = logging.handlers.QueueListener(
        log_queue,
        console_handler,
        file_handler,
        respect_handler_level=True,
    )
    listener.start()

    atexit.register(listener.stop)