from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemma-4-31b-it")
        self.output_dir = Path(os.getenv("FANFICTL_OUTPUT_DIR", "./output")).resolve()
