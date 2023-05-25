import logging

import uvicorn
from fastapi import Depends, FastAPI, HTTPException

from envoy.admin.api.depends import AdminAuthDepends
from envoy.admin.api.router import router
from envoy.admin.settings import admin_settings

logging.basicConfig(style="{", level=logging.INFO)

admin_auth = AdminAuthDepends(admin_settings.admin_username, admin_settings.admin_password)
app = FastAPI(dependencies=[Depends(admin_auth)])
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9999)
