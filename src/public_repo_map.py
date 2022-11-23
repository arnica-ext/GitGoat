import os, pathlib, logging, subprocess
from datetime import datetime, timedelta
from src.connection import ConnectionHandler
from src.config import Config
import pygit2

class IdentityMap:
    
    def __init__(self, config_file = None):
        self.config = Config() if config_file is None else Config(config_file)
        self.conn = ConnectionHandler(config_file=config_file)
        self.local_repos_path = os.path.join(pathlib.Path().resolve(),'public_repos')
        if not os.path.isdir(self.local_repos_path):
            os.mkdir(self.local_repos_path)
        os.environ['GIT_SSL_NO_VERIFY'] = "1"
        self.members_activity_config = self.get_members_activity_config()
        self.repos_map = self.config.repo_names_mapping_to_public_repos
        self.earliest_commit = int((datetime.utcnow() - timedelta(1800)).timestamp())
        self.max_mapped_contributors = 10
    
    def get_members_activity_config(self):
        map = {}
        for member in self.config.members:
            if 'days_since_last_commit' in member:
                for setting in member['days_since_last_commit']:
                    if setting['repo'] not in map:
                        map[setting['repo']] = []
                    map[setting['repo']].append({'email': member['email'], 'days_since_last_commit': setting['days']})
        return map
    
    def map_authors(self):
        map = {}
        for repo in self.repos_map:
            map[repo] = {}
            members_metadata = self.get_members_from_public_repo(self.repos_map[repo]['org'], self.repos_map[repo]['repo'])
            for member in self.members_activity_config[repo]:
                if len(members_metadata) > 0:
                    map[repo][members_metadata.pop(0)] = member['email']
        return map
    
    def get_members_from_public_repo(self, organization, repository):
        members_metadata = {}
        repo = self.clone_public_repo(organization, repository)
        last = repo[repo.head.target]
        for commit in repo.walk(last.id, pygit2.GIT_SORT_TIME):
            if self.earliest_commit > commit.commit_time:
                break
            if len(commit.parent_ids) > 1: # Merge commits
                continue
            if commit.author is not None and commit.author.email is not None and '[bot]' not in commit.author.email:
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

    def clone_public_repo(self, organization, repository):
        remote = f'https://github.com/{organization}/{repository}.git'
        os_path = os.path.join(self.local_repos_path, f'{organization}-{repository}')
        if os.path.isdir(os_path):
            logging.info(f'A local copy of the repository {organization}/{repository} exists. Pulling recent changes.')
            subprocess.run(['git', '-C', os_path, 'pull'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  
        else:
            logging.info(f'This is the fist time the repository {organization}/{repository} is cloned, so it may take less time going forward.')
            subprocess.run(['git', 'clone', remote, os_path], stderr=subprocess.DEVNULL)   
        return pygit2.Repository(os_path)
    
    def get_mapped_cloned_repo(self, gitgoat_repo_name):
        if gitgoat_repo_name in self.repos_map:
            org = self.config.repo_names_mapping_to_public_repos[gitgoat_repo_name]['org']
            repo = self.config.repo_names_mapping_to_public_repos[gitgoat_repo_name]['repo']
            os_path = os.path.join(self.local_repos_path, f'{org}-{repo}')
            return pygit2.Repository(os_path)
        return None
        

    
