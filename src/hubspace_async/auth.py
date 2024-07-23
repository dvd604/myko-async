__all__ = ["HubSpaceAuth"]

import asyncio
import base64
import datetime
import hashlib
import logging
import os
import re
from collections import namedtuple
from typing import Final, Optional

from aiohttp import ClientResponse, ClientSession

from .const import HUBSPACE_DEFAULT_USERAGENT

logger = logging.getLogger(__name__)


HUBSPACE_OPENID_URL: Final[str] = (
    "https://accounts.hubspaceconnect.com/auth/realms/thd/protocol/openid-connect/auth"
)
HUBSPACE_DEFAULT_CLIENT_ID: Final[str] = "hubspace_android"

HUBSPACE_DEFAULT_REDIRECT_URI: Final[str] = "hubspace-app://loginredirect"
HUBSPACE_CODE_URL: Final[str] = (
    "https://accounts.hubspaceconnect.com/auth/realms/thd/login-actions/authenticate"
)
HUBSPACE_TOKEN_HEADERS: Final[dict[str, str]] = {
    "Content-Type": "application/x-www-form-urlencoded",
    "user-agent": HUBSPACE_DEFAULT_USERAGENT,
    "host": "accounts.hubspaceconnect.com",
}
HUBSPACE_TOKEN_URL: Final[str] = (
    "https://accounts.hubspaceconnect.com/auth/realms/thd/protocol/openid-connect/token"
)
TOKEN_TIMEOUT: Final[int] = 118


auth_challenge = namedtuple("AuthChallenge", ["challenge", "verifier"])


class HubSpaceAuth:
    """Authentication against the HubSpace API

    This class follows the HubSpace authentication workflow and utilizes
    refresh tokens.
    """

    def __init__(self, username, password):
        self._async_lock = asyncio.Lock()
        self.__username = username
        self.__password = password
        self.__refresh_token: Optional[str] = None
        self.__token: Optional[str] = None
        self.token_expiry: Optional[float] = None

    async def webapp_login(
        self, challenge: auth_challenge, client: ClientSession
    ) -> str:
        """Get the code used for generating the token

        :param challenge: Challenge data for connection and approving
        :param client: async client for making requests
        """
        code_params: dict[str, str] = {
            "response_type": "code",
            "client_id": HUBSPACE_DEFAULT_CLIENT_ID,
            "redirect_uri": HUBSPACE_DEFAULT_REDIRECT_URI,
            "code_challenge": challenge.challenge,
            "code_challenge_method": "S256",
            "scope": "openid offline_access",
        }
        response: ClientResponse = await client.get(
            HUBSPACE_OPENID_URL, params=code_params
        )
        response.raise_for_status()
        resp_text = await response.text()
        return await self.generate_code(
            re.search("session_code=(.+?)&", resp_text).group(1),
            re.search("execution=(.+?)&", resp_text).group(1),
            re.search("tab_id=(.+?)&", resp_text).group(1),
            client,
        )

    @staticmethod
    async def generate_challenge_data() -> auth_challenge:
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        return auth_challenge(code_challenge, code_verifier)

    async def generate_code(
        self, session_code: str, execution: str, tab_id: str, client: ClientSession
    ) -> str:
        """Finalize login to HubSpace page

        :param session_code: Session code during form interaction
        :param execution: Session code during form interaction
        :param tab_id: Session code during form interaction
        :param client: async client for making request
        """
        params = {
            "session_code": session_code,
            "execution": execution,
            "client_id": HUBSPACE_DEFAULT_CLIENT_ID,
            "tab_id": tab_id,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "user-agent": HUBSPACE_DEFAULT_USERAGENT,
        }
        auth_data = {
            "username": self.__username,
            "password": self.__password,
            "credentialId": "",
        }
        response = await client.post(
            HUBSPACE_CODE_URL,
            params=params,
            data=auth_data,
            headers=headers,
            allow_redirects=False,
        )
        if response.status != 302:
            response.raise_for_status()
        return re.search("&code=(.+?)$", response.headers.get("location")).group(1)

    @staticmethod
    async def generate_refresh_token(
        code: str, challenge: auth_challenge, client: ClientSession
    ) -> str:
        """Generate the refresh token from the given code and challenge

        :param code: Code used for generating refresh token
        :param challenge: Challenge data for connection and approving
        :param client: async client for making request
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": HUBSPACE_DEFAULT_REDIRECT_URI,
            "code_verifier": challenge.verifier,
            "client_id": HUBSPACE_DEFAULT_CLIENT_ID,
        }
        response = await client.post(
            HUBSPACE_TOKEN_URL, headers=HUBSPACE_TOKEN_HEADERS, data=data
        )
        response.raise_for_status()
        return (await response.json()).get("refresh_token")

    @staticmethod
    async def generate_token(client: ClientSession, refresh_token: str) -> str:
        """Generate a token from the refresh token

        :param client: async client for making request
        :param refresh_token: Refresh token for generating request tokens
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "openid email offline_access profile",
            "client_id": "hubspace_android",
        }
        response = await client.post(
            HUBSPACE_TOKEN_URL, headers=HUBSPACE_TOKEN_HEADERS, data=data
        )
        response.raise_for_status()
        return (await response.json()).get("id_token")

    async def token(self, client: ClientSession) -> str:
        async with self._async_lock:
            if not self.__refresh_token:
                logger.debug(
                    "Refresh token not present. Generating a new refresh token"
                )
                challenge = await HubSpaceAuth.generate_challenge_data()
                logger.debug("Challenge information: %s", challenge)
                code: str = await self.webapp_login(challenge, client)
                logger.debug("Successfully generated an auth code")
                self.__refresh_token = await self.generate_refresh_token(
                    code, challenge, client
                )
                logger.debug("Successfully generated a refresh token")
            if (
                not self.token_expiry
                or datetime.datetime.now().timestamp() >= self.token_expiry
            ):
                logger.debug("Token has not been generated or is expired")
                self.__token = await self.generate_token(client, self.__refresh_token)
                self.token_expiry = datetime.datetime.now().timestamp() + TOKEN_TIMEOUT
                logger.debug("Token has been successfully generated")
        return self.__token
