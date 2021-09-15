import asyncio, logging, sys, os
from src.config import Config
from src.repository import Repository

async def mock_test(config_file: str, orgs: list = []):
    config = Config() if config_file is None else Config(config_file)
    org_names = orgs if len(orgs) > 0 else config.org_names
    for org in org_names:
        logging.info('----- Checking access to repos -----')
        r = Repository(org)
        if len(await r.get_all()) > 0:
            logging.info('Managed to get access to repos')
            exit(0)
        logging.error('Did NOT manage to get access to repos')
        exit(1)

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
    asyncio.run(mock_test(config_file=config_file, orgs=org))
    
