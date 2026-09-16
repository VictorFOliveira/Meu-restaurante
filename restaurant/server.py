import os
import uvicorn

def run():
    uvicorn.run("restaurant.api:app", host=os.getenv("API_HOST","0.0.0.0"), port=int(os.getenv("API_PORT","8000")), reload=False)

if __name__ == "__main__": run()
