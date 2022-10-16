import asyncio
from src.public_repo_map import IdentityMap

idmap = IdentityMap()
asyncio.run(idmap.map_authors())
print('Done')
