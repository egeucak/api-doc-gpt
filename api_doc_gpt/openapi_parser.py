import csv
from dataclasses import dataclass
from io import StringIO

def dict_to_csv(data: list[dict]) -> str:
    """
    Convert a dictionary to a CSV string.
    """
    # Use a StringIO object to simulate a file for CSV writer
    f = StringIO()
    writer = csv.writer(f)
    if not data: return ""
    # Write the header row
    writer.writerow(data[0].keys())
    # Write the data rows
    for row in data:
        writer.writerow(row.values())
    # Get the CSV string
    csv_string = f.getvalue()
    f.close()
    return csv_string


@dataclass
class OpenApiGeneric:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self):
        return self.__dict__
    
    def __str__(self) -> str:
        return str(self.to_dict())
    
    def __repr__(self) -> str:
        return str(self.to_dict())


@dataclass
class OpenApiGenericList:
    content: list[OpenApiGeneric]

    def __init__(self, content: list[OpenApiGeneric]) -> None:
        self.content = content

    def to_dict(self):
        return [item.to_dict() for item in self.content]
    
    def to_csv(self):
        return dict_to_csv(self.to_dict())


class OpenApiMethodDefinition(OpenApiGeneric):
    operation_id: str
    path: str
    method: str
    summary: str
    security: str
    response_schema: str
 
class OpenApiMethodDefinitionList(OpenApiGenericList):
    content: list[OpenApiMethodDefinition]


class OpenApiParameterDefinition(OpenApiGeneric):
    operation_id: str
    required: bool
    name: str
    in_: str
    title: str
    parameter_type: str

class OpenApiParameterDefinitionList(OpenApiGenericList):
    content: list[OpenApiParameterDefinition]


class OpenApiRequestBodyDefinition(OpenApiGeneric):
    operation_id: str
    content_type: str
    schema_ref: str

class OpenApiRequestBodyDefinitionList(OpenApiGenericList):
    content: list[OpenApiRequestBodyDefinition]


class OpenApiSchemaDefinition(OpenApiGeneric):
    schema_name: str
    variable_name: str
    variable_type: str
    required: bool

class OpenApiSchemaDefinitionList(OpenApiGenericList):
    content: list[OpenApiSchemaDefinition]


class OpenApiSecurityDefinition(OpenApiGeneric):
    security_name: str
    security_type: str

class OpenApiSecurityDefinitionList(OpenApiGenericList):
    content: list[OpenApiSecurityDefinition]

@dataclass
class OpenApiParts:
    method_definitions: OpenApiMethodDefinitionList
    parameter_definitions: OpenApiParameterDefinitionList
    request_body_definitions: OpenApiRequestBodyDefinitionList
    schema_definitions: OpenApiSchemaDefinitionList
    security_definitions: OpenApiSecurityDefinitionList

class OpenApiParser:
    schema_prefix = "#/components/schemas/"

    def __init__(self, openapi_json: dict) -> None:
        self.openapi_json = openapi_json
        self.openapi_parts = OpenApiParts([], [], [], [], [])

    def parse(self) -> OpenApiParts:
        self._parse_paths()
        self._parse_components()
        return self.openapi_parts
    
    def _parse_paths(self):
        openapi_data = self.openapi_json
        schema_prefix = self.schema_prefix
    
        method_definition_data = []
        parameter_list = []
        request_body_list = []

        for path, path_item in openapi_data["paths"].items():
            for method, operation in path_item.items():
                operation_id = operation["operationId"]
                security = None
                if "security" in operation:
                    security = list(operation["security"][0].keys())[0]
                    # security = "🔒"
                responses = operation.get("responses")
                success_response = responses.get("200")
                if not success_response: success_response = list(responses.values())[0]
                if success_response.get("content"):
                    response_content_type, response_content_schema = list(success_response.get("content").items())[0]
                    response_content_schema_ref = response_content_schema.get("schema", {}).get("$ref")
                else:
                    response_content_type = None
                    response_content_schema = None
                    response_content_schema_ref = None
                if response_content_schema_ref: response_content_schema_ref = response_content_schema_ref.replace(schema_prefix, "")

                if operation.get("parameters"):
                    for parameter in operation.get("parameters"):
                        parameter_type = parameter.get("schema").get("type")
                        if parameter_type == "array" and parameter.get("schema", {}).get("items"):
                            try:
                                parameter_type_ref = parameter["schema"]['items'].get('type')
                            except KeyError:
                                parameter_type_ref = parameter["schema"]['items'].get('$ref').replace(schema_prefix, "")
                            parameter_type = f"array[{parameter_type_ref}]"
                        parameter_list.append({
                            "operation_id": operation_id,
                            "required": parameter.get("required"),
                            "name": parameter.get("name"),
                            "in": parameter.get("in"),
                            "title": parameter.get("schema").get("title"),
                            "parameter_type": parameter_type,
                        })
                if request_body := operation.get("requestBody"):
                    for content_type, schema in request_body.get("content").items():
                        request_body_list.append({
                            "operation_id": operation_id,
                            "content_type": content_type,
                            "schema_ref": schema.get("schema").get("$ref", "").replace(schema_prefix, "")
                        })
                method_definition_data.append({
                    "operation_id": operation_id,
                    "path": path,
                    "method": method.upper(),
                    "summary": operation.get("summary", ""),
                    "security": security,
                    # "response_type": response_content_type,
                    "response_schema": response_content_schema_ref
                })
        self.openapi_parts.method_definitions = OpenApiMethodDefinitionList([OpenApiMethodDefinition(**d) for d in method_definition_data])
        self.openapi_parts.parameter_definitions = OpenApiParameterDefinitionList([OpenApiParameterDefinition(**d) for d in parameter_list])
        self.openapi_parts.request_body_definitions = OpenApiRequestBodyDefinitionList([OpenApiRequestBodyDefinition(**d) for d in request_body_list])

    def _parse_components(self):
        openapi_data = self.openapi_json
        schema_prefix = self.schema_prefix

        schema_data = []
        security_data = []

        for path, path_item in openapi_data.get('components', {}).get("schemas", {}).items():
            required_fields = set(path_item.get("required", []))
            properties = path_item.get("properties", {})
            for property_key, property_details in properties.items():
                variable_type = property_details.get("type")
                if not variable_type and property_details.get("$ref"):
                    variable_type = property_details.get("$ref", "").replace(schema_prefix, "") # fallback to $ref
                if variable_type == "array":
                    variable_type = property_details.get("items", {}).get("$ref", "").replace(schema_prefix, "")
                    variable_type = variable_type.replace(schema_prefix, "")
                schema_data.append({
                    "schema_name": path,
                    "variable_name": property_key,
                    "variable_type": variable_type,
                    "required": property_key in required_fields
                })

        for path, path_item in openapi_data.get('components', {}).get("securitySchemes", {}).items():
            security_data.append({
                "security_name": path,
                "security_type": path_item.get("type")
            })

        self.openapi_parts.schema_definitions = OpenApiSchemaDefinitionList([OpenApiSchemaDefinition(**d) for d in schema_data])
        self.openapi_parts.security_definitions = OpenApiSecurityDefinitionList([OpenApiSecurityDefinition(**d) for d in security_data])
