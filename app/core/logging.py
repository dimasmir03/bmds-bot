import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
    # httpx logs every HTTP request at INFO (e.g. each Hugging Face file while loading weights).
    logging.getLogger("httpx").setLevel(logging.WARNING)
