import json
import logging

import requests

from api_doc_gpt.chat import Chat

logger = logging.getLogger(__name__)

class ProcessingEngine:
    def __init__(self, chat: Chat, base_url = "http://0.0.0.0:8000"):
        self.chat = chat
        self.base_url = base_url
        
    def ask(self, question) -> str:
        response: str = self.chat.user_message(f"PROMPT: {question}")
        if response.startswith("OUT: "): return self.process_out(response)
        elif response.startswith("CMD: "): return self.process_cmd(response)
        return self.ask(f"Your answer does not start with either OUT: or CMD:. Answer again. The question is '{question}'")

    def cmd_resp(self, server_dat: str) -> str:
        response: str = self.chat.user_message(f"CMD_RESP: {server_dat}")
        return self.process_out(response)
        
    def process_out(self, text: str) -> str:
        text = text.replace("OUT: ", "", 1)
        return text

    def process_cmd(self, text: str):
        command = text.replace("CMD: ", "", 1)
        command_parts = command.split(";")
        # Command format:
        # METHOD PATH; REQ_BODY {body}; HEADER {header}

        method = command_parts[0].split(" ")[0]
        path = command_parts[0].split(" ")[1]

        body = None
        headers = None

        if "REQ_BODY" in command:
            for part in command_parts:
                if "REQ_BODY" in part:
                    body_str = part.split("REQ_BODY ")[1]
                    body = json.loads(body_str)
                    break

        if "HEADER" in command:
            for part in command_parts:
                if "HEADER" in part:
                    header_str = part.split("HEADER ")[1]
                    try:
                        headers = json.loads(header_str)
                    except:
                        headers = None
                    finally:
                        break

        response = self.send_request(method, path, body, headers=headers)
        return self.cmd_resp(response)
   
    def send_request(self, method: str, path: str, body_dict: dict | None, headers: dict | None = None):
        try:
            body = None
            if body_dict:
                body = json.dumps(body_dict)
            logger.debug(f"Sending request to {self.base_url + path}")
            logger.debug(f"Request body: {body}")
            logger.debug(f"Request headers: {headers}")
            resp = requests.request(method, self.base_url + path, data=body, headers=headers)
            try:
                resp_text = resp.json()
                resp_text = json.dumps(resp_text)
            except:
                resp_text = resp.text
            
            logger.debug(f"Response: {resp}")
            logger.debug(f"Response status: {resp.status_code}")
            
            return json.dumps(resp.json())
        except Exception as e:
            return e
