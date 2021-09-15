from src.connection import ConnectionHandler

class Branch:

    def __init__(self, organization, config_file = None):
        self.endpoint = f'/repos/{organization}/[REPO]/git/refs'
        self.config_file = config_file

    async def get_main(self, pat, repository):
        conn = ConnectionHandler(pat, self.config_file)
        endpoint = self.endpoint.replace('[REPO]', repository) + '/heads/main'
        resp = await conn.get(endpoint)
        return resp['object']['sha']

    async def create_branch(self, pat, repository, branch_name, source_branch_sha):
        conn = ConnectionHandler(pat, self.config_file)
        endpoint = self.endpoint.replace('[REPO]', repository)
        data = {
            'ref': 'refs/heads/' + branch_name,
            'sha': source_branch_sha
        }
        resp = await conn.post(endpoint, json_data=data)
        return resp
      