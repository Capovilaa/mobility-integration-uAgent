import os
import uuid
 
import requests
from messages import GeoParkingRequest, KeyValue, UAgentResponse, UAgentResponseType
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low

# get .env private keys 
GEOAPI_PARKING_SEED = os.getenv(
    "GEOAPI_PARKING_SEED", "geoapi parking adaptor agent secret phrase"
)

# create agent
agent = Agent(name="geoapi_parking_adaptor", seed=GEOAPI_PARKING_SEED)

# add to him the protocol
geoapi_parking_protocol = Protocol("Geoapi CarParking")

# check agent's balance
fund_agent_if_low(agent.wallet.address())

# get private key from .env
GEOAPI_API_KEY = os.getenv("GEOAPI_API_KEY", "")

# grant that this private key exists 
assert GEOAPI_API_KEY, "GEOAPI_API_KEY environment variable is missing from .env"

# base parking api url
PARKING_API_URL = "https://api.geoapify.com/v2/places?"

# format the response from api 
def format_parking_data(api_response) -> list:
    """
    By taking the response from the API, this function formats the response
    to be appropriate for displaying back to the user.
    """
    
    # crete some variables to be used
    parking_data = []
    parking_name = "Unknown Parking"
    parking_capacity = ""
    
    # run place in api response
    for place in api_response["features"]:
        
        # set those variables with parking's informations
        if "name" in place["properties"]:
            parking_name = place["properties"]["name"]
            address = place["properties"]["formatted"].split(",")[1::]
            parking_address = "".join(list(address))
        elif "formatted" in place["properties"]:
            parking_address = place["properties"]["formatted"]
        else:
            continue
        if "capacity" in place["properties"]["datasource"]["raw"]:
            parking_capacity = (
                f'{place["properties"]["datasource"]["raw"]["capacity"]} spaces'
            )
        elif "parking" in place["properties"]["datasource"]["raw"]:
            parking_capacity = (
                f'{place["properties"]["datasource"]["raw"]["parking"]} parking'
            )
        elif (
            "access" in place["properties"]["datasource"]["raw"]
            and place["properties"]["datasource"]["raw"]["access"] != "yes"
        ):
            continue
        
        # add to list the formatted data
        parking_data.append(
            f"""● Car Parking: {parking_name} has {parking_capacity} at {parking_address}"""
        )
        
    # returns formatted list with parking's data
    return parking_data

# it sends the requests to parking's api
def get_parking_from_api(latitude, longitude, radius, max_r) -> list:
    """
    With all the user preferences, this function sends the request to the Geoapify Parking API,
    which returns the response.
    """
    
    # returns response with data or an error
    try:
        response = requests.get(
            url=f"{PARKING_API_URL}categories=parking&filter=circle:{longitude},{latitude},{radius}&bias=proximity:{longitude},{latitude}&limit={max_r}&apiKey={GEOAPI_API_KEY}",
            timeout=60,
        )
        return response.json()
    except Exception as exc:
        print("Error: ", exc)
        return []

# when receives a request to find parking spaces
@geoapi_parking_protocol.on_message(model=GeoParkingRequest, replies=UAgentResponse)
async def geoapi_parking(ctx: Context, sender: str, msg: GeoParkingRequest):
    """
    The function takes the request to search for parking in any location based on user preferences
    and returns the formatted response to TAGI.
    """
    ctx.logger.info(f"Received message from {sender}")
    
    # 
    try:
        radius_in_meter = msg.radius * 1609
        
        # calls function to returns parking spaces
        response = get_parking_from_api(
            msg.latitude, msg.longitude, radius_in_meter, msg.max_result
        )
        
        # format function's response
        response = format_parking_data(
            response
        )
        
        # generate an unique id
        request_id = str(uuid.uuid4())
        
        # if it found nearby parking spaces
        if len(response) > 1:
            option = f"""Here is the list of some Parking spaces nearby:\n"""
            
            # initiate some varibles to be used
            idx = ""
            options = [KeyValue(key=idx, value=option)]
            
            # set variables and append it into list
            for parking in response:
                option = parking
                options.append(KeyValue(key=idx, value=option))
            
            # send back the parking spaces found
            await ctx.send(
                sender,
                UAgentResponse(
                    options=options,
                    type=UAgentResponseType.SELECT_FROM_OPTIONS,
                    request_id=request_id,
                ),
            )
        
        # else, returns thar doesn't found
        else:
            await ctx.send(
                sender,
                UAgentResponse(
                    message="No options available for this context",
                    type=UAgentResponseType.FINAL,
                    request_id=request_id,
                ),
            )
            
    # returns an error if some issue happens
    except Exception as exc:
        ctx.logger.error(exc)
        await ctx.send(
            sender, UAgentResponse(message=str(exc), type=UAgentResponseType.ERROR)
        )

# include protocol to the agent 
agent.include(geoapi_parking_protocol)