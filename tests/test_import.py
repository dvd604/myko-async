import hubspace_async


def test_api():
    api_elems = [
        "HubSpaceConnection",
        "HubSpaceState",
        "HubSpaceAuth",
        "HubSpaceDevice",
        "get_hs_device",
    ]
    for elem in api_elems:
        assert hasattr(hubspace_async, elem)
