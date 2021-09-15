import logging, requests, time
from src.config import Config
from datetime import datetime

class ConnectionHandler:
    
    def __init__(self, pat = None, config_file = None):
        self.config = Config() if config_file is None else Config(config_file)
        self.headers = self.config.base_headers
        self.base_url = self.config.base_url
        if pat is not None:
            self.headers['Authorization'] = Config.generate_auth_header(pat)

    async def get(self, endpoint):
        resp = requests.get(self.base_url + endpoint, headers=self.headers)
        if resp.status_code != 200:
            logging.warning(f'The response code for the GET endpoint {endpoint} is {resp.status_code}. Message: {resp.text}')
            await self.__validate_rate_limit(resp)
            resp = requests.get(self.base_url + endpoint, headers=self.headers)
        try:
            return resp.json()
        except Exception:
            return {}
    
    async def delete(self, endpoint):
        resp = requests.delete(self.base_url + endpoint, headers=self.headers)
        if resp.status_code != 204:
            logging.warning(f'The response code for the DELETE endpoint {endpoint} is {resp.status_code}. Message: {resp.text}')
            await self.__validate_rate_limit(resp)
            requests.delete(self.base_url + endpoint, headers=self.headers)
    
    async def post(self, endpoint, json_data):
        resp = requests.post(self.base_url + endpoint, headers=self.headers, json=json_data)
        if resp.status_code not in [200, 201]:
            logging.warning(f'The response code for the POST endpoint {endpoint} is {resp.status_code}. Message: {resp.text}')
            await self.__validate_rate_limit(resp)
            resp = requests.post(self.base_url + endpoint, headers=self.headers, json=json_data)
        try:
            return resp.json()
        except Exception:
            return {}
    
    async def put(self, endpoint, json_data):
        resp = requests.put(self.base_url + endpoint, headers=self.headers, json=json_data)
        if resp.status_code not in [200, 201, 204]:
            logging.warning(f'The response code for the PUT endpoint {endpoint} is {resp.status_code}. Message: {resp.text}')
            await self.__validate_rate_limit(resp)
            resp = requests.put(self.base_url + endpoint, headers=self.headers, json=json_data)
        try:
            return resp.json()
        except Exception:
            return {}
    
    async def patch(self, endpoint, json_data):
        resp = requests.patch(self.base_url + endpoint, headers=self.headers, json=json_data)
        if resp.status_code not in [200]:
            logging.warning(f'The response code for the PATCH endpoint {endpoint} is {resp.status_code}. Message: {resp.text}')
            await self.__validate_rate_limit(resp)
            resp = requests.put(self.base_url + endpoint, headers=self.headers, json=json_data)
        try:
            return resp.json()
        except Exception:
            return {}

    async def __validate_rate_limit(self, resp):
        remaining_requests = int(resp.headers['X-RateLimit-Remaining']) if 'X-RateLimit-Remaining' in resp.headers else 1
        if remaining_requests <= 1:
            time_to_sleep = (int(resp.headers['X-RateLimit-Reset']) - datetime.timestamp(datetime.now())) + 1
            logging.info(f'Sleeping for {time_to_sleep} seconds')
            time.sleep(time_to_sleep)