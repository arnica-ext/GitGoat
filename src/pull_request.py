from src.connection import ConnectionHandler
from faker import Faker
import time, logging

class PullRequest:

    def __init__(self, organization, config_file = None):
        self.endpoint = f'/repos/{organization}/[REPO]/pulls'
        self.fake = Faker()
        self.config_file = config_file

    async def get_pull_requests(self, pat, repository):
        conn = ConnectionHandler(pat, self.config_file)
        endpoint = self.endpoint.replace('[REPO]', repository)
        pr_ids = {}
        resp = await conn.get(endpoint)
        if 'message' in resp:
            logging.error(f'No PRs found in {endpoint}. Skipping.')
            return pr_ids
        for pr in resp:
            if pr['state'] == 'open': 
                pr_ids[str(pr['number'])] = pr['user']['login']
        return pr_ids

    async def create_pull_request(self, pat, repository, head_branch):
        conn = ConnectionHandler(pat, self.config_file)
        endpoint = self.endpoint.replace('[REPO]', repository)
        data = {
            'head': head_branch,
            'base': 'main',
            'title': self.fake.lexify(text='Approval GitGoat fake reference ????????'),
            'body': self.fake.paragraph(nb_sentences=3)
        }
        resp = await conn.post(endpoint, json_data=data)
        return resp
      
    async def review(self, pat, repository, pull_request_number):
        conn = ConnectionHandler(pat, self.config_file)
        endpoint = self.endpoint.replace('[REPO]', repository) + f'/{str(pull_request_number)}/reviews'
        data = {
            'event': 'APPROVE',
            'body:': self.fake.lexify(text='GitGoat automated PR review ????????')
        }
        resp = await conn.post(endpoint, data)
        return resp

    async def merge(self, pat, repository, pull_request_number):
        conn = ConnectionHandler(pat, self.config_file)
        endpoint = self.endpoint.replace('[REPO]', repository) + f'/{str(pull_request_number)}/merge'
        data = {
            'commit_title': self.fake.lexify(text='GitGoat fake commit title ????????'),
            'merge_method': 'merge'
        }
        resp = await conn.put(endpoint, data)
        return True if 'merged' in resp else False