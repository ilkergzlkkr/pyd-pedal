import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run("pypedal.main:app", host="0.0.0.0", port=int(os.getenv("PORT") or 8000))
