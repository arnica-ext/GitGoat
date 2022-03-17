
import os, stat, pathlib, time, logging
from src.config import Config
import git

class CodeOwners:
    
    filename = 'CODEOWNERS'

    def __init__(self, organization: str, repo_name: str, repository: git.Repo, config_file = None):
        self.config = Config() if config_file is None else Config(config_file)
        self.org = organization
        self.repo = repository
        self.repo_name = repo_name
        self.repo.git.add(update=True)
        self.origin = self.repo.remote(name='origin')
        self.is_codeowners_in_config = self.__is_codeowners_in_config()
    
    async def push_file(self, filename):
        if not self.is_codeowners_in_config:
            return
        self.repo.index.add([filename])
        self.repo.index.commit('Added CODEOWNERS by GitGoat')
        try:
            self.origin.push()
        except Exception:
            logging.warning(f'Unable to push code from {self.repo.common_dir}')

    async def generate_file(self):
        if not self.is_codeowners_in_config:
            return
        filename = os.path.join(await self.__get_folder(), CodeOwners.filename)
        rules = ''
        for owner in self.config.repo_configs[self.repo_name]['codeowners']['owners']:
            rules += f'{owner["pattern"]}\t'
            if 'users' in owner:
                for u in owner['users']:
                    rules += f'@{u} '
            if 'teams' in owner:
                for t in owner['teams']:
                    rules += f'@{self.org}/{self.repo_name}-{t} '
            rules += '\n' 
        with open(filename, 'w') as f:
                f.write(rules)
        return filename

    async def __get_folder(self):
        path = self.config.repo_configs[self.repo_name]['codeowners']['path']
        codeowners_path = os.path.join(self.repo.working_dir, path)
        if not os.path.isdir(codeowners_path):
            os.mkdir(codeowners_path)
        return codeowners_path

    def __is_codeowners_in_config(self):
        if 'codeowners' in self.config.repo_configs[self.repo_name]:
            if 'path' in self.config.repo_configs[self.repo_name]['codeowners'] and 'owners' in self.config.repo_configs[self.repo_name]['codeowners']:
                return True
        return False
    
