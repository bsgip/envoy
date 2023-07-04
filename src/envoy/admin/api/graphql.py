import json
import logging
from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Request
from fastapi_async_sqlalchemy import db

from envoy.admin.schema.graphql import AggregatorLoader, schema
from envoy.admin.schema.uri import GraphqlUri

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(GraphqlUri)
async def graphql_query(request: Request) -> dict:
    raw_body = await request.body()
    query = raw_body.decode("utf-8")

    json_obj = json.loads(query)
    q = json_obj["query"]

    result = await schema.execute_async(
        q, context_value={"session": db.session, "aggregator_loader": AggregatorLoader(db.session)}
    )

    # if result.errors is not None and len(result.errors) > 0:
    #    msg = "\n".join([e.message for e in result.errors])
    return {
        "data": result.data,
        "errors": None if result.errors is None else [e.message for e in result.errors],
        "extensions": result.extensions,
    }
