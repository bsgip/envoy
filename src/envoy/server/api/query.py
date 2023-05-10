from fastapi import Query

# List query parameters to provide paging/filtering to List resources
StartQueryParameter = Query([0], alias="s")
AfterQueryParameter = Query([0], alias="a")
LimitQueryParameter = Query([1], alias="l")
