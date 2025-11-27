from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    auth,
    users,
    roles,
    students,
    groups,
    contracts,
    transactions,
    coach,
    gate,
    reports,
    settings,
    public,
    import_router,
)

app = FastAPI(
    title="BUNYODKOR CIMS API",
    description="Comprehensive management system for Bunyodkor Football Academy",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "bunyodkor-cims"}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(students.router)
app.include_router(groups.router)
app.include_router(contracts.router)
app.include_router(transactions.router)
app.include_router(coach.router)
app.include_router(gate.router)
app.include_router(reports.router)
app.include_router(settings.router)
app.include_router(public.router)
app.include_router(import_router.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
