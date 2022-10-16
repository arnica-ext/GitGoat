import os, stat, pathlib, time, logging, subprocess
from datetime import datetime, timedelta
from src.connection import ConnectionHandler
from src.config import Config
import git, pygit2

class GitRemoteCallbacks(pygit2.RemoteCallbacks):

    def transfer_progress(self, stats):
        print(f'{stats.indexed_objects}/{stats.total_objects}')


class IdentityMap:
    
    def __init__(self, config_file = None):
        self.config = Config() if config_file is None else Config(config_file)
        self.conn = ConnectionHandler(config_file=config_file)
        self.local_repos_path = os.path.join(pathlib.Path().resolve(),'local_repos')
        #if os.path.isdir(self.local_repos_path):
        #    self.rmtree(self.local_repos_path)
        if not os.path.isdir(self.local_repos_path):
            os.mkdir(self.local_repos_path)
        public_clones_path = os.path.join(self.local_repos_path,'public_clones')
        if not os.path.isdir(public_clones_path):
            os.mkdir(public_clones_path)
        os.environ['GIT_SSL_NO_VERIFY'] = "1"
        self.members_activity_config = self.get_members_activity_config()
        self.repos_map = self.config.repo_names_mapping_to_public_repos
        self.earliest_commit = int((datetime.utcnow() - timedelta(180)).timestamp())
        self.max_mapped_contributors = 10
    
    def rmtree(self, top):
        for root, dirs, files in os.walk(top, topdown=False):
            for name in files:
                filename = os.path.join(root, name)
                os.chmod(filename, stat.S_IWUSR)
                os.remove(filename)
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(top)
    
    def get_members_activity_config(self):
        map = {}
        for member in self.config.members:
            if 'days_since_last_commit' in member:
                for setting in member['days_since_last_commit']:
                    if setting['repo'] not in map:
                        map[setting['repo']] = []
                    map[setting['repo']].append({'email': member['email'], 'days_since_last_commit': setting['days']})
        return map
    
    async def map_authors(self):
        map = {}
        for repo in self.repos_map:
            map[repo] = {}
            members_metadata = await self.get_members_from_public_repo(self.repos_map[repo]['org'], self.repos_map[repo]['repo'])
            for member in self.members_activity_config[repo]:
                map[repo][member['email']] = members_metadata.pop()
        print(map)
        return map
    
    async def get_members_from_public_repo(self, organization, repository):
        members_metadata = {}
        repo = await self.clone_public_repo(organization, repository)
        last = repo[repo.head.target]
        for commit in repo.walk(last.id, pygit2.GIT_SORT_TIME):
            if self.earliest_commit > commit.commit_time:
                break
            if len(commit.parent_ids) > 1: # Merge commits
                continue
            if commit.author is not None and commit.author.email is not None:
                if commit.author.email not in members_metadata:
                    members_metadata[commit.author.email] = 0
                members_metadata[commit.author.email] += 1
        return self.get_top_contributors(members_metadata)

    def get_top_contributors(self, members_metadata):
        top_contributors = []
        members = members_metadata.copy()
        for _ in range(self.max_mapped_contributors):
            if len(members) > 0:
                top_contributor = max(members, key=members.get)
                top_contributors.append(top_contributor)
                members[top_contributor] = 0
        return top_contributors
            

    async def clone_public_repo(self, organization, repository):
        remote = f'https://github.com/{organization}/{repository}.git'
        os_path = os.path.join(self.local_repos_path, 'public_repos', f'{organization}-{repository}')
        if os.path.isdir(os_path):
            subprocess.run(['git', '-C', os_path, 'pull'])
        else:
            logging.info('This is the fist time the repository is cloned, so it may take longer than next times.')
            subprocess.run(['git', 'clone', remote, os_path])   
        return pygit2.Repository(os_path)

    
