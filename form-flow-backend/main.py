from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import models
import database

# Import Routers
from routers import auth, forms, speech

app = FastAPI()

# Configure CORS
origins = [
    "http://localhost:5173", # Default port for Vite/React development server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(forms.router)
app.include_router(speech.router)

# --- Database Initialization ---
@app.on_event("startup")
async def startup_event():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

@app.get("/")
def read_root():
    return {"Hello": "Form Wizard Pro Backend is running (Refactored)"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
