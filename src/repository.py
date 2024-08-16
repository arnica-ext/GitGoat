import os, stat, pathlib, time, logging
from src.connection import ConnectionHandler
from src.branch import Branch
from src.config import Config
from datetime import datetime, timedelta
from src.public_repo_map import IdentityMap
from datetime import datetime
import pygit2, subprocess

class Repository:
    
    AMENDED_BRANCH = 'amended'
    
    def __init__(self, organization, config_file = None):
        self.org = organization
        self.endpoint = f'/orgs/{organization}/repos'
        self.config = Config() if config_file is None else Config(config_file)
        self.conn = ConnectionHandler(config_file=config_file)
        self.branch = Branch(organization)
        # self.cleanup_local_repos()
        self.local_repos_path = os.path.join(pathlib.Path().resolve(),'local_repos')
        if not os.path.isdir(self.local_repos_path):
            os.mkdir(self.local_repos_path)
        os.environ['GIT_SSL_NO_VERIFY'] = "1"
        self.identity_map = IdentityMap(config_file).map_authors()
    
    # def cleanup_local_repos(self):
    #     self.local_repos_path = os.path.join(pathlib.Path().resolve(),'local_repos')
    #     if os.path.isdir(self.local_repos_path):
    #         self.rmtree(self.local_repos_path)
    #     os.mkdir(self.local_repos_path)
        
    # def rmtree(self, top):
    #     for root, dirs, files in os.walk(top, topdown=False):
    #         for name in files:
    #             try:
    #                 filename = os.path.join(root, name)
    #                 os.chmod(filename, stat.S_IWUSR)
    #                 os.remove(filename)
    #             except:
    #                 os.remove(filename)
    #         for name in dirs:
    #             try:
    #                 os.rmdir(os.path.join(root, name))
    #             except:
    #                 continue
    #     os.rmdir(top)
    
    async def delete_existing_repos(self):
        for repo in await self.get_all():
            if repo['name'] in self.config.repo_names or repo['name'] == 'GitGoat':
                await self.conn.delete(f'/repos/{self.org}/{repo["name"]}')
                logging.info(f"Deleted the repository {repo['name']}")

    async def get_all(self):
        repos = await self.conn.get(self.endpoint)
        return repos

    async def create(self, name, auto_init = False):
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

    async def clone_public_repo(self, source_org, source_repo, retry_attempts = 3):
        local_repo_name = self.config.get_repo_name_by_public_repo(source_org, source_repo)
        repo_path = os.path.join(self.local_repos_path, local_repo_name)
        if os.path.isdir(repo_path):
            repo = pygit2.Repository(f'{repo_path}', flags=pygit2.GIT_REPOSITORY_OPEN_BARE)
            remote_name = f'dst-{int(datetime.now().timestamp())}'
            local_default_branch = Repository.get_local_default_branch(repo_path)
            await self.replace_public_repo_commits(repo, local_repo_name)
            gitgoat_remote = repo.create_remote(remote_name, self.get_remote(local_repo_name, 'GitGoat', Config.get_pat()))
            try:
                logging.debug(f'Trying to push the {source_repo} code to {local_repo_name}')                
                subprocess.run(['git', '-C', repo_path, 'push', gitgoat_remote.name, f'+{Repository.AMENDED_BRANCH}:{local_default_branch}'])
                subprocess.run(['git', '-C', repo_path, 'remote', 'remove', gitgoat_remote.name])
                #gitgoat_remote.push(specs=[f'+refs/heads/{Repository.AMENDED_BRANCH}:refs/heads/main'])
                logging.debug(f'Successfully pushed the {source_repo} code to {local_repo_name}')
                #gitgoat_remote.prune()
            except Exception as ex:
                subprocess.run(['git', '-C', repo_path, 'remote', 'remove', gitgoat_remote.name])
                logging.warning(f'Unable to push the TAMPERED {source_repo} code to {local_repo_name}. Exception: {ex}')
            return 
        public_remote = f'https://github.com/{source_org}/{source_repo}.git'
        default_branch = await self.conn.get(f'/repos/{source_org}/{source_repo}')
        default_branch = default_branch['default_branch']
        try:
            repo = pygit2.clone_repository(url=public_remote, path=repo_path, bare=True)
        except Exception as ex:
            if retry_attempts >= 0:
                logging.warning(f'Could not clone the repo {source_repo}. Remaining retry attempts: {retry_attempts - 1}. Error: {ex}.')
                await self.clone_public_repo(source_org, source_repo, retry_attempts - 1)
            return
        local_default_branch = Repository.get_local_default_branch(repo_path)
        await self.replace_public_repo_commits(repo, local_repo_name)
        gitgoat_remote = repo.create_remote('dst', self.get_remote(local_repo_name, 'GitGoat', Config.get_pat()))
        try:
            logging.debug(f'Trying to push the {source_repo} code to {local_repo_name}')
            subprocess.run(['git', '-C', repo_path, 'push', gitgoat_remote.name, f'+{Repository.AMENDED_BRANCH}:{local_default_branch}'])
            #gitgoat_remote.push(specs=[f'+refs/heads/{Repository.AMENDED_BRANCH}:refs/heads/main'])
            logging.debug(f'Successfully pushed the {source_repo} code to {local_repo_name}')
            subprocess.run(['git', '-C', repo_path, 'remote', 'remove', gitgoat_remote.name])
        except Exception as ex:
            subprocess.run(['git', '-C', repo_path, 'remote', 'remove', gitgoat_remote.name])
            logging.warning(f'Unable to push the TAMPERED {source_repo} code to {local_repo_name}. Exception: {ex}')
    
    
    def get_local_default_branch(repo_path, remote_name='origin'):
        try:
            result = subprocess.run(['git', '-C', repo_path, 'remote', 'show', remote_name], capture_output=True, text=True, check=True)
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if 'HEAD branch' in line:
                    return line.split(':')[-1].strip()
        except subprocess.CalledProcessError as e:
            print(f"Error executing git command: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
        return 'main'
    
    
    async def replace_public_repo_commits(self, repo, local_repo_name):
        email_to_login_map = self.config.get_email_to_login_map()
        mapped_authors = self.identity_map[local_repo_name] if local_repo_name in self.identity_map else {}
        last_commit_map = {}
        for member in self.config.members:
            for repo_config in member['days_since_last_commit']:
                if repo_config['repo'] == local_repo_name:
                    last_commit_map[member['email']] = repo_config['days']
        Repository.amend_repo(repo, mapped_authors, email_to_login_map, last_commit_map)
        return True

    def amend_repo(repo: pygit2.Repository, mapped_authors, email_to_login_map, last_commit_map):
        ref = None
        for commit in repo.walk(repo.head.target.hex, pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_REVERSE):
            if commit.author is not None \
                and commit.author.email is not None \
                and commit.author.email in mapped_authors and \
                int((datetime.utcnow() - timedelta(last_commit_map[mapped_authors[commit.author.email]])).timestamp()) > commit.commit_time:
                    if ref is None:
                        try:
                            ref = repo.branches.local.create(Repository.AMENDED_BRANCH, commit)
                        except Exception as ex:
                            logging.warning(f'Failed to create branch {Repository.AMENDED_BRANCH}. Exception: {ex}')
                            return 
                        continue
                    author = pygit2.Signature(name=email_to_login_map[mapped_authors[commit.author.email]], email=mapped_authors[commit.author.email], time=commit.commit_time, offset=commit.commit_time_offset)
                    Repository.cherrypick(repo, commit, author, author)
            elif ref is not None:
                    Repository.cherrypick(repo, commit, commit.author, commit.committer) 
    
    def cherrypick(repo: pygit2.Repository, cherry: pygit2.Commit, author: pygit2.Signature, committer: pygit2.Signature):
        basket = repo.branches.get(Repository.AMENDED_BRANCH)
        base = repo.merge_base(basket.target, cherry.id)
        if base.hex in [parent.hex for parent in cherry.parents]:
            index = repo.merge_trees(base, basket, cherry, favor='theirs')
        else:
            index = repo.merge_trees(repo[basket.target].parents[0], basket, cherry, favor='theirs')
        if index.conflicts is not None:
            for conflict in index.conflicts:
                try:
                    index_entry = Repository.select_merge_resolution(conflict)
                    if index_entry is None:
                        continue
                    index.read_tree(index_entry.id)
                    index.add(index_entry)
                except KeyError as ex:
                    return
        tree_id = index.write_tree()
        repo.create_commit(basket.name, author, committer, cherry.message,tree_id, [basket.target])
    
    def select_merge_resolution(conflict: pygit2.IndexEntry):
        if conflict[2] is not None:
            return conflict[2]
        elif conflict[1] is not None:
            return conflict[1]
        return None
                
    async def clone(self, repo_name, username, password, email, branch = 'main', retry = False):
        remote = self.get_remote(repo_name, username, password)
        os_path = os.path.join(self.local_repos_path, repo_name)
        if not os.path.isdir(os_path):
            os.mkdir(os_path)
        try: 
            if branch != 'main' and not retry:
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