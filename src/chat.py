import logging

import openai

logger = logging.getLogger(__name__)

class Chat:
    _messages = []
    def __init__(
        self,
        system_message: str = "You are a helpful AI assistant",
        starting_state: list[str] = None,
        model_name: str = "gpt-3.5-turbo"
    ):
        if starting_state:
            self._messages = starting_state
        else:
            self._messages.append({
                "role": "system",
                "content": system_message
            })
        self.total_tokens = 0
        self.model_name = model_name
        
    def _construct_request(self, messages):
        req = {
            "model": self.model_name,
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
        logger.debug(f"Tokens for this request: {resp['usage']['total_tokens']}")
        logger.debug(f"Total tokens used: {self.total_tokens}")
        logger.debug(f"Question: {text}")
        logger.debug(f"Answer: {content}")
        return content
