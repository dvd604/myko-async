_hs_api_default:

==============
hubspace-async
==============


    Creates a session to HubSpace and handles authentication


This project was designed to asynchronously connect to the HubSpace API and
retrieve data. The implementation was based on
`jdeath/Hubspace-Homeassistant <https://github.com/jdeath/Hubspace-Homeassistant>`_
but converted to async and cleaned up.

Examples
========
These examples provide sample usage when running from the python
shell. If the code is running within an async loop, gathering the loop
and telling it to run is not required.


Gather all devices from the API
-------------------------------

.. code-block:: python


   from hubspace_async import connection
   import asyncio


   conn = connection.HubSpaceConnection("username", "password")
   loop.run_until_complete(conn.populate_data())

A sample output would look like

.. code-block:: json

   [{"id": "blah1"}, {"id": "blah2"}]

After running this code, the following attributes will be populated:

  * homes: Dictionary of all homes from the API response
  * rooms: Dictionary of all rooms from the API response
  * devices: Dictionary of all devices from the API response


Updating a devices state
------------------------
In this example we will turn a light on. The request requires the use
of ``functionInstance`` for it to work. However some updates
may not require this field.


.. code-block:: python


   from hubspace_async import connection, HubSpaceState
   import asyncio


   conn = connection.HubSpaceConnection("username", "password")
   state = HubSpaceState(
        functionClass="power",
        functionInstance="light-power",
        value="on",
    )
   child_id = "abc123"
   loop.run_until_complete(conn.set_device_state(child_id, new_states))
