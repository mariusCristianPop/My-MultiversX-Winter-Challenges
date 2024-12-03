import logging
import time
from pathlib import Path

def setup_logging(output_dir: Path, logger_name: str = "ShardWalletOrchestrator") -> logging.Logger:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"execution_log_{timestamp}.txt"
    logger = logging.getLogger(logger_name)
    logger.propagate = False
    logger.handlers = []
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(file_format)
    logger.addHandler(console_handler)

    return logger
