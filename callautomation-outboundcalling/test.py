import unittest
from unittest.mock import patch, MagicMock
from main import app, call_automation_client, ACS_PHONE_NUMBER, TARGET_PHONE_NUMBER
from azure.communication.callautomation import PhoneNumberIdentifier
from azure.core.messaging import CloudEvent

class TestCallAutomationApp(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('main.call_automation_client.create_call')
    def test_outbound_call(self, mock_create_call):
        """Test Outbound call handler (mocked create_call)."""
        mock_call_connection_properties = MagicMock()
        mock_call_connection_properties.call_connection_id = "test_connection_id"
        mock_create_call.return_value = mock_call_connection_properties

        response = self.app.get('/outboundCall')

        # redirect
        self.assertEqual(response.status_code, 302)  
        self.assertIn(b'<a href="/">', response.data)

        #call_back_Event
        mock_create_call.assert_called_once_with(
            PhoneNumberIdentifier(TARGET_PHONE_NUMBER),
            'https://s9fsrvs5.usw2.devtunnels.ms:8080/api/callbacks',
            cognitive_services_endpoint="https://tool1.cognitiveservices.azure.com/",
            source_caller_id_number=PhoneNumberIdentifier(ACS_PHONE_NUMBER)
        )

    @patch('main.call_automation_client.get_call_connection')
    @patch('main.get_media_recognize_choice_options')
    def test_callback_handler_call_connected(self, mock_get_media, mock_get_call_connection):
        """Test the callback handler (CallConnected event.)"""
        mock_call_connection_client = MagicMock()
        mock_get_call_connection.return_value = mock_call_connection_client

        callback_data = {
            "data": {
                "callConnectionId": "test_connection_id"
            },
            "type": "Microsoft.Communication.CallConnected",
            "source": "/myapplication/myevent"
        }

        with app.test_request_context('/api/callbacks', method='POST'):
            with patch('main.request') as mock_request:
                mock_request.json = [callback_data]
                response = self.app.post('/api/callbacks', json=[callback_data])

                self.assertEqual(response.status_code, 200)
                mock_get_call_connection.assert_called_once_with("test_connection_id")
                mock_get_media.assert_called_once()

    @patch('main.call_automation_client.get_call_connection')
    @patch('main.handle_play')
    def test_callback_handler_recognize_completed(self, mock_handle_play, mock_get_call_connection):
        """Test the callback handler for RecognizeCompleted event."""
        mock_call_connection_client = MagicMock()
        mock_get_call_connection.return_value = mock_call_connection_client

        callback_data = {
            "data": {
                "callConnectionId": "test_connection_id",
                "recognitionType": "choices",
                "choiceResult": {
                    "label": "Confirm",
                    "recognizedPhrase": "Confirm"
                }
            },
            "type": "Microsoft.Communication.RecognizeCompleted",
            "source": "/myapplication/myevent"
        }

        with app.test_request_context('/api/callbacks', method='POST'):
            with patch('main.request') as mock_request:
                mock_request.json = [callback_data]
                response = self.app.post('/api/callbacks', json=[callback_data])

                self.assertEqual(response.status_code, 200)
                # Match the arguments with named arguments as they appear in the actual call
                mock_handle_play.assert_called_once_with(
                    call_connection_client=mock_call_connection_client,
                    text_to_play="Thank you for confirming your appointment tomorrow at 9am, we look forward to meeting with you."
                )

    @patch('main.call_automation_client.get_call_connection')
    @patch('main.handle_play')
    def test_callback_handler_recognize_failed(self, mock_handle_play, mock_get_call_connection):
        """Test the callback handler for RecognizeFailed event."""
        mock_call_connection_client = MagicMock()
        mock_get_call_connection.return_value = mock_call_connection_client

        callback_data = {
            "data": {
                "callConnectionId": "test_connection_id",
                "operationContext": "retry",
                "resultInformation": {
                    "message": "Error occurred",
                    "code": 8510,
                    "subCode": 8510
                }
            },
            "type": "Microsoft.Communication.RecognizeFailed",
            "source": "/myapplication/myevent"
        }

        with app.test_request_context('/api/callbacks', method='POST'):
            with patch('main.request') as mock_request:
                mock_request.json = [callback_data]
                response = self.app.post('/api/callbacks', json=[callback_data])

                self.assertEqual(response.status_code, 200)
                mock_handle_play.assert_called_once_with(
                    call_connection_client=mock_call_connection_client,
                    text_to_play="I didn't receive an input, we will go ahead and confirm your appointment. Goodbye"
                )

    @patch('main.call_automation_client.get_call_connection')
    def test_callback_handler_play_completed(self, mock_get_call_connection):
        """Test the callback handler for PlayCompleted event."""
        mock_call_connection_client = MagicMock()
        mock_get_call_connection.return_value = mock_call_connection_client

        callback_data = {
            "data": {
                "callConnectionId": "test_connection_id"
            },
            "type": "Microsoft.Communication.PlayCompleted",
            "source": "/myapplication/myevent"
        }

        with app.test_request_context('/api/callbacks', method='POST'):
            with patch('main.request') as mock_request:
                mock_request.json = [callback_data]
                response = self.app.post('/api/callbacks', json=[callback_data])

                self.assertEqual(response.status_code, 200)
                mock_call_connection_client.hang_up.assert_called_once_with(is_for_everyone=True)


if __name__ == '__main__':
    unittest.main()
