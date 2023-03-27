import importlib
import json
import logging
from typing import Literal

from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI
import openai
import requests

from api_doc_gpt.chat import Chat
from api_doc_gpt.react.react_engine import ReactEngine
from api_doc_gpt.react.tools import GetEndpointDetails, RequestTool
from api_doc_gpt.naive.naive_agent import NaiveAgent


class ApiMasterAI:
    chat: Chat

    def __init__(self, target_app: str, base_url: str, openapi_json_path: str, model_name: str, agent: Literal["naive", "react"] = "naive"):
        self.target_app_path = target_app
        self.base_url = base_url
        self.openapi_json_path = openapi_json_path
        self.model_name = model_name
        self.agent = agent
    
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

    def start(self):
        if self.agent == "naive":
            self.start_naive()
        elif self.agent == "react":
            self.start_react()
        else:
            raise ValueError(f"Method '{self.agent}' is not supported.")
    
    def start_naive(self):
        openapi = self._get_openapi()
        naive_engine = NaiveAgent(base_url=self.base_url, model_name=self.model_name, openapi_json=openapi)
        naive_engine.start()
        self.engine = naive_engine

    def start_react(self):
        openapi = self._get_openapi()
        react_engine = ReactEngine(tools=[GetEndpointDetails(openapi_json=openapi), RequestTool()], openapi_json=openapi, base_url=self.base_url)
        self.engine = react_engine

    def q(self, question):
        return self.engine.ask(question)


def start_api_master(
        openai_key: str,
        target_app: str | None = None,
        openapi_json: str | None = None,
        base_url="http://0.0.0.0:8000",
        verbose: bool = False,
        model_name: str = "gpt-3.5-turbo",
        agent: Literal["naive", "react"] = "react"
    ) -> callable:
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.ERROR)

    openai.api_key = openai_key
    api_master_ai = ApiMasterAI(target_app=target_app, base_url=base_url, openapi_json_path=openapi_json, model_name=model_name, agent=agent)
    api_master_ai.start()
    q = api_master_ai.q

    while True:
        inp = input(">>> ")
        if inp == "exit": break
        print(q(inp))
