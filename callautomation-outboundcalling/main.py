from azure.eventgrid import EventGridEvent, SystemEventNames
from flask import Flask, Response, request, json, send_file, render_template, redirect
from logging import INFO
from azure.communication.callautomation import (
    CallAutomationClient,
    CallConnectionClient,
    CommunicationUserIdentifier,
    PhoneNumberIdentifier,
    RecognizeInputType,
    MicrosoftTeamsUserIdentifier,
    CallInvite,
    RecognitionChoice,
    DtmfTone,
    TextSource)
from azure.core.messaging import CloudEvent

# Your ACS resource connection string
ACS_CONNECTION_STRING = "endpoint=https://kunwar.unitedstates.communication.azure.com/;accesskey=85rBigfYiky6inW9VKHTGf1GOVvZC1lydro3CjuHvZ4fmjcMENSUJQQJ99AJACULyCppI8XKAAAAAZCSkEO5"

# Your ACS resource phone number will act as source number to start outbound call
ACS_PHONE_NUMBER = "+18442479162"

# Initialize Target ACS User ID (this will be updated dynamically)
TARGET_ACS_USER_ID = None  # Placeholder, will be updated dynamically

# Callback events URI to handle callback events.
CALLBACK_URI_HOST = "https://q6797bsv.usw2.devtunnels.ms:8080"
CALLBACK_EVENTS_URI = CALLBACK_URI_HOST.strip() + "/api/callbacks"
COGNITIVE_SERVICES_ENDPOINT = "https://tool1.cognitiveservices.azure.com/"

# Prompts for text-to-speech
SPEECH_TO_TEXT_VOICE = "en-US-NancyNeural"
MAIN_MENU = "Hello, this is Contoso Bank, we're calling about your appointment tomorrow. Please say confirm or cancel."
CONFIRMED_TEXT = "Thank you for confirming your appointment."
CANCEL_TEXT = "Your appointment has been canceled."
CUSTOMER_QUERY_TIMEOUT = "I'm sorry, I didn't receive a response. Please try again."
NO_RESPONSE = "I didn't receive an input, confirming your appointment. Goodbye."
INVALID_AUDIO = "I'm sorry, I didn't understand your response, please try again."

# Flask application
app = Flask(__name__,
            template_folder="template")

call_automation_client = CallAutomationClient.from_connection_string(ACS_CONNECTION_STRING)

# Function to update the TARGET_ACS_USER_ID dynamically
@app.route('/update_acs_user_id', methods=['POST'])
def update_acs_user_id():
    global TARGET_ACS_USER_ID
    data = request.get_json()
    new_acs_user_id = data.get('new_acs_user_id', None)
    if new_acs_user_id:
        TARGET_ACS_USER_ID = new_acs_user_id  # Update the global variable
        return {"status": "success", "message": f"Updated ACS user ID to {TARGET_ACS_USER_ID}"}, 200
    return {"status": "failure", "message": "Invalid ACS user ID"}, 400

def get_choices():
    choices = [
        RecognitionChoice(label="Confirm", phrases=["Confirm", "First", "One"], tone=DtmfTone.ONE),
        RecognitionChoice(label="Cancel", phrases=["Cancel", "Second", "Two"], tone=DtmfTone.TWO)
    ]
    return choices

def get_media_recognize_choice_options(call_connection_client: CallConnectionClient, text_to_play: str, target_participant: str, choices: any, context: str):
    play_source = TextSource(text=text_to_play, voice_name=SPEECH_TO_TEXT_VOICE)
    call_connection_client.start_recognizing_media(
        input_type=RecognizeInputType.CHOICES,
        target_participant=target_participant,
        choices=choices,
        play_prompt=play_source,
        interrupt_prompt=False,
        initial_silence_timeout=10,
        operation_context=context
    )
     
def handle_play(call_connection_client: CallConnectionClient, text_to_play: str):
    play_source = TextSource(text=text_to_play, voice_name=SPEECH_TO_TEXT_VOICE)
    call_connection_client.play_media_to_all(play_source)

# GET endpoint to place phone call to dynamically updated ACS user ID
@app.route('/outboundCall')
def outbound_call_handler():
    global TARGET_ACS_USER_ID
    if not TARGET_ACS_USER_ID:
        return {"status": "failure", "message": "Target ACS User ID is not set."}, 400
    
    target_participant = CommunicationUserIdentifier(TARGET_ACS_USER_ID)
    source_caller = PhoneNumberIdentifier(ACS_PHONE_NUMBER)
    call_connection_properties = call_automation_client.create_call(
        target_participant, 
        CALLBACK_EVENTS_URI,
        cognitive_services_endpoint=COGNITIVE_SERVICES_ENDPOINT,
        source_caller_id_number=source_caller
    )
    app.logger.info("Created call with connection id: %s", call_connection_properties.call_connection_id)
    return {"status": "success", "message": "Outbound call initiated"}, 200

# POST endpoint to handle callback events
@app.route('/api/callbacks', methods=['POST'])
def callback_events_handler():
    for event_dict in request.json:
        event = CloudEvent.from_dict(event_dict)
        call_connection_id = event.data['callConnectionId']
        app.logger.info("%s event received for call connection id: %s", event.type, call_connection_id)
        call_connection_client = call_automation_client.get_call_connection(call_connection_id)
        target_participant = CommunicationUserIdentifier(TARGET_ACS_USER_ID)
        if event.type == "Microsoft.Communication.CallConnected":
            app.logger.info("Starting recognize")
            get_media_recognize_choice_options(
                call_connection_client=call_connection_client,
                text_to_play=MAIN_MENU,
                target_participant=target_participant,
                choices=get_choices(), context=""
            )
        elif event.type == "Microsoft.Communication.RecognizeCompleted":
            app.logger.info("Recognize completed: data=%s", event.data)
            label_detected = event.data['choiceResult']['label']
            text_to_play = CONFIRMED_TEXT if label_detected == "Confirm" else CANCEL_TEXT
            handle_play(call_connection_client=call_connection_client, text_to_play=text_to_play)
        elif event.type == "Microsoft.Communication.RecognizeFailed":
            failedContext = event.data.get('operationContext')
            resultInformation = event.data.get('resultInformation', {})
            app.logger.info("Recognition failed, message=%s, code=%s", resultInformation.get('message'), resultInformation.get('code'))
            text_to_play = CUSTOMER_QUERY_TIMEOUT if resultInformation.get('subCode') == 8510 else INVALID_AUDIO
            get_media_recognize_choice_options(
                call_connection_client=call_connection_client,
                text_to_play=text_to_play,
                target_participant=target_participant,
                choices=get_choices(),
                context="retry"
            )
        elif event.type in ["Microsoft.Communication.PlayCompleted", "Microsoft.Communication.PlayFailed"]:
            app.logger.info("Terminating call")
            call_connection_client.hang_up(is_for_everyone=True)
    return Response(status=200)

# GET endpoint to render the menus
@app.route('/')
def index_handler():
    return render_template("index.html")

if __name__ == '__main__':
    app.logger.setLevel(INFO)
    app.run(port=8080)
