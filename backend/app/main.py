from fastapi import FastAPI

app = FastAPI(title="pyweb backend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
