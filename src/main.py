import importlib
import json
import os
import logging

from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI
import openai
import requests

from src.openapi_parser import OpenApiParser, OpenApiParts
from src.chat import Chat
from src.processing_engine import ProcessingEngine


class ApiMasterAI:
    chat: Chat
    engine: ProcessingEngine

    def __init__(self, target_app: str, base_url: str, openapi_json_path: str, model_name: str):
        self.target_app_path = target_app
        self.base_url = base_url
        self.openapi_json_path = openapi_json_path
        self.model_name = model_name
    
    def start(self):
        openapi = self._get_openapi()
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

    def _get_openapi(self) -> dict:
        if self.openapi_json_path:
            openapi_docs = self.get_openapi_from_path(self.openapi_json_path)
        elif self.target_app_path:
            openapi_docs = self.get_openapi_from_fastapi(self.target_app_path)
        return openapi_docs
    
    def get_openapi_from_fastapi(self, target_app_path: str):
        package_path, module_name = target_app_path.split(":")
        fastapi_module = importlib.import_module(package_path, module_name)
        app: FastAPI = getattr(fastapi_module, module_name)
        openapi_docs = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        )
        return openapi_docs
    
    def get_openapi_from_path(self, path: str):
        # check if path is URL or file path
        if path.startswith("http"):
            openapi_docs = requests.get(path).json()
        else:
            with open(path, "r") as f:
                openapi_docs = json.load(f)
        return openapi_docs

    def get_system_prompt(self, openapi_parts: OpenApiParts) -> str:
        method_definitions = openapi_parts.method_definitions.to_csv()
        schema_definitions = openapi_parts.schema_definitions.to_csv()
        parameter_definitions = openapi_parts.parameter_definitions.to_csv()
        request_body_definitions = openapi_parts.request_body_definitions.to_csv()
        security_definitions = openapi_parts.security_definitions.to_csv()

        system_prompt = ""
        dirname = os.path.dirname(__file__)
        with open(dirname + "/assets/system_prompt.txt", "r") as f:
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
        with open(dirname + "/assets/start_prompt.json", "r") as f:
            start_prompt = json.loads(f.read())
        return start_prompt
    
    def q(self, question):
        return self.engine.ask(question)


def start_api_master(
        openai_key: str,
        target_app: str | None = None,
        openapi_json: str | None = None,
        base_url="http://0.0.0.0:8000",
        verbose: bool = False,
        model_name: str = "gpt-3.5-turbo"
    ) -> callable:
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.ERROR)

    openai.api_key = openai_key
    api_master_ai = ApiMasterAI(target_app=target_app, base_url=base_url, openapi_json_path=openapi_json, model_name=model_name)
    api_master_ai.start()
    q = api_master_ai.q

    while True:
        inp = input(">>> ")
        if inp == "exit": break
        print(q(inp))
