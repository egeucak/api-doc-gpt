import os
import json
import logging

from api_doc_gpt.chat import Chat
from api_doc_gpt.engine import Engine
from api_doc_gpt.openapi_parser import OpenApiGeneric, OpenApiParser, OpenApiGenericList
from api_doc_gpt.react.tools import Tool, RequestTool, GetEndpointDetails

dirname = os.path.dirname(__file__)
logger = logging.getLogger(__name__)


class ReactEngine(Engine):
    def __init__(self, tools: list[Tool], openapi_json: dict, base_url: str) -> None:
        self.tools = tools
        self.openapi_json = openapi_json
        self.base_url = base_url
        self.chat = self._get_chat()

    def _get_chat(self):
        system_prompt = self.get_system_prompt()
        chat = Chat(system_message=system_prompt, stop=["\nObservation:", "\n\tObservation:"])
        return chat

    def get_system_prompt(self) -> str:
        tools = self.tools
        system_prompt = ""

        with open(dirname + "/../assets/react.prompt", "r") as f:
            system_prompt = f.read()

        parser = OpenApiParser(openapi_json=self.openapi_json)
        openapi_parts = parser.parse()

        system_prompt = system_prompt.format(
            tool_descriptions="\n".join([f"- {tool.name}: {tool.description}" for tool in tools]),
            tool_name_list=", ".join([f"{tool.name}" for tool in tools]),
            method_list=openapi_parts.method_definitions.to_csv(),
            base_url=self.base_url
        )
        return system_prompt

    def extract_json_objects(self, text, decoder=json.JSONDecoder()):
        """Find JSON objects in text, and yield the decoded JSON data

        Does not attempt to look for JSON arrays, text, or other JSON types outside
        of a parent JSON object.

        """
        pos = 0
        while True:
            match = text.find('{', pos)
            if match == -1:
                break
            try:
                result, index = decoder.raw_decode(text[match:])
                yield result
                pos = match + index
            except ValueError:
                pos = match + 1

    def parse_language(self, input_str: str):
        lines = input_str.strip().split("\n")
        action = None
        args = None
        args_str = ""
        args_ingesting = False
        for line in lines:
            if line.startswith("Action:"):
                action = line.split(":", 1)[1].strip()
            elif line.startswith("Action Input: "):
                args_ingesting = True
                args_str = line.split(": ", 1)[1].strip()
            elif args_ingesting:
                args_str += line.strip()
        args_dict = None
        for obj in self.extract_json_objects(args_str):
            args_dict = obj

        if args_dict != None:
            args = args_dict
        else:
            args = args_str
        return {"action": action, "args": args}
    

    def ask(self, question) -> str:
        chat = self.chat
        resp: str = chat.user_message(question)
        while True:
            if "Action:" in resp:
                parsed_tools = self.parse_language(resp)
                logging.debug(f"parsed_tools: {parsed_tools}")
                if tool := [t for t in self.tools if t.name == parsed_tools["action"]]:
                    try:
                        observation = tool[0](parsed_tools["args"])
                        logging.debug(f"observation: {observation}")
                    except Exception as e:
                        resp = chat.user_message("Observation: " + str(e))
                        logging.debug(f"resp: {e}")
                        continue
                    resp = chat.user_message("Observation: " + str(observation))
            else:
                break
        return resp
