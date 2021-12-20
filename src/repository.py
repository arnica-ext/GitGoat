import os, stat, pathlib, time, logging
from src.connection import ConnectionHandler
from src.branch import Branch
from src.config import Config
import git

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

    async def create(self, name):
        data = {
            'name': name,
            'private': True,
            'auto_init': True
        }
        await self.conn.post(self.endpoint, json_data=data)
        
    async def delete(self, name):
        resp = await self.conn.get(self.endpoint)
        for repo in resp:
            if name == repo["name"]:
                await self.conn.delete(f'/repos/{self.org}/{repo["name"]}')
                return
            
    async def clone_gitgoat(self):
        await self.create('GitGoat')
        gitgoat_remote = 'https://github.com/arnica-ext/GitGoat.git'
        os_path = os.path.join(self.local_repos_path, self.org)
        repo = git.Repo.clone_from(gitgoat_remote, os.path.join(os_path, 'GitGoat'))
        remote = repo.create_remote('dst', self.get_remote('GitGoat', 'GitGoat', Config.get_pat()))
        try:
            remote.push(refspec=f'main:main', force=True)
            logging.info(f'Successfully pushed the GitGoat code from {repo.common_dir}')
        except Exception as ex:
            logging.warning(f'Unable to push the GitGoat code from {repo.common_dir}. Exception: {ex}')

    async def clone(self, repo_name, username, password, email, branch = 'main', retry = False):
        remote = self.get_remote(repo_name, username, password)
        os_path = os.path.join(self.local_repos_path, repo_name)
        self.create_dir(os_path, username)
        try: 
            if branch != 'main':
                sha = await self.branch.get_main(password, repo_name)
                await self.branch.create_branch(password, repo_name, branch, sha)
            if not retry:
                repo = git.Repo.clone_from(remote, os.path.join(os_path, username) , branch=branch)
            else:
                repo = git.Repo.clone_from(remote, os.path.join(os_path, username, 'retry') , branch=f'{branch}_retry')
            repo.config_writer().set_value("user", "name", username).release()
            repo.config_writer().set_value("user", "email", email).release()
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