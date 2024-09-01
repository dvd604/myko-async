__all__ = ["HubSpaceAuth", "InvalidAuth"]

import asyncio
import base64
import datetime
import hashlib
import logging
import os
import re
from collections import namedtuple
from typing import Final, Optional
from urllib.parse import parse_qs, urlparse

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


class InvalidAuth(Exception):
    pass


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
        logger.hs_trace(
            ("URL: %s" "\n\tparams: %s"),
            HUBSPACE_OPENID_URL,
            code_params,
        )
        response: ClientResponse = await client.get(
            HUBSPACE_OPENID_URL, params=code_params
        )
        logger.hs_trace("Status code: %s", response.status)
        response.raise_for_status()
        resp_text = await response.text()
        if resp_text is None:
            raise InvalidAuth("Unable to authenticate with the supplied username / password")
        session_code = re.search("session_code=(.+?)&", resp_text).group(1)
        execution = re.search("execution=(.+?)&", resp_text).group(1)
        tab_id = re.search("tab_id=(.+?)&", resp_text).group(1)
        logger.hs_trace(
            (
                "WebApp Login:"
                "\n\tSession Code: %s"
                "\n\tExecution: %s"
                "\n\tTab ID:%s"
            ),
            session_code,
            execution,
            tab_id,
        )
        return await self.generate_code(
            session_code,
            execution,
            tab_id,
            client,
        )

    @staticmethod
    async def generate_challenge_data() -> auth_challenge:
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        chal = auth_challenge(code_challenge, code_verifier)
        logger.hs_trace("Challenge information: %s", chal)
        return chal

    async def generate_code(
        self, session_code: str, execution: str, tab_id: str, client: ClientSession
    ) -> str:
        """Finalize login to HubSpace page

        :param session_code: Session code during form interaction
        :param execution: Session code during form interaction
        :param tab_id: Session code during form interaction
        :param client: async client for making request
        """
        logger.hs_trace("Generating code")
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
        logger.hs_trace(
            ("URL: %s" "\n\tparams: %s" "\n\tdata: %s" "\n\theaders: %s"),
            HUBSPACE_CODE_URL,
            params,
            auth_data,
            headers,
        )
        response = await client.post(
            HUBSPACE_CODE_URL,
            params=params,
            data=auth_data,
            headers=headers,
            allow_redirects=False,
        )
        logger.hs_trace("Status code: %s", response.status)
        logger.hs_trace("Location: %s", response.headers.get("location"))
        if response.status != 302:
            response.raise_for_status()
        parsed_url = urlparse(response.headers.get("location"))
        code = parse_qs(parsed_url.query)["code"][0]
        logger.hs_trace("Code: %s", code)
        return code

    @staticmethod
    async def generate_refresh_token(
        code: str, challenge: auth_challenge, client: ClientSession
    ) -> str:
        """Generate the refresh token from the given code and challenge

        :param code: Code used for generating refresh token
        :param challenge: Challenge data for connection and approving
        :param client: async client for making request
        """
        logger.hs_trace("Generating refresh token")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": HUBSPACE_DEFAULT_REDIRECT_URI,
            "code_verifier": challenge.verifier,
            "client_id": HUBSPACE_DEFAULT_CLIENT_ID,
        }
        logger.hs_trace(
            ("URL: %s" "\n\tdata: %s" "\n\theaders: %s"),
            HUBSPACE_TOKEN_URL,
            data,
            HUBSPACE_TOKEN_HEADERS,
        )
        response = await client.post(
            HUBSPACE_TOKEN_URL, headers=HUBSPACE_TOKEN_HEADERS, data=data
        )
        logger.hs_trace("Status code: %s", response.status)
        response.raise_for_status()
        resp_json = await response.json()
        refresh_token = resp_json.get("refresh_token")
        logger.hs_trace("JSON response: %s", resp_json)
        return refresh_token

    @staticmethod
    async def generate_token(client: ClientSession, refresh_token: str) -> str:
        """Generate a token from the refresh token

        :param client: async client for making request
        :param refresh_token: Refresh token for generating request tokens
        """
        logger.hs_trace("Generating token")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "openid email offline_access profile",
            "client_id": "hubspace_android",
        }
        logger.hs_trace(
            ("URL: %s" "\n\tdata: %s" "\n\theaders: %s"),
            HUBSPACE_TOKEN_URL,
            data,
            HUBSPACE_TOKEN_HEADERS,
        )
        response = await client.post(
            HUBSPACE_TOKEN_URL, headers=HUBSPACE_TOKEN_HEADERS, data=data
        )
        logger.hs_trace("Status code: %s", response.status)
        response.raise_for_status()
        resp_json = await response.json()
        auth_token = resp_json.get("id_token")
        logger.hs_trace("JSON response: %s", resp_json)
        return auth_token

    async def token(self, client: ClientSession) -> str:
        async with self._async_lock:
            if not self.__refresh_token:
                logger.debug(
                    "Refresh token not present. Generating a new refresh token"
                )
                challenge = await HubSpaceAuth.generate_challenge_data()
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
