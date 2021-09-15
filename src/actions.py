from src.connection import ConnectionHandler

class Actions:

    def __init__(self, organization, config_file = None):
        self.orgs_endpoint = f'/orgs/{organization}/actions/permissions'
        self.repos_endpoint = f'/repos/{organization}/[REPO]/actions/permissions'
        self.conn = ConnectionHandler(config_file=config_file)

    async def enable_selected_repositories_in_org(self):
        data = {
            'enabled_repositories': 'selected'
        }
        resp = await self.conn.put(self.orgs_endpoint, json_data=data)
        return resp
    
    # Make sure the repo identifiers are used as an input and not the repo names.
    async def enable_selected_repository_ids_in_org(self, repo_ids = []):
        data = {
            'selected_repository_ids': repo_ids
        }
        resp = await self.conn.put(self.orgs_endpoint + f'/repositories', json_data=data)
        return resp

    # The following allowed_actions are available: 'all', 'local_only', or 'selected'
    async def enable_actions_in_repo(self, repo, allowed_actions = 'selected'):
        data = {
            'enabled': True,
            'allowed_actions': allowed_actions
        }
        resp = await self.conn.put(self.repos_endpoint.replace('[REPO]', repo), json_data=data)
        return resp
    

    async def enable_selected_actions_in_repo(self, repo, verified_allowed = True):
        data = {
            'github_owned_allowed': True,
            'verified_allowed': verified_allowed
        }
        resp = await self.conn.put(self.repos_endpoint.replace('[REPO]', repo) + f'/selected-actions', json_data=data)
        return resp

      