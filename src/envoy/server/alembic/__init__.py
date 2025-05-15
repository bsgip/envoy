"""DB versions - allows any downstream dependencies to use these migrations by making it all relative.

Originally sourced from https://stackoverflow.com/a/74875605"""

from pathlib import Path

from alembic import command
from alembic.config import Config

# Ensure all the paths are absolute references and can be accessed from within this project or in downstream projects
ROOT_PATH = Path(__file__).parent.parent
ALEMBIC_CFG = Config(ROOT_PATH / "alembic.ini")
ALEMBIC_CFG.set_main_option("script_location", str((ROOT_PATH / "alembic").resolve()))


def current(verbose=False):
    command.current(ALEMBIC_CFG, verbose=verbose)


def upgrade(revision="head"):
    command.upgrade(ALEMBIC_CFG, revision)


def downgrade(revision):
    command.downgrade(ALEMBIC_CFG, revision)
