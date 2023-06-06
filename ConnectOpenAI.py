from typing import Tuple

import openai
import tiktoken
import variables
import time


class ConnectOpenAI:
    def __init__(self, api_key: str, instruction: str, **kwargs):
        self.api_key = api_key
        self.model = kwargs.get('model', 'gpt-4')
        self.max_tokens = kwargs.get('max_tokens', 2048)
        self.frequency_penalty = kwargs.get('frequency_penalty', 0.2)
        self.presence_penalty = kwargs.get('presence_penalty', 0.2)
        self.messages = [{"role": "system", "content": instruction}]

        self.estimated_tokens = 0
        self.total_tokens = 0

    def num_tokens_from_messages(self, messages, model="gpt-3.5-turbo-0301"):
        """Returns the number of tokens used by a list of messages."""
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            print("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")
        if model == "gpt-3.5-turbo":
            print("Warning: gpt-3.5-turbo may change over time. Returning num tokens assuming gpt-3.5-turbo-0301.")
            return self.num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
        elif model == "gpt-4":
            print("Warning: gpt-4 may change over time. Returning num tokens assuming gpt-4-0314.")
            return self.num_tokens_from_messages(messages, model="gpt-4-0314")
        elif model == "gpt-3.5-turbo-0301":
            tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
            tokens_per_name = -1  # if there's a name, the role is omitted
        elif model == "gpt-4-0314":
            tokens_per_message = 3
            tokens_per_name = 1
        else:
            raise NotImplementedError(
                f"""num_tokens_from_messages() is not implemented for model {model}. 
                See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are 
                converted to tokens.""")
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return num_tokens

    def moderate_message(self, user_message: str, test: bool = False, test_flagged: bool = False) -> bool:
        if test:
            flagged = test_flagged
        else:
            openai.api_key = self.api_key
            response = openai.Moderation.create(input=user_message)
            flagged = response['results'][0]['flagged']
        return flagged

    def create_story(self, user_message: str, test: bool = False, test_reason: str = 'stop', wait_time: int = 1) -> \
            Tuple[str, str]:
        if test:
            if not any(test_reason in reason for reason in ('stop', 'length', 'content_filter')):
                test_reason = 'stop'
            time.sleep(wait_time)
            story = variables.example_story
            finish_reason = test_reason
        else:
            print('Generating a story for:')
            print(user_message)
            self.messages.append({"role": "user", "content": user_message})
            self.estimated_tokens = self.num_tokens_from_messages(self.messages, self.model)
            openai.api_key = self.api_key
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=self.messages,
                max_tokens=self.max_tokens,
                frequency_penalty=self.frequency_penalty,
                presence_penalty=self.presence_penalty,
            )

            story = response['choices'][0]['message']['content']
            print('Story generated.')
            finish_reason = response['choices'][0]['finish_reason']
            self.total_tokens = response['usage']['total_tokens']
            print(f'Total used tokens: {self.total_tokens}')

        return story, finish_reason
