from __future__ import annotations

import uvicorn

from src.config.settings import get_settings
from src.presentation.api.app import create_app

settings = get_settings()
app = create_app(settings)

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
