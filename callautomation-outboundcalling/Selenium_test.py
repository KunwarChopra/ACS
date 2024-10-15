from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import time
import pyttsx3

# URL
FLASK_APP_URL = "http://127.0.0.1:8080"
ACS_DASHBOARD_URL = "http://localhost:5000"

CHROME_DRIVER_PATH = r"C:\chromedriver-win64\chromedriver.exe"

chrome_options = Options()
chrome_options.add_argument("--use-fake-ui-for-media-stream") 
chrome_options.add_argument("--allow-file-access-from-files")

service = Service(executable_path=CHROME_DRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

engine = pyttsx3.init()

main_menu_prompt_duration = 20  # Adjust this based on actual audio length

try:
    # Step 1: Open ACS Dashboard and login
    driver.get(ACS_DASHBOARD_URL)
    login_button = WebDriverWait(driver, 120).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.primary-button'))  
    )
    print("Step 1: Logging into the ACS dashboard...")
    login_button.click()

    # Wait for ACS user ID to be provisioned
    provisioned_id_element = WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.XPATH, '//span[contains(@class, "identity") and contains(text(), "acs:")]'))
    )

    # Step 2: Capture the provisioned ACS user ID
    provisioned_acs_user_id = provisioned_id_element.text.strip()
    print(f"Step 2: Captured ACS user ID: {provisioned_acs_user_id}")

    # Step 3: Send the captured ACS user ID to the Flask app to update the Target ACS User ID
    update_url = f"{FLASK_APP_URL}/update_acs_user_id"
    payload = {'new_acs_user_id': provisioned_acs_user_id}
    print("Step 3: Sending ACS user ID to the Flask app...")

    response = requests.post(update_url, json=payload)

    if response.status_code == 200:
        print(f"Step 3: Successfully updated ACS user ID in Flask app. Response: {response.text}")
    else:
        print(f"Step 3: Failed to update ACS user ID in Flask app. Response: {response.text}")
        driver.quit()
        exit()

    # Add a delay before proceeding to allow time for any background processing
    time.sleep(10)

    # Step 4: Navigate to the Flask app and place a call
    driver.execute_script("window.open('');")  
    driver.switch_to.window(driver.window_handles[1])
    driver.get(FLASK_APP_URL)

    # Wait for the "Place a call" button and click it
    place_call_button = WebDriverWait(driver, 120).until(
        EC.element_to_be_clickable((By.XPATH, '//input[@type="submit" and @value="Place a call!"]'))
    )
    print("Step 4: Triggering the outbound call to the updated ACS user...")
    place_call_button.click()

    # Wait some time outbound call has been placed successfully
    time.sleep(20)

    # Step 5: Navigate back to ACS to verify the incoming call
    driver.switch_to.window(driver.window_handles[0]) 
    print("Step 5: Navigating back to ACS dashboard to check for incoming call...")

    # Incoming call card on the ACS
    incoming_call_card = WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.XPATH, '//h2[contains(text(), "Incoming Call")]'))
    )
    
    print("Step 6: Incoming call detected on the ACS dashboard!")

    # Step 7: Answer the call (automatically accept the call with microphone unmuted, video off)
    answer_call_button = WebDriverWait(driver, 120).until(
        EC.element_to_be_clickable((By.XPATH, '//span[@title="Answer call with microphone unmuted and video off"]'))
    )
    print("Step 7: Answering the call...")
    answer_call_button.click()

    # Step 8: Wait for the prompt to speech to be played
    print("Step 8: Waiting for the prompt 'Main Menu' to finish playing...")

    # Wait for the duration of the Main Menu prompt
    time.sleep(main_menu_prompt_duration) 

    # Step 9: Ensure response is provided before ending the call
    while True:
        # Check if the "Confirm" response has been played
        print("Step 9: Generating speech response after prompt is played...")
        engine.say("Confirm")
        engine.runAndWait()

        # After providing response, break out of the loop
        print("Step 10: Speech response 'Confirm' provided via microphone (through virtual audio cable).")
        break
finally:
    time.sleep(30) 
    driver.quit()
    print("Test completed!")
