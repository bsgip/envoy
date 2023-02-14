import uvicorn
from fastapi import Depends, FastAPI

from server.api.depends import LFDIAuthDepends
from server.api.sep2.time import router as tm_router
from server.settings import AppSettings

settings = AppSettings()
lfdi_auth = LFDIAuthDepends(settings.cert_pem_header)


app = FastAPI(**settings.fastapi_kwargs, dependencies=[Depends(lfdi_auth)])

app.include_router(tm_router, tags=["time"])

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
