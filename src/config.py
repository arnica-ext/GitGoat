import os, logging, coloredlogs, base64, logging, yaml

class Config:

    def __init__(self, filename: str = None) -> None:
        coloredlogs.install()
        logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', datefmt='%m/%d/%Y %H:%M:%S', level=logging.INFO)
        self.filename = 'config.yaml' if filename is None else filename
        with open(self.filename, "r") as f:
            self.__obj = yaml.load(f, Loader=yaml.FullLoader)
        self.base_url = self.__obj['base_url']
        self.base_headers = self.__obj['base_headers']
        self.base_headers['Authorization'] = Config.generate_auth_header(Config.get_pat())
        self.org_names = self.__obj['org_names']
        self.repo_names = self.__obj['repo_names']
        self.repo_configs = self.__obj['repo_configs']
        self.teams = self.__obj['teams']
        self.members = self.__obj['members']

    def get_pat():
        __auth_password = os.getenv('github_token')
        if __auth_password is None:
            logging.error("Credentials are not set as OS environment variables.")
            exit(1)
        return __auth_password

    def generate_auth_header(pat: str):
        return 'Basic ' + base64.b64encode(('GitGoat:' + pat).encode('ascii')).decode('ascii')