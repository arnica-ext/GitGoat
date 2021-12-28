import asyncio, logging, sys
from tqdm import tqdm
from src.config import Config
from src.repository import Repository
from src.teams import Team
from src.actions import Actions
from src.commit import Commit
from src.members import Membership
from src.pull_request import PullRequest
from src.direct_permissions import DirectPermission
from src.branch import Branch
from src.codeowners import CodeOwners

async def mock(config_file: str, orgs: list = []):
    config = Config() if config_file is None else Config(config_file)
    org_names = orgs if len(orgs) > 0 else config.org_names
    for org in org_names:
        logging.info(f'----- Organization: {org} -----')
        logging.info('----- Creating Repos -----')
        await create_repos(config, org)
        logging.info('----- Setting up Actions configurations -----')
        await setup_actions(config, org)
        logging.info('----- Inviting Members -----')
        await invite_members(config, org)
        logging.info('----- Members accepting invitations -----')
        await accept_invitations(config, org)
        logging.info('----- Creating Teams -----')
        await create_teams(config, org)
        logging.info('----- Granting Direct Permissions -----')
        await add_direct_permissions(config, org)
        logging.info('----- Configuring Branch Protection -----')
        await configure_branch_protection(config, org)
        logging.info('----- Configuring CODEOWNERS -----')
        await configure_codeowners(config, org)
        logging.info('----- Creating Commits and Pull Requests -----')
        await create_commits(config, org)
        logging.info('----- Reviewing Pull Requests -----')
        await review_pull_requests(config, org)
        logging.info('----- Merging Pull Requests -----')
        await merge_pull_requests(config, org)

async def create_repos(config, org):
    r = Repository(org, config.filename) 
    await r.delete_existing_repos()
    for repo_name in tqdm(config.repo_names, desc='Repos'):
        await r.create(repo_name)
    logging.info(f'Cloning GitGoat and pushing to org {org}.')
    await r.clone_gitgoat()
    
async def create_teams(config, org):
    t = Team(org, config.filename)
    for repo in tqdm(config.teams, desc='Teams'):
        for gp in repo['group_postfixes']:
            await t.create(f'{repo["repo"]}-{gp}', [f'{org}/{repo["repo"]}'])
            await t.add_repository_permission(f'{repo["repo"]}-{gp}', f'{org}/{repo["repo"]}', gp)
            for member in config.members:
                if (f'{repo["repo"]}-{gp}' in member['member_of_groups']):
                    await t.add_member(f'{repo["repo"]}-{gp}',member['login'])

async def invite_members(config, org):
    m = Membership(org, config.filename)
    await m.invite_members()

async def accept_invitations(config, org):
    m = Membership(org, config.filename)
    for member in tqdm(config.members, desc='Members'):
        token =  member['token'] if 'ghp_' in member['token'] else 'ghp_' + member['token']
        await m.accept_invitation_to_org(token)

async def add_direct_permissions(config, org):
    dp = DirectPermission(org, config.filename)
    for member in tqdm(config.members, desc='Direct Permission'):
        if 'gitgoat_repo_permission' in member:
            await dp.add_repository_permission('GitGoat',member['login'],member['gitgoat_repo_permission'])

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
    for actions_enabled_repo in tqdm(actions_enabled_repo_names, desc='Actions'):
        await a.enable_actions_in_repo(actions_enabled_repo, allowed_actions=config.repo_configs[actions_enabled_repo]['allowed_actions'])
        if config.repo_configs[actions_enabled_repo]['allowed_actions'] == 'selected':
            await a.enable_selected_actions_in_repo(actions_enabled_repo, verified_allowed=config.repo_configs[actions_enabled_repo]['verified_allowed_actions'])

async def configure_codeowners(config, org):
    r = Repository(org, config.filename)
    for repo_name in tqdm(config.repo_names, desc='CODEOWNERS'):
        repo = await r.clone(repo_name, 'GitGoat', Config.get_pat(), 'GitGoat@gitgoat.tools')
        co = CodeOwners(org,repo_name, repo, config.filename)
        filename = await co.generate_file()
        await co.push_file(filename)

async def configure_branch_protection(config, org):
    b = Branch(org, config.filename)
    for repo_name in tqdm(config.repo_names, desc='Branch Protection'):
        if 'branch_protection_restirctions' in config.repo_configs[repo_name]:
            users = config.repo_configs[repo_name]['branch_protection_restirctions']['users']
            teams = []
            for team_postfix in config.repo_configs[repo_name]['branch_protection_restirctions']['teams']:
                teams.append(f'{repo_name}-{team_postfix}')
            enforce_admins = config.repo_configs[repo_name]['branch_protection_restirctions']['enforce_admins']
            require_code_owner_reviews = config.repo_configs[repo_name]['branch_protection_restirctions']['require_code_owner_reviews']
            await b.set_branch_protection(repo_name, 'main', enforce_admins, require_code_owner_reviews, users, teams)

async def create_commits(config, org):
    r = Repository(org, config.filename)
    pr = PullRequest(org, config.filename)
    for member in config.members:
        token =  member['token'] if 'ghp_' in member['token'] else 'ghp_' + member['token']
        for commit_details in tqdm(member['days_since_last_commit'], desc=f'Commits for {member["login"]}'):
            repo = await r.clone(commit_details['repo'], member['login'], token, member['email'], commit_details['branch'])
            c = Commit(repo)
            c.generate_commits(25, commit_details['days'])
            if commit_details['create_pr']:
                await pr.create_pull_request(token, commit_details['repo'], commit_details['branch'])

async def review_pull_requests(config, org):
    pr = PullRequest(org, config.filename)
    pr_reviews_map = await get_pr_reviews_map(pr, config)
    for member in tqdm(config.members, desc=f'Members Review PRs'):
        token =  member['token'] if 'ghp_' in member['token'] else 'ghp_' + member['token']
        for repo in config.repo_names:
            member_reviewed_prs_of_login = []
            prs = await pr.get_pull_requests(token,repo)
            if is_member_codeowner(config, member, repo):
                for p in prs:
                    if prs[p] != member['login'] and prs[p] not in member_reviewed_prs_of_login and not pr_reviews_map[repo][p]:
                        await pr.review(token, repo, p)
                        pr_reviews_map[repo][p] = True
                        member_reviewed_prs_of_login.append(prs[p])
            elif can_members_review(config, repo):
                for p in prs:
                    if prs[p] != member['login'] and not pr_reviews_map[repo][p]:
                        await pr.review(token, repo, p)
                        pr_reviews_map[repo][p] = True
                        member_reviewed_prs_of_login.append(prs[p])
    await review_pull_requests_by_owner(pr_reviews_map, pr)

async def review_pull_requests_by_owner(pr_reviews_map, pr):
    for repo in tqdm(pr_reviews_map, desc=f'Owner Reviews PRs'):
        for pr_id in pr_reviews_map[repo]:
            if not pr_reviews_map[repo][pr_id]:
                await pr.review(Config.get_pat(), repo, pr_id)

async def get_pr_reviews_map(pr, config):
    pr_reviews_map = {}
    for repo in config.repo_names:
        pr_reviews_map[repo] = {}
        for pr_id in await pr.get_pull_requests(Config.get_pat(),repo):
            pr_reviews_map[repo][pr_id] = False
    return pr_reviews_map

async def merge_pull_requests(config, org):
    pr = PullRequest(org, config.filename)
    for member in tqdm(config.members, desc=f'Members Merge PRs'):
        for repo in config.repo_names:
            token =  member['token'] if 'ghp_' in member['token'] else 'ghp_' + member['token']
            if is_member_allowed_to_merge(config, member, repo):
                prs = await pr.get_pull_requests(token,repo)
                for p in prs:
                    merged = await pr.merge(token, repo, p)
                    if not merged: 
                        logging.warning(f'Did NOT merge the PR id {p} in repository {repo} by {member["login"]}')

def can_members_review(config, repo):
    if 'branch_protection_restirctions' in config.repo_configs[repo] and 'require_code_owner_reviews' in config.repo_configs[repo]['branch_protection_restirctions'] and not config.repo_configs[repo]['branch_protection_restirctions']['require_code_owner_reviews']:
        return True
    return False

def is_member_codeowner(config, member, repo):
    if 'codeowners' in config.repo_configs[repo] and 'owners' in config.repo_configs[repo]['codeowners']:
        for owner in config.repo_configs[repo]['codeowners']['owners']:
            for u in owner['users']:
                if u == member:
                    return True
            for t in owner['teams']:
                for m in config.members:
                    if m['login'] == member['login'] and f'{repo}-{t}' in m['member_of_groups']:
                        return True
    return False

def is_member_allowed_to_merge(config, member, repo):
    if 'branch_protection_restirctions' in config.repo_configs[repo]:
        if member['login'] in config.repo_configs[repo]['branch_protection_restirctions']['users']:
            return True
        for team in config.repo_configs[repo]['branch_protection_restirctions']['teams']:
            for group_membership in member['member_of_groups']:
                if group_membership == f'{repo}-{team}':
                    return True
    else:
        if f'{repo}-maintain' in member['member_of_groups'] or f'{repo}-push' in member['member_of_groups']:
            return True
    return False

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
    
