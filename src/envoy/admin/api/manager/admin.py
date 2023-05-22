from sqlalchemy.ext.asyncio import AsyncSession


class AdminManager:
    @staticmethod
    async def commit_doe(session: AsyncSession, site_id: int):
        pass

    # mapper to map from request? not req'd for pure json I would think
    # upsert function to do the sqlalchemy magic (that will need to go in crud folder)

    # maybe:
    # await session.commit()
    # return result
