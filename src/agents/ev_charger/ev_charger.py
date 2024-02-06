import os
import uuid
 
import requests
from messages import EVRequest, KeyValue, UAgentResponse, UAgentResponseType
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low

# get from .env keys to set on agent creation
EV_SEED = os.getenv("EV_SEED", "ev charger service secret phrase")

# create agent with seed by private keys
agent = Agent(
    name="ev_adaptor",
    seed=EV_SEED,
)

# checks agent's balance
fund_agent_if_low(agent.wallet.address())
 
# get from .env private key
OPENCHARGEMAP_API_KEY = os.environ.get("OPENCHARGEMAP_API_KEY", "")

# assert that has the key, else show an error 
assert (
    OPENCHARGEMAP_API_KEY
), "OPENCHARGEMAP_API_KEY environment variable is missing from .env"

# base charge map url 
OPENCHARGEMAP_API_URL = "https://api.openchargemap.io/v3/poi?"

# mas results from api
MAX_RESULTS = 100

# function to get charging stations
def get_ev_chargers(latitude: float, longitude: float, miles_radius: float) -> list:
    """Return ev chargers available within given miles_readius of the latiture and longitude.
    this information is being retrieved from https://api.openchargemap.io/v3/poi? API
    """
    
    # request's response
    response = requests.get(
        url=OPENCHARGEMAP_API_URL
        + f"maxresults={MAX_RESULTS}&latitude={latitude}&longitude={longitude}&distance={miles_radius}",
        headers={"x-api-key": OPENCHARGEMAP_API_KEY},
        timeout=5,
    )
    
    # if returns correctly
    if response.status_code == 200:
        return response.json()
    
    # else return empty list
    return []

# create a protocol
# this protocol is used to define message formats and handlers for specific types
# of messages related to EV chargers. It will be used to specify how the agent
# should handle messages of this type
ev_chargers_protocol = Protocol("EvChargers")

# when this agent receive a request
@ev_chargers_protocol.on_message(model=EVRequest, replies=UAgentResponse)
async def ev_chargers(ctx: Context, sender: str, msg: EVRequest):
    ctx.logger.info(f"Received message from {sender}")
    
    # try to call the function to get ev chargers
    # expect to retrieve information about nearby charging stations
    try:
        # call the function and storage it in a list
        ev_chargers = get_ev_chargers(msg.latitude, msg.longitude, msg.miles_radius)
        
        # unique identifier is generated
        request_id = str(uuid.uuid4())
        
        # lists are initialized to collect data from nearby charging stations 
        conn_types = []
        options = []
        
        # get details about the charging stations and storage it with an id
        for idx, ev_station in enumerate(ev_chargers):
            
            # for each connection
            for conn in ev_station["Connections"]:
                conn_types.append(conn["ConnectionType"]["Title"])
                conn_type_str = ", ".join(conn_types)
                option = f"""● EV charger: {ev_station['AddressInfo']['Title']} , located {round(ev_station['AddressInfo']['Distance'], 2)} miles from your location\n● Usage cost {ev_station['UsageCost']};\n● Type - {conn_type_str}"""
 
            # save in options
            options.append(KeyValue(key=idx, value=option))
        
        # send back to sender the available options
        await ctx.send(
            sender,
            UAgentResponse(
                options=options,
                type=UAgentResponseType.SELECT_FROM_OPTIONS,
                request_id=request_id,
            ),
        )
    
    # if some issue happens, send back an error treatment
    except Exception as exc:
        ctx.logger.error(exc)
        await ctx.send(
            sender, UAgentResponse(message=str(exc), type=UAgentResponseType.ERROR)
        )

# includes to agent the ev chargers protocol
agent.include(ev_chargers_protocol)