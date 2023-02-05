
import os, stat, pathlib, time, logging, base64
from src.config import Config
from src.connection import ConnectionHandler

class CodeOwners:
    
    filename = 'CODEOWNERS'

    def __init__(self, organization: str, repo_name: str, config_file = None):
        self.config = Config() if config_file is None else Config(config_file)
        self.org = organization
        self.repo = repo_name
        self.is_codeowners_in_config = self.__is_codeowners_in_config()
        self.conn = ConnectionHandler(config_file=config_file)

    async def generate_codeowners(self):
        if not self.is_codeowners_in_config:
            return
        content = await self.generate_file_contents()
        filename = self.config.repo_configs[self.repo]['codeowners']['path'] + 'CODEOWNERS'
        sha = await self.get_branch_hash()
        await self.commit_codeowners(content, filename, sha)
        
    async def get_branch_hash(self):
        resp = await self.conn.get(f'/repos/{self.org}/{self.repo}/git/ref/heads/main')
        return resp['object']['sha']

    async def generate_file_contents(self):
        rules = ''
        for owner in self.config.repo_configs[self.repo]['codeowners']['owners']:
            rules += f'{owner["pattern"]}\t'
            if 'users' in owner:
                for u in owner['users']:
                    rules += f'@{u} '
            if 'teams' in owner:
                for t in owner['teams']:
                    rules += f'@{self.org}/{self.repo}-{t} '
            rules += '\n' 
        return self.base64_encode(rules)

    def __is_codeowners_in_config(self):
        if 'codeowners' in self.config.repo_configs[self.repo]:
            if 'path' in self.config.repo_configs[self.repo]['codeowners'] and 'owners' in self.config.repo_configs[self.repo]['codeowners']:
                return True
        return False

    async def commit_codeowners(self, content: str, path: str, sha: str):
        query = """
            mutation ($input: CreateCommitOnBranchInput!) {
                createCommitOnBranch(input: $input) {
                    commit {
                        url
                    }
                }
            }
        """
        variables = {
                    'input': {
                        'branch': {
                            'repositoryNameWithOwner': f'{self.org}/{self.repo}',
                            'branchName': 'main'
                        },
                        'message': {
                            'headline': f'GitGoat generated CODEOWNERS'
                        },
                        'fileChanges': {
                            'additions': [{
                                'path': path,
                                'contents': content
                            }]
                        },
                        "expectedHeadOid": sha
                    }
                }
        resp = await self.conn.post_graphql(query, variables, Config.get_pat())
        return resp

    def base64_encode(self, content = None):
        text = content if content is not None else self.fake.paragraph(nb_sentences=1)
        base64_bytes = base64.b64encode(text.encode('ascii'))
        return base64_bytes.decode('ascii')
    
