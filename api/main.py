from fastapi import FastAPI

from routes.generate_problem import router as generate_problem_router

app = FastAPI(title="office-hours API", version="0.1.0")

app.include_router(generate_problem_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
