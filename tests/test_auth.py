import json
import os
import pathlib
import time
from urllib.parse import urlencode

import aiohttp
import pytest

from hubspace_async import auth

current_path = pathlib.Path(__file__).parent.resolve()


@pytest.fixture(scope="function")
def hs_auth():
    return auth.HubSpaceAuth("username", "password")


@pytest.fixture(scope="function")
async def aio_sess() -> aiohttp.ClientSession:
    async with aiohttp.ClientSession() as session:
        yield session


async def build_url(base_url: str, qs: dict[str, str]) -> str:
    return f"{base_url}?{urlencode(qs)}"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "time_offset,is_expired",
    [
        # No token
        (None, True),
        # Expired token
        (-5, True),
        # Non-Expired token
        (5, False),
    ],
)
async def test_is_expired(time_offset, is_expired, hs_auth):
    if time_offset:
        hs_auth._token_data = auth.token_data("token", time.time() + time_offset)
    assert await hs_auth.is_expired == is_expired


@pytest.mark.anyio
@pytest.mark.parametrize(
    "page_filename,err_msg,expected",
    [
        # Valid
        (
            "auth_webapp_login.html",
            None,
            auth.auth_sess_data("url_sess_code", "url_exec_code", "url_tab_id"),
        ),
        # page is missing expected id
        (
            "auth_webapp_login_missing.html",
            "Unable to parse login page",
            None,
        ),
        # form field is missing expected attribute
        (
            "auth_webapp_login_bad_format.html",
            "Unable to extract login url",
            None,
        ),
        # URL missing expected elements
        (
            "auth_webapp_login_bad_qs.html",
            "Unable to parse login url",
            None,
        ),
    ],
)
async def test_extract_login_data(page_filename, err_msg, expected):
    with open(os.path.join(current_path, "data", page_filename), "r") as f:
        page_data = f.read()
    if expected:
        assert await auth.extract_login_data(page_data) == expected
    else:
        with pytest.raises(auth.InvalidResponse, match=err_msg):
            await auth.extract_login_data(page_data)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "page_filename, gc_exp, response, expected_err",
    [
        # Invalid status code
        (None, None, {"status": 403}, aiohttp.ClientError),
        # Invalid auth provided
        (None, None, {"status": 200}, aiohttp.ClientError),
        # @TODO - Correctly match param escaping
        # Valid auth passed to generate_code
        # ("auth_webapp_login.html", None, {"status": 200}, None),
    ],
)
async def test_webapp_login(
    page_filename,
    gc_exp,
    response,
    expected_err,
    hs_auth,
    aioresponses,
    aio_sess,
    mocker,
):
    if page_filename:
        with open(os.path.join(current_path, "data", page_filename), "r") as f:
            response["body"] = f.read()
    challenge = await hs_auth.generate_challenge_data()
    generate_code = mocker.patch.object(hs_auth, "generate_code")
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": auth.HUBSPACE_DEFAULT_CLIENT_ID,
        "redirect_uri": auth.HUBSPACE_DEFAULT_REDIRECT_URI,
        "code_challenge": challenge.challenge,
        "code_challenge_method": "S256",
        "scope": "openid offline_access",
    }
    url = await build_url(auth.HUBSPACE_OPENID_URL, params)
    aioresponses.post(url, **response)
    if not expected_err:
        await hs_auth.webapp_login(challenge, aio_sess)
        generate_code.assert_called_once_with(*gc_exp)
    else:
        with pytest.raises(expected_err):
            await hs_auth.webapp_login(challenge, aio_sess)
        generate_code.assert_not_called()


@pytest.mark.anyio
async def test_generate_challenge_data():
    pass


@pytest.mark.anyio
@pytest.mark.parametrize(
    "session_code, execution, tab_id, response, expected_err, expected",
    [
        # Invalid response
        (
            "sess_code",
            "execution",
            "tab_id",
            {"status": 200},
            auth.InvalidResponse,
            None,
        ),
        # Invalid Location
        (
            "sess_code",
            "execution",
            "tab_id",
            {"status": 302, "headers": {"location": "nope"}},
            auth.InvalidAuth,
            None,
        ),
        # Valid location
        (
            "sess_code",
            "execution",
            "tab_id",
            {"status": 302, "headers": {"location": "https://cool.beans?code=beans"}},
            None,
            "beans",
        ),
    ],
)
async def test_generate_code(
    session_code,
    execution,
    tab_id,
    response,
    expected_err,
    expected,
    hs_auth,
    aioresponses,
    aio_sess,
):
    params = {
        "session_code": session_code,
        "execution": execution,
        "client_id": auth.HUBSPACE_DEFAULT_CLIENT_ID,
        "tab_id": tab_id,
    }
    url = await build_url(auth.HUBSPACE_CODE_URL, params)
    aioresponses.post(url, **response)
    if not expected_err:
        assert (
            await hs_auth.generate_code(session_code, execution, tab_id, aio_sess)
            == expected
        )
    else:
        with pytest.raises(expected_err):
            await hs_auth.generate_code(session_code, execution, tab_id, aio_sess)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "code,response,expected,err",
    [
        # Invalid refresh token
        ("code", {"status": 403}, None, aiohttp.ClientError),
        # Incorrect format
        (
            "code",
            {"status": 200, "body": json.dumps({"refresh_token2": "cool_beans"})},
            None,
            auth.InvalidResponse,
        ),
        # Valid refresh token
        (
            "code",
            {"status": 200, "body": json.dumps({"refresh_token": "cool_beans"})},
            "cool_beans",
            None,
        ),
    ],
)
async def test_generate_refresh_token(
    code, response, expected, err, hs_auth, aioresponses, aio_sess
):
    challenge = await hs_auth.generate_challenge_data()
    aioresponses.post(auth.HUBSPACE_TOKEN_URL, **response)
    if expected:
        assert expected == await hs_auth.generate_refresh_token(
            code, challenge, aio_sess
        )
    else:
        with pytest.raises(err):
            await hs_auth.generate_refresh_token(code, challenge, aio_sess)
    aioresponses.assert_called_once()
    call_args = list(aioresponses.requests.values())[0][0]
    assert call_args.kwargs["headers"] == auth.HUBSPACE_TOKEN_HEADERS
    assert call_args.kwargs["data"] == {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": auth.HUBSPACE_DEFAULT_REDIRECT_URI,
        "code_verifier": challenge.verifier,
        "client_id": auth.HUBSPACE_DEFAULT_CLIENT_ID,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "refresh_token,response,expected,err",
    [
        # Invalid status
        ("code", {"status": 403}, None, aiohttp.ClientError),
        # bad response
        (
            "code",
            {"status": 200, "body": json.dumps({"id_token2": "cool_beans"})},
            None,
            auth.InvalidResponse,
        ),
        # valid response
        (
            "code",
            {"status": 200, "body": json.dumps({"id_token": "cool_beans"})},
            "cool_beans",
            None,
        ),
    ],
)
async def test_generate_token(
    refresh_token, response, expected, err, aioresponses, aio_sess
):
    aioresponses.post(auth.HUBSPACE_TOKEN_URL, **response)
    if expected:
        assert expected == (await auth.generate_token(aio_sess, refresh_token)).token
    else:
        with pytest.raises(err):
            await auth.generate_token(aio_sess, refresh_token)
    aioresponses.assert_called_once()
    call_args = list(aioresponses.requests.values())[0][0]
    assert call_args.kwargs["headers"] == auth.HUBSPACE_TOKEN_HEADERS
    assert call_args.kwargs["data"] == {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "openid email offline_access profile",
        "client_id": "hubspace_android",
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "webapp_login_return, generate_refresh_token_return",
    [
        ("cool", "beans"),
    ],
)
async def test_perform_initial_login(
    webapp_login_return, generate_refresh_token_return, hs_auth, aio_sess, mocker
):
    mocker.patch.object(hs_auth, "webapp_login", return_value=webapp_login_return)
    mocker.patch.object(
        hs_auth, "generate_refresh_token", return_value=generate_refresh_token_return
    )
    assert (
        await hs_auth.perform_initial_login(aio_sess) == generate_refresh_token_return
    )


# @TODO - Implement this test
# async def test_token():
#     pass
