from build import logging
from src.connection import ConnectionHandler

class Branch:

    def __init__(self, organization, config_file = None):
        self.endpoint = f'/repos/{organization}/[REPO]/git/refs'
        self.branch_protection_endpoint = f'/repos/{organization}/[REPO]/branches/[BRANCH]/protection'
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
    
    async def set_branch_protection(self, repository, branch_name, enforce_admins = False, require_code_owner_reviews = False, restricted_users = [], restricted_teams = []):
        conn = ConnectionHandler(config_file=self.config_file)
        endpoint = self.branch_protection_endpoint.replace('[REPO]',repository).replace('[BRANCH]', branch_name)
        payload = {
            'required_status_checks': {
                'strict': False,
                'contexts': []
            },
            'enforce_admins': enforce_admins,
            'required_pull_request_reviews': {
                'required_approving_review_count': 1,
                'require_code_owner_reviews': require_code_owner_reviews
            },
            'allow_force_pushes': True,
            'allow_deletions': True,
            'restrictions': None
        }
        if len(restricted_users) > 0 or len(restricted_teams) > 0:
            identities_payload = {
                'users': restricted_users,
                'teams': restricted_teams
            }
            payload['restrictions'] = identities_payload
            payload['bypass_pull_request_allowances'] = identities_payload
        else:
            logging.info(f'No users and teams are defined in the repository {repository}')
        resp = await conn.put(endpoint, payload)
        return resp
      