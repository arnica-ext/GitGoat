import os, stat, pathlib, time, logging
from src.connection import ConnectionHandler
from src.branch import Branch
from src.config import Config
from datetime import datetime, timedelta
from src.public_repo_map import IdentityMap
import pygit2

class Repository:
    
    def __init__(self, organization, config_file = None):
        self.org = organization
        self.endpoint = f'/orgs/{organization}/repos'
        self.config = Config() if config_file is None else Config(config_file)
        self.conn = ConnectionHandler(config_file=config_file)
        self.branch = Branch(organization)
        self.local_repos_path = os.path.join(pathlib.Path().resolve(),'local_repos')
        if os.path.isdir(self.local_repos_path):
            self.rmtree(self.local_repos_path)
        os.mkdir(self.local_repos_path)
        os.environ['GIT_SSL_NO_VERIFY'] = "1"
        self.identity_map = IdentityMap(config_file).map_authors()
        
    def rmtree(self, top):
        for root, dirs, files in os.walk(top, topdown=False):
            for name in files:
                filename = os.path.join(root, name)
                os.chmod(filename, stat.S_IWUSR)
                os.remove(filename)
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(top)
    
    async def delete_existing_repos(self):
        for repo in await self.get_all():
            if repo['name'] in self.config.repo_names or repo['name'] == 'GitGoat':
                await self.conn.delete(f'/repos/{self.org}/{repo["name"]}')
                logging.info(f"Deleted the repository {repo['name']}")

    async def get_all(self):
        return await self.conn.get(self.endpoint)

    async def create(self, name, auto_init = True):
        data = {
            'name': name,
            'private': True,
            'auto_init': auto_init
        }
        await self.conn.post(self.endpoint, json_data=data)
        
    async def delete(self, name):
        resp = await self.conn.get(self.endpoint)
        for repo in resp:
            if name == repo["name"]:
                await self.conn.delete(f'/repos/{self.org}/{repo["name"]}')
                return

    async def clone_public_repo(self, source_org, source_repo):
        local_repo_name = self.config.get_repo_name_by_public_repo(source_org, source_repo)
        await self.create(local_repo_name, auto_init=False)
        public_remote = f'https://github.com/{source_org}/{source_repo}.git'
        os_path = os.path.join(self.local_repos_path, self.org)
        repo = pygit2.clone_repository(url=public_remote, path=os.path.join(os_path, local_repo_name), bare=True)
        await self.replace_public_repo_commits(repo, local_repo_name)
        gitgoat_remote = repo.create_remote('dst', self.get_remote(local_repo_name, 'GitGoat', Config.get_pat()))
        try:
            gitgoat_remote.push(specs=[f'{repo.head.name}:refs/heads/main'])
            logging.info(f'Successfully pushed the {source_repo} code to {local_repo_name}')
        except Exception as ex:
            logging.warning(f'Unable to push the {source_repo} code to {local_repo_name}. Exception: {ex}')
    
    async def replace_public_repo_commits(self, repo, local_repo_name):
        email_to_login_map = self.config.get_email_to_login_map()
        mapped_authors = self.identity_map[local_repo_name] if local_repo_name in self.identity_map else {}
        last_commit_map = {}
        for member in self.config.members:
            for repo_config in member['days_since_last_commit']:
                if repo_config['repo'] == local_repo_name:
                    last_commit_map[member['email']] = repo_config['days']
        amended_commit = None
        for commit in repo.walk(repo.head.target.hex, pygit2.GIT_SORT_TIME):
            if commit.author is not None \
                and commit.author.email is not None \
                and commit.author.email in mapped_authors and \
                int((datetime.utcnow() - timedelta(last_commit_map[mapped_authors[commit.author.email]])).timestamp()) > commit.commit_time:
                    author = pygit2.Signature(name=email_to_login_map[mapped_authors[commit.author.email]], email=mapped_authors[commit.author.email], time=commit.commit_time, offset=commit.commit_time_offset)
                    amended_commit = repo.amend_commit(commit=commit, refname=None, author=author, committer=author)
            elif amended_commit is not None:
                amended_commit = repo.amend_commit(commit=commit, refname=None)
                    


    async def clone(self, repo_name, username, password, email, branch = 'main', retry = False):
        remote = self.get_remote(repo_name, username, password)
        os_path = os.path.join(self.local_repos_path, repo_name)
        if not os.path.isdir(os_path):
            os.mkdir(os_path)
        try: 
            if branch != 'main':
                sha = await self.branch.get_main(password, repo_name)
                create_branch = await self.branch.create_branch(password, repo_name, branch, sha)
            if not retry:
                repo = pygit2.clone_repository(url=remote, path=os.path.join(os_path, username), checkout_branch=branch)
            else:
                repo = pygit2.clone_repository(url=remote, path=os.path.join(os_path, username, 'retry'), checkout_branch=f'{branch}_retry')
            repo.config.set_multivar(name='user.name', regex='^user.name$', value=username)
            repo.config.set_multivar(name='user.email', regex='^user.name$', value=email)
        except Exception as ex:
            if not retry:
                logging.warning(f'Waiting 10 seconds before retrying to clone repo {repo_name} to branch {branch}. Exception: {ex}')
                time.sleep(10)
                return await self.clone(repo_name, username, password, email, branch, retry = True)
            else:
                logging.error(f'Failed cloning the repo  {repo_name} to branch {branch}. Exception: {ex}')
                return await self.clone(repo_name, username, password, email, 'main', retry = True)
        return repo
    
    def get_remote(self, repo_name, username, password):
        if 'api.github.com' in self.conn.base_url:
            return f'https://{username}:{password}@github.com/{self.org}/{repo_name}.git'
        url = self.conn.base_url.replace(f'/api/v3','').replace(f'https://','')
        return f'https://{username}:{password}@{url}/{self.org}/{repo_name}.git'

    def create_dir(self, os_path, username):
        if not os.path.isdir(os_path):
            os.mkdir(os_path)
        elif os.path.isdir(os.path.join(os_path, username)):
            self.rmtree(os.path.join(os_path, username))
        os.mkdir(os.path.join(os_path, username))