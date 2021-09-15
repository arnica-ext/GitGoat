import asyncio, logging, sys
from src.config import Config
from src.repository import Repository
from src.teams import Team
from src.actions import Actions
from src.commit import Commit
from src.members import Membership
from src.pull_request import PullRequest

async def mock(config_file: str, orgs: list = []):
    config = Config() if config_file is None else Config(config_file)
    org_names = orgs if len(orgs) > 0 else config.org_names
    for org in org_names:
        logging.info('----- Creating Repos -----')
        await create_repos(config, org)
        logging.info('----- Setting up Actions configurations -----')
        await setup_actions(config, org)
        logging.info('----- Creating Teams -----')
        await create_teams(config, org)
        logging.info('----- Inviting Members -----')
        await invite_members(config, org)
        logging.info('----- Members accepting invitations -----')
        await accept_invitations(config, org)
        logging.info('----- Creating Commits and Pull Requests -----')
        await create_commits(config, org)
        logging.info('----- Merging Pull Requests -----')
        await merge_pull_requests(config, org)

async def create_repos(config, org):
    r = Repository(org, config.filename) 
    for repo_name in config.repo_names:
        await r.create(repo_name)
        logging.info(f'Created repository {repo_name} in org {org}.')
    
async def create_teams(config, org):
    t = Team(org, config.filename)
    for repo in config.teams:
        for gp in repo['group_postfixes']:
            await t.create(f'{repo["repo"]}-{gp}', [f'{org}/{repo["repo"]}'])
            await t.add_repository_permission(f'{repo["repo"]}-{gp}', f'{org}/{repo["repo"]}', gp)
            logging.info(f'Created the team {repo["repo"]}-{gp} and added the permission {gp} to repo {org}/{repo["repo"]}')
            for member in config.members:
                if (f'{repo["repo"]}-{gp}' in member['member_of_groups']):
                    await t.add_member(f'{repo["repo"]}-{gp}',member['login'])

async def invite_members(config, org):
    m = Membership(org, config.filename)
    await m.invite_members()

async def accept_invitations(config, org):
    m = Membership(org, config.filename)
    for member in config.members:
        token =  member['token'] if 'ghp_' in member['token'] else 'ghp_' + member['token']
        await m.accept_invitation_to_org(token)
        logging.info(f'The user {member["login"]} accepted the invitation to join {org}')

async def setup_actions(config, org):
    a = Actions(org, config.filename)
    await a.enable_selected_repositories_in_org()
    r = Repository(org, config.filename)
    repo_mapping = {}
    for repo in await r.get_all():
        repo_mapping[repo['name']] = repo['id']
    actions_enabled_repo_ids = []
    actions_enabled_repo_names = []
    for repo_name in config.repo_configs:
        if 'actions_enabled' in config.repo_configs[repo_name]:
            if config.repo_configs[repo_name]['actions_enabled']:
                actions_enabled_repo_ids.append(repo_mapping[repo_name])
                actions_enabled_repo_names.append(repo_name)
    await a.enable_selected_repository_ids_in_org(actions_enabled_repo_ids)
    for actions_enabled_repo in actions_enabled_repo_names:
        await a.enable_actions_in_repo(actions_enabled_repo, allowed_actions=config.repo_configs[actions_enabled_repo]['allowed_actions'])
        if config.repo_configs[actions_enabled_repo]['allowed_actions'] == 'selected':
            await a.enable_selected_actions_in_repo(actions_enabled_repo, verified_allowed=config.repo_configs[actions_enabled_repo]['verified_allowed_actions'])

async def create_commits(config, org):
    r = Repository(org, config.filename)
    pr = PullRequest(org, config.filename)
    for member in config.members:
        for commit_details in member['days_since_last_commit']:
            token =  member['token'] if 'ghp_' in member['token'] else 'ghp_' + member['token']
            repo = await r.clone(commit_details['repo'], member['login'], token, member['email'], commit_details['branch'])
            c = Commit(repo)
            c.generate_commits(200, commit_details['days'])
            if commit_details['create_pr']:
                await pr.create_pull_request(token, commit_details['repo'], commit_details['branch'])
                logging.info(f'Created a PR by {member["login"]} from branch {commit_details["branch"]}')

async def merge_pull_requests(config, org):
    pr = PullRequest(org, config.filename)
    for member in config.members:
        for repo in config.repo_names:
            if f'{repo}-triage' in member['member_of_groups'] or f'{repo}-maintain' in member['member_of_groups']:
                token =  member['token'] if 'ghp_' in member['token'] else 'ghp_' + member['token']
                prs = await pr.get_pull_requests(token,repo)
                for p in prs:
                    merged = await pr.merge(token, repo, p)
                    if merged: 
                        logging.info(f'Merged the PR id {p} in repository {repo} by {member["login"]}')
                    else:
                        logging.warning(f'Did NOT merge the PR id {p} in repository {repo} by {member["login"]}')


if __name__ == '__main__':
    try:
        if sys.argv[sys.argv.index("--config")+1].startswith('--'):
            raise 
        config_file = sys.argv[sys.argv.index("--config")+1]
        logging.info(f'Custom config file is set to {config_file}')
    except:
        config_file = 'config.yaml'
    try:
        if sys.argv[sys.argv.index("--org")+1].startswith('--'):
            raise
        org = [sys.argv[sys.argv.index("--org")+1]]
        logging.info(f'Custom organization is set to {org[0]}')
    except:
        org = []
    asyncio.run(mock(config_file=config_file, orgs=org))
    
