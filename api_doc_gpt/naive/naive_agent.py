import json
import os
from api_doc_gpt.engine import Engine

from api_doc_gpt.openapi_parser import OpenApiParser, OpenApiParts
from api_doc_gpt.chat import Chat
from api_doc_gpt.naive.processing_engine import ProcessingEngine


class NaiveAgent(Engine):
    chat: Chat
    engine: ProcessingEngine

    def __init__(self, base_url: str, openapi_json: dict, model_name: str):
        self.base_url = base_url
        self.model_name = model_name
        self.openapi_json = openapi_json

    def start(self):
        openapi = self.openapi_json
        openapi_parts = OpenApiParser(openapi).parse()

        system_prompt = self.get_system_prompt(openapi_parts)
        start_prompt = self.get_start_prompt()

        starting_state = [
            {"role": "system", "content": system_prompt},
            *start_prompt
        ]
        chat = Chat(starting_state=starting_state, model_name=self.model_name)
        engine = ProcessingEngine(chat=chat, base_url=self.base_url)
        self.chat = chat
        self.engine = engine

    def get_system_prompt(self, openapi_parts: OpenApiParts) -> str:
        method_definitions = openapi_parts.method_definitions.to_csv()
        schema_definitions = openapi_parts.schema_definitions.to_csv()
        parameter_definitions = openapi_parts.parameter_definitions.to_csv()
        request_body_definitions = openapi_parts.request_body_definitions.to_csv()
        security_definitions = openapi_parts.security_definitions.to_csv()

        system_prompt = ""
        dirname = os.path.dirname(__file__)
        with open(dirname + "/../assets/system_prompt.txt", "r") as f:
            system_prompt = f.read()

        system_prompt = system_prompt.format(
            method_definitions = method_definitions,
            parameter_definitions = parameter_definitions,
            request_body_definitions = request_body_definitions,
            schema_definitions = schema_definitions,
            security_definitions = security_definitions
        )
        return system_prompt

    def get_start_prompt(self) -> dict:
        start_prompt = {}
        dirname = os.path.dirname(__file__)
        with open(dirname + "/../assets/start_prompt.json", "r") as f:
            start_prompt = json.loads(f.read())
        return start_prompt
    
    def ask(self, question):
        return self.engine.ask(question)
