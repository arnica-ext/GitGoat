
from src.connection import ConnectionHandler

class Team:

    def __init__(self, organization, config_file = None):
        self.org = organization
        self.endpoint = f'/orgs/{organization}/teams'
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
    
    async def add_member(self, team_name, member):
        endpoint = f'/orgs/{self.org}/teams/{team_name}/memberships/{member}'
        data = {
            'role': 'member'
        }
        resp = await self.conn.put(endpoint, data)
        return resp

    # Permission parameter options: pull, push, admin, maintain, triage
    async def add_repository_permission(self, team_name, repo_name, permission):
        endpoint = f'/orgs/{self.org}/teams/{team_name}/repos/{repo_name}'
        data = {
            'permission': permission
        }
        resp = await self.conn.put(endpoint, data)
        return resp
        
    async def delete(self, name):
        await self.conn.delete(f'/orgs/{self.org}/teams/{name}')
