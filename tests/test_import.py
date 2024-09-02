import hubspace_async


def test_api():
    api_elems = [
        "HubSpaceConnection",
        "HubSpaceState",
        "HubSpaceAuth",
        "HubSpaceDevice",
        "HubSpaceRoom",
        "InvalidAuth",
        "InvalidResponse",
    ]
    assert len(api_elems) == len(hubspace_async.__all__)
    for elem in api_elems:
        assert hasattr(hubspace_async, elem)
