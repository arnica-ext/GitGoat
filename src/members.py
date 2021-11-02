import logging
from src.config import Config
from src.connection import ConnectionHandler

class Membership:

    def __init__(self, organization, config_file = None):
        self.org = organization
        self.memberships_endpoint = f'/user/memberships/orgs/{organization}'
        self.invitations_endpoint = f'/orgs/{organization}/invitations'
        self.config = Config() if config_file is None else Config(config_file)

    # Invite all members that are configured in the config file.
    async def invite_members(self):
        conn = ConnectionHandler(config_file=self.config.filename)
        await self.__cancel_invitations(conn)
        for member in self.config.members:
            data = {
                'invitee_id': member['member_id']
            }
            await conn.post(self.invitations_endpoint, json_data=data)

    async def __cancel_invitations(self, conn: ConnectionHandler):
        if not self.config.is_saas:
            return 
        resp = await conn.get(self.invitations_endpoint)
        for invitation in resp:
            await conn.delete(self.invitations_endpoint + '/' + str(invitation['id']))
            logging.info(f'Cancelled the existing (before this execution) invitation for user {str(invitation["login"])}')

    # Accept an invitation to an organization by a given user PAT.
    async def accept_invitation_to_org(self, pat):
        if not self.config.is_saas:
            return 
        conn = ConnectionHandler(pat, self.config.filename)
        data = {
            'state': 'active'
        }
        await conn.patch(self.memberships_endpoint, json_data=data)