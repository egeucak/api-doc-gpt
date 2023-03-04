from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI
import openai
import json
import requests
import importlib
import csv
from io import StringIO


def dict_to_csv(data):
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


class Chat:
    _messages = []
    def __init__(self, system_message: str = "You are a helpful AI assistant", starting_state: list[str] = None):
        if starting_state:
            self._messages = starting_state
        else:
            self._messages.append({
                "role": "system",
                "content": system_message
            })
        self.total_tokens = 0
        
    def _construct_request(self, messages):
        req = {
            "model": "gpt-3.5-turbo",
            "messages": messages
        }
        return req
    
    def _send_req(self, args):
        return openai.ChatCompletion.create(
            **args,
            temperature=0
        )
    
    def user_message(self, text: str):
        self._messages.append(
            {
                "role": "user",
                "content": text
            }
        )
        request = self._construct_request(self._messages)
        resp = self._send_req(request)
        message = resp["choices"][0]["message"]
        role = message["role"]
        content = message["content"]
        
        self._messages.append({
            "role": role,
            "content": content
        })
        self.total_tokens += resp["usage"]["total_tokens"]
        return content


class ProcessingEngine:
    def __init__(self, chat: Chat, base_url = "http://0.0.0.0:8000"):
        self.chat = chat
        self.base_url = base_url
        
    def ask(self, question) -> str:
        response: str = self.chat.user_message(f"PROMPT: {question}")
        if response.startswith("OUT: "): return self.process_out(response)
        elif response.startswith("CMD: "): return self.process_cmd(response)
        return self.ask(f"Your answer does not start with either OUT: or CMD:. Answer again. The question is '{question}'")

    def cmd_resp(self, server_dat) -> str:
        response: str = self.chat.user_message(f"CMD_RESP: {server_dat}")
        return self.process_out(response)
        
    def process_out(self, text: str) -> str:
        text = text.replace("OUT: ", "", 1)
        return text

    def process_cmd(self, text: str):
        command = text.replace("CMD: ", "", 1)
        method = command.split(" ")[0]
        path = command.split(" ")[1]
        body = None
        if "REQUEST_BODY" in command:
            body_str = command.split("REQUEST_BODY: ")[1]
            body = json.loads(body_str)

        response = self.send_request(method, path, body)
        return self.cmd_resp(response)
   
    def send_request(self, method: str, path: str, body_dict: dict | None):
        try:
            body = None
            if body_dict:
                body = json.dumps(body_dict)
            req = requests.request(method, self.base_url + path, data=body)
            return req.text
        except Exception as e:
            return e


class ApiMasterAI:
    chat: Chat
    engine: ProcessingEngine

    def __init__(self, app: FastAPI, base_url: str):
        self.app = app
        self.base_url = base_url

    def get_method_definitions(self, openapi_docs):
        data = []
        for path, path_item in openapi_docs['paths'].items():
            for method, operation in path_item.items():
                summary = operation.get('summary', '')
                request_body = operation.get('requestBody', '').__str__()
                parameters = operation.get('parameters', '').__str__()
                data.append({
                    'path': path,
                    'method': method.upper(),
                    'summary': summary,
                    "request_body": request_body,
                    "parameters": parameters,
                })

        method_definitions = dict_to_csv(data)
        return method_definitions

    def get_schema_definitions(self, openapi_docs):
        data = []
        for path, path_item in openapi_docs.get('components', {}).get("schemas", {}).items():
            required_fields = path_item.get("required", [])
            properties = path_item.get("properties")
            data.append({
                "schema": path,
                "required_fields": required_fields,
                "properties": properties,
            })
        schema_definitions = dict_to_csv(data)
        return schema_definitions

    def get_openapi(self):
        app = self.app
        openapi_docs = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
            openapi_prefix=app.openapi_prefix,
        )
        return openapi_docs
    
    def start(self):
        method_definitions = self.get_method_definitions(self.get_openapi())
        schema_definitions = self.get_schema_definitions(self.get_openapi())

        system_prompt = self.get_system_prompt(method_definitions, schema_definitions)
        start_prompt = self.get_start_prompt()

        starting_state = [
            {"role": "system", "content": system_prompt},
            *start_prompt
        ]
        chat = Chat(starting_state=starting_state)
        engine = ProcessingEngine(chat=chat, base_url=self.base_url)
        self.chat = chat
        self.engine = engine        

    def get_system_prompt(self, method_definitions, schema_definitions) -> str:
        system_prompt = ""
        with open("./system_prompt.txt", "r") as f:
            system_prompt = f.read()

        system_prompt = system_prompt.format(method_definitions = method_definitions, schema_definitions = schema_definitions)
        return system_prompt

    def get_start_prompt(self) -> dict:
        start_prompt = {}
        with open("./start_prompt.json", "r") as f:
            start_prompt = json.loads(f.read())
        return start_prompt
    
    def q(self, question):
        return self.engine.ask(question)


def start_api_master(openai_key: str, target_app: str, base_url="http://0.0.0.0:8000") -> callable:
    openai.api_key = openai_key
    package_path, module_name = target_app.split(":")
    fastapi_module = importlib.import_module(package_path, module_name)
    fastapi_app = getattr(fastapi_module, module_name)
    api_master_ai = ApiMasterAI(app=fastapi_app, base_url=base_url)
    api_master_ai.start()
    q = api_master_ai.q

    while True:
        inp = input(">>> ")
        if inp == "exit": break
        print(q(inp))
    
if __name__=="__main__":
    import fire
    fire.Fire(start_api_master)
