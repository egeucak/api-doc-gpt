import logging

import requests

from api_doc_gpt.openapi_parser import OpenApiGeneric, OpenApiParser, OpenApiGenericList

logger = logging.getLogger(__name__)

def search_in_openapi_parts(openapi_part: OpenApiGenericList, key, value) -> OpenApiGeneric | None:
    for item in openapi_part.content:
        if getattr(item, key) == value:
            return item
    return None


class Tool:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def __call__(self, *args: any, **kwds: any) -> any:
        raise NotImplementedError
    
class GetEndpointDetails(Tool):
    def __init__(self, openapi_json: dict):
        self.openapi_json = openapi_json
        super().__init__(
            name="EndpointDetails",
            description="Use this for getting details about an OpenAPI endpoint. You should use this tool to know which body or other parameters you need to use for request. Always use this tool before sending any requests. Input should be operation_id. Always start with this before doing anything else.",
        )

    def __call__(self, endpoint_id: str) -> any:
        parser = OpenApiParser(openapi_json=self.openapi_json)
        openapi_parts = parser.parse()

        endpoint_definition = search_in_openapi_parts(openapi_parts.method_definitions, "operation_id", endpoint_id)
        if not endpoint_definition:
            raise ValueError(f"Endpoint {endpoint_id} not found")

        endpoint_parameters_part = search_in_openapi_parts(openapi_parts.parameter_definitions, "operation_id", endpoint_id)
        request_body_part = search_in_openapi_parts(openapi_parts.request_body_definitions, "operation_id", endpoint_id)
        request_body_schema = None

        security = endpoint_definition.security
        security_details_part = search_in_openapi_parts(openapi_parts.security_definitions, "security_name", security)

        if request_body_part:
            request_body_ref = request_body_part.schema_ref
            request_body_schema = []
            for schema in openapi_parts.schema_definitions.content:
                if schema.schema_name == request_body_ref:
                    request_body_schema.append(schema)

        return {
            "endpoint_parameters": endpoint_parameters_part,
            "request_body_schema": request_body_schema,
            "endpoint_definition": endpoint_definition,
            "security_details": security_details_part,
        }  

class RequestTool(Tool):
    def __init__(self):
        super().__init__(
            name="Request",
            description="Use this for making a request to an API on user's behalf. Action Input must be a dict of arguments that can be passed to `requests.request` function.",
        )

    def __call__(self, body) -> any:
        logger.debug(f"Making request with data: {body}")
        return requests.request(**body).json()