"""
HALOsination — Optional UI server (port 8001).

The mandatory POST /run API runs on port 8000 (see run.py).
This UI server serves the demo interface at http://localhost:8001
which calls the API on port 8000 from the browser.

Per G42 Agentathon spec: optional UI may run on port 8001; the
port-8000 API must remain programmatically evaluable regardless.
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="HALOsination UI", version="0.5.0")

UI_DIR = Path(__file__).resolve().parent / "ui"


@app.get("/")
def index():
    return FileResponse(UI_DIR / "index.html")


@app.get("/halo")
def halo():
    return FileResponse(UI_DIR / "halo.html")


# Serve any static files in ui/ (in case we add CSS/JS files later)
if UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("HALOsination UI server")
    print("Open in browser: http://localhost:8001")
    print("(Make sure the API server is also running: python run.py)")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8001)
