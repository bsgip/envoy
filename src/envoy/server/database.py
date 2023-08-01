from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "do_connect")
def receive_do_connect(dialect, conn_rec, cargs, cparams):
    "listen for the 'do_connect' event"
    print(f"cargs {cargs}")
    print(f"cparams {cparams}")



def fetch_azure_token()