
from src.connection import ConnectionHandler

class DirectPermission:

    def __init__(self, organization, config_file = None):
        self.org = organization
        self.endpoint = f'/repos/{organization}/[REPO]/collaborators/[USERNAME]'
        self.conn = ConnectionHandler(config_file=config_file)

    async def create(self, name, repo_names = []):
        await self.delete(name)
        data = {
            'name': name,
            'repo_names': repo_names,
            'privacy': 'secret'
        }
        resp = await self.conn.post(self.endpoint, json_data=data)
        return resp
    
    # Permission parameter options: pull, push, admin, maintain, triage
    async def add_repository_permission(self, repo_name, member, permission):
        endpoint = self.endpoint.replace('[REPO]',repo_name).replace('[USERNAME]',member)
        data = {
            'permission': permission
        }
        resp = await self.conn.put(endpoint, data)
        return resp
