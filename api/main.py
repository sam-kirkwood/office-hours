from fastapi import FastAPI

from routes.add_interest import router as add_interest_router
from routes.generate_paper_engagement import router as generate_paper_engagement_router
from routes.generate_problem import router as generate_problem_router
from routes.grade_paper_answer import router as grade_paper_answer_router
from routes.grade_solution import router as grade_solution_router
from routes.ingest_paper import router as ingest_paper_router
from routes.ingest_paper_user import router as ingest_paper_user_router
from routes.paper_question import router as paper_question_router
from routes.parse_solution import router as parse_solution_router
from routes.propose_papers import router as propose_papers_router
from routes.suggest_papers import router as suggest_papers_router
from routes.surface_daily import router as surface_daily_router
from routes.update_queue import router as update_queue_router

app = FastAPI(title="office-hours API", version="0.1.0")

app.include_router(generate_problem_router)
app.include_router(add_interest_router)
app.include_router(grade_solution_router)
app.include_router(ingest_paper_router)
app.include_router(ingest_paper_user_router)
app.include_router(generate_paper_engagement_router)
app.include_router(grade_paper_answer_router)
app.include_router(paper_question_router)
app.include_router(propose_papers_router)
app.include_router(suggest_papers_router)
app.include_router(parse_solution_router)
app.include_router(surface_daily_router)
app.include_router(update_queue_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
