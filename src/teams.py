
from src.connection import ConnectionHandler

class Team:

    def __init__(self, organization, config_file = None):
        self.org = organization
        self.endpoint = f'/orgs/{organization}/teams'
        self.conn = ConnectionHandler(config_file=config_file)

    async def create(self, name, repo_names = [], parent_team = None):
        data = {
            'name': name,
            'repo_names': repo_names,
            'privacy': 'closed'
        }
        if parent_team is not None:
            data['parent_team_id'] = parent_team
        resp = await self.conn.post(self.endpoint, json_data=data)
        return resp['slug'], resp['id']
    
    async def get(self, slug):
        resp = await self.conn.get(f'{self.endpoint}/{slug}')
        return resp['id']

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
        
    async def delete(self):
        teams = await self.conn.get(f'/orgs/{self.org}/teams')
        for team in teams:
            await self.conn.delete(f'/orgs/{self.org}/teams/{team["slug"]}')
