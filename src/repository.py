import os, stat, pathlib, time
from src.connection import ConnectionHandler
from src.branch import Branch
import git


class Repository:
    
    def __init__(self, organization, config_file = None):
        self.org = organization
        self.endpoint = f'/orgs/{organization}/repos'
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

    async def get_all(self):
        return await self.conn.get(self.endpoint)

    async def create(self, name):
        await self.delete(name)
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

    async def clone(self, repo_name, username, password, email, branch = 'main'):
        if 'api.github.com' in self.conn.base_url:
            remote = f'https://{username}:{password}@github.com/{self.org}/{repo_name}.git'
        else:
            url = self.conn.base_url.replace(f'/api/v3','').replace(f'https://','')
            remote = f'https://{username}:{password}@{url}/{self.org}/{repo_name}.git'
        os_path = os.path.join(self.local_repos_path, repo_name)
        if not os.path.isdir(os_path):
            os.mkdir(os_path)
        os.mkdir(os.path.join(os_path, username))
        if branch != 'main':
            sha = await self.branch.get_main(password, repo_name)
            await self.branch.create_branch(password, repo_name, branch, sha)
            time.sleep(3)
        repo = git.Repo.clone_from(remote, os.path.join(os_path, username) , branch=branch)
        repo.config_writer().set_value("user", "name", username).release()
        repo.config_writer().set_value("user", "email", email).release()
        return repo