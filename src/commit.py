from datetime import datetime, timedelta
from random import random
import git, os, logging, pygit2, tqdm, subprocess, base64
from faker import Faker
from src.config import Config
from src.secrets import Secrets
from src.connection import ConnectionHandler


class Commit:
    
    def __init__(self, secrets: Secrets, access_token: str, config_file = None):
        self.pat = access_token
        self.fake = Faker()
        self.secrets = secrets
        self.config = Config() if config_file is None else Config(config_file)
        self.conn = ConnectionHandler(config_file=config_file)

    async def get_branch_hash(self, organization: str, repository: str, branch: str):
        resp = await self.conn.get(f'/repos/{organization}/{repository}/git/refs')
        main_sha = None
        other_sha = None
        for ref in resp:
            if f'refs/heads/{branch}' == ref['ref']:
                return ref['object']['sha']
            elif f'refs/heads/main' == ref['ref']:
                main_sha = ref['object']['sha']
            else:
                other_sha = ref['object']['sha']
        json_data = {
                    'ref':f'refs/heads/{branch}',
                    'sha': main_sha if main_sha is not None else other_sha
                }
        resp = await self.conn.post(f'/repos/{organization}/{repository}/git/refs', json_data=json_data)
        return resp['object']['sha']

    async def generate_random_commits(self, organization: str, repository: str, branch: str, branch_head_hash: str, count: int, days_since_latest_commit: int, commit_secret = False):
        if days_since_latest_commit > 90 and not commit_secret:
            return
        query = """
            mutation ($input: CreateCommitOnBranchInput!) {
                createCommitOnBranch(input: $input) {
                    commit {
                        url
                    }
                }
            }
        """
        additions = []
        for _ in range(3):
            additions.append({
                'path': f'GitGoat_{self.fake.lexify(text="???????")}.txt',
                'contents': self.base64_encode(self.secrets.get_next_secret()) if commit_secret else self.base64_encode()
            })  
        variables = {
                    'input': {
                        'branch': {
                            'repositoryNameWithOwner': f'{organization}/{repository}',
                            'branchName': branch
                        },
                        'message': {
                            'headline': f'Random commit message from GitGoat - {self.fake.lexify(text="?????")}'
                        },
                        'fileChanges': {
                            'additions': additions
                        },
                        "expectedHeadOid": branch_head_hash
                    }
                }
        resp = await self.conn.post_graphql(query, variables, self.pat)
        return resp

    def base64_encode(self, content = None):
        text = content if content is not None else self.fake.paragraph(nb_sentences=1)
        base64_bytes = base64.b64encode(text.encode('ascii'))
        return base64_bytes.decode('ascii')