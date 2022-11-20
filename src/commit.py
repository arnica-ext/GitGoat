from datetime import datetime, timedelta
from random import random
import git, os, logging, pygit2, tqdm
from faker import Faker
from src.config import Config
from src.secrets import Secrets
from src.public_repo_map import IdentityMap

class Commit:
    
    CONFIG_FILE = None
    PUBLIC_REPO_MAP = IdentityMap(CONFIG_FILE)
    MAPPED_AUTHORS = PUBLIC_REPO_MAP.map_authors()
    
    
    def __init__(self, repository: pygit2.repository, secrets: Secrets, gitgoat_repo_name: str, config_file = None):
        self.repo = repository
        #self.repo.git.add(update=True)
        #self.origin = self.repo.remote(name='origin') 
        self.fake = Faker()
        self.secrets = secrets
        self.gitgoat_repo_name = gitgoat_repo_name
        self.config = Config() if config_file is None else Config(config_file)
        if (Commit.CONFIG_FILE != config_file):
            Commit.CONFIG_FILE = config_file
            Commit.PUBLIC_REPO_MAP = IdentityMap(config_file)
            Commit.MAPPED_AUTHORS = Commit.PUBLIC_REPO_MAP.map_authors()
        self.mapped_authors = Commit.MAPPED_AUTHORS[gitgoat_repo_name] if gitgoat_repo_name in Commit.MAPPED_AUTHORS else {}
        self.earliest_commit = int((datetime.utcnow() - timedelta(days=1800)).timestamp())
        self.author = self.repo.config._get_entry('user.email').value
        
    def generate_mirrored_commits(self, days_since_latest_commit: int, commit_secret = False): ## TODO: adjust the URL of the origin and push to the GitGoat repo!
        public_repo = Commit.PUBLIC_REPO_MAP.get_mapped_cloned_repo(self.gitgoat_repo_name)
        last = public_repo[public_repo.head.target]
        commits_count = 0
        commit_ids = []
        repo_path = self.repo.path.replace('.git/', '')
        for commit in public_repo.walk(last.id, pygit2.GIT_SORT_TIME):
            indexes = {}
            if self.earliest_commit > commit.commit_time:
                break
            if len(commit.parent_ids) > 1 and commit.id not in commit_ids: # Merge commits
                continue
            commit_ids.append(commit.id)
            if commit.author is not None and commit.author.email is not None:
                if commit.author.email in self.mapped_authors and \
                    int((datetime.utcnow() - timedelta(days_since_latest_commit)).timestamp()) > commit.commit_time:
                        self.write_commit_tree(commit.tree, repo_path, indexes)
                        #path_len = len(repo_path)
                        #for index in indexes.keys():
                        #    self.repo.index.add(index[path_len:])
                        #self.repo.index.write()
                        self.repo.index.add_all()
                        tree = self.repo.TreeBuilder().write()
                        message = commit.message
                        timestamp = datetime.fromtimestamp(commit.commit_time).strftime('%Y-%m-%d %H:%M:%S')
                        author_email = self.mapped_authors[commit.author.email]
                        author_login = self.config.email_to_login_map[author_email]
                        author = pygit2.Signature(author_login,author_email)
                        self.repo.create_commit('refs/HEAD', author = author, committer = author, message = message, commit_time = timestamp, tree = tree, parents = [self.repo.head.target.hex])
                        #self.repo.index.commit(message, commit_date=timestamp, author_date=timestamp)
                        commits_count += 1
                        if commits_count > 10 or len(indexes.keys()) > 1000:
                            logging.info(f'{datetime.now().strftime("%H:%M:%S")}: pushing a bulk of {commits_count} commits ({len(indexes.keys())} indexes in last commit).')
                            commits_count = 0
                            try:
                                self.origin.push()
                            except Exception as ex:
                                logging.warning(f'Unable to push code from {self.repo.path}. {ex}')
        if commit_secret:
            filename = f'secret_{self.fake.lexify(text="???????")}.txt'
            self.repo.index.add([self.generate_file_message(filename=filename, file_content=self.secrets.get_next_secret())])
            timestamp = (datetime.now()- timedelta(days_since_latest_commit + int(random()*10)+1)).strftime('%Y-%m-%d %H:%M:%S')
            self.repo.index.commit(f'GitGoat generated secret {self.fake.lexify(text="?????")}', commit_date=timestamp, author_date=timestamp)
        try:
            self.origin.push()
        except Exception:
            logging.warning(f'Unable to push code from {self.repo.working_dir}')
                    
    def write_commit_tree(self, commit_tree, working_dir, indexes):
        for obj in commit_tree:
            path = os.path.join(working_dir, obj.name)
            if obj.type_str == 'blob':
                with open(path, 'wb') as f:
                    f.write(obj.data)
                indexes[path] = 1
            elif obj.type_str == 'tree':
                try:
                   os.mkdir(path)
                except:
                    continue 
                #indexes[path] = 1
                self.write_commit_tree(obj, path, indexes)
         
    # Generates commits with some flexability. The count of commits and days since last commit are mandatory, while the others have default generators. 
    # If commit_dates are provided as a list, make sure the commit_messages list is the same length. 
    def generate_random_commits(self, count: int, days_since_latest_commit: int, commit_dates: list = [], commit_messages: list = [], random_commit_messages: bool = True, commit_message: str = 'Random commit message', commits_filename = None, commit_secret = False):
        if len(commit_dates) == 0:
            commit_dates = self.generate_commit_dates(count, days_since_latest_commit)
        if len(commit_messages) == 0:
            commit_messages = self.generate_commit_messages(len(commit_dates), random_commit_messages, commit_message)
        for _ in range(len(commit_dates)):
            self.repo.index.add([self.generate_file_message(filename=commits_filename)])
            timestamp = commit_dates.pop(0).strftime('%Y-%m-%d %H:%M:%S')
            self.repo.index.commit(commit_messages.pop(0), commit_date=timestamp, author_date=timestamp)
        if commit_secret:
            filename = f'secret_{self.fake.lexify(text="???????")}.txt'
            self.repo.index.add([self.generate_file_message(filename=filename, file_content=self.secrets.get_next_secret())])
            if timestamp is None:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.repo.index.commit(f'GitGoat generated secret {self.fake.lexify(text="?????")}', commit_date=timestamp, author_date=timestamp)
        try:
            self.origin.push()
            #logging.info(f'Successfully pushed code from {self.repo.common_dir}')
        except Exception:
            logging.warning(f'Unable to push code from {self.repo.common_dir}')

    # The file name and content are automatically generated if the values are not assigned.
    # The open_file_mode setting options are 'w' for overwiriting or 'a' for appending content. 
    def generate_file_message(self, filename = None, file_content = None, open_file_mode = 'w'):
        if filename is None:
            filename = f'{self.fake.lexify(text="???????")}.txt'
        filename = os.path.join(self.repo.working_dir,filename)
        content = file_content if file_content is not None else self.fake.paragraph(nb_sentences=1)
        with open(filename, open_file_mode) as f:
                f.write(content)
        return filename

    def generate_commit_messages(self, count: int, random: bool = True, message: str = 'Random commit message'):
        commit_messages = []
        text = message if random is False else message + ' ???????????????' 
        for _ in range(count):
            commit_messages.append(self.fake.lexify(text=text))
        return commit_messages

    def generate_commit_dates(self, count: int, days_since_latest_commit):
        commit_dates = []
        end_date = f'-{str(days_since_latest_commit)}d'
        for _ in range(count):
            commit_dates.append(self.fake.date_time_between(start_date='-1y', end_date=end_date, tzinfo=None))
        if days_since_latest_commit < 60:
            for _ in range(int(count/10)):
                commit_dates.append(self.fake.date_time_between(start_date='-29d', end_date=end_date, tzinfo=None))       
        return commit_dates