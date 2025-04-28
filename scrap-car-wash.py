from selenium import webdriver
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import csv
import re
from geopy.geocoders import Nominatim

MAX_ATTEMPT = 100

def init_driver():
    """Initialize the WebDriver and return it."""
    options = webdriver.ChromeOptions()
    options.add_argument("--lang=en-GB")
    options.add_argument("--enable-experimental-accessibility-language-detection-dynamic")
    options.add_argument("--enable-experimental-accessibility-language-detection")
    # options.add_argument("--headless")  # Uncomment for headless mode
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Create WebDriver instance
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)
    actionChains = ActionChains(driver)
    print('initialize success')
    return driver, wait, actionChains
def get_lat_lng_from_url(driver):
    """Extract real place lat/lon from URL (from !3d...!4d... pattern)."""
    url = driver.current_url
    match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url)
    if match:
        lat = float(match.group(1))
        lon = float(match.group(2))
        return lat, lon
    else:
        return None, None
def get_lat_lng_from_page(driver):
    """Fallback: Extract lat/lng from meta tag inside the page."""
    try:
        lat_lng = driver.execute_script("""
            const metaTag = document.querySelector('meta[property="og:image"]');
            if (metaTag) {
                const content = metaTag.getAttribute('content');
                const match = content.match(/center=([-\\d\\.]+),([-\\d\\.]+)/);
                if (match) {
                    return [parseFloat(match[1]), parseFloat(match[2])];
                }
            }
            return null;
        """)
        if lat_lng:
            return lat_lng[0], lat_lng[1]
        else:
            return None, None
    except Exception as e:
        print(f"Error executing JavaScript: {e}")
        return None, None
def get_lat_lng(driver):
    """Bulletproof method: Try URL first, fallback to JS."""
    lat, lon = get_lat_lng_from_url(driver)
    if lat is None or lon is None:
        print("URL parsing failed, trying JavaScript fallback...")
        lat, lon = get_lat_lng_from_page(driver)
    return lat, lon
def extract_place_info(title, driver):
    try:
        query = f'div.m6QErb[aria-label="{title}"]'
        name = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, query))).get_attribute('aria-label')
    except :
        print(f"No name")
        return 'retry'
    # Attempt to extract address
    try:
        address = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label*='Address']"))).get_attribute('aria-label')
    except :
        print("No address")
        return name , "", "", ""
   # Extract website
    try :
        website = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'http') and @data-item-id='authority']"))).get_attribute('href')
    except :
        website = ""
        print(f"No website")
    # Extract Plus Code
    try :
        plus_code = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, "//button[contains(@aria-label, 'Plus code')]"))).get_attribute('aria-label')
    except :
        plus_code = ""
        print(f"No plus code")
    return name, address, website, plus_code
def wait_for_map_to_idle(driver, timeout=10):
    """Wait until Google Maps finishes loading new place information."""
    script = """
        const callback = arguments[arguments.length - 1];
        let check = () => {
            let spinner = document.querySelector('div[role="progressbar"]');
            let pin = document.querySelector('img[src*="loading"]');
            if (spinner || pin) {
                return false;
            }
            return true;
        };

        let start = Date.now();
        let interval = setInterval(() => {
            if (check()) {
                clearInterval(interval);
                callback(true);
            }
            if (Date.now() - start > arguments[0] * 1000) {
                clearInterval(interval);
                callback(false);
            }
        }, 200);
    """
    success = driver.execute_async_script(script, timeout)
    if not success:
        raise TimeoutError("Map did not finish loading in time.")

"""Scrape car wash details from Google Maps."""
def scrape(driver, wait, actionChains, city_name):
    """ set up google maps driver """
    query = f"car+wash+in+{city_name}+Australia"
    driver.get("https://www.google.com/maps/search/" + query)

    print('driver-load success')

    try:
        agree_button = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(., 'Agree to all') or contains(., 'Accept all')]"
        )))
        agree_button.click()
        print("Cookie consent accepted.")
        time.sleep(1)  # Give time for the page to load
    except :
        print("No cookie banner found or already accepted")
    
    focus_element = driver.find_element(By.ID, 'zero-input')
    actionChains.move_to_element(focus_element).click().perform()
    for atempt in range(MAX_ATTEMPT):
        for _ in range(2):
            actionChains.send_keys(Keys.PAGE_DOWN).perform()
            time.sleep(0.1)
        html =driver.find_element(By.TAG_NAME, "html").get_attribute('outerHTML')
        if(html.find("You've reached the end of the list.")!=-1):
            break

    print('scrolling success')
    # Create a CSV file to store the data
    with open(f"car_washes_{city_name}.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Name", "Address", "Website", "Plus-code", "lat", "lon"])

        results = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//a[@class='hfpxzc']")))
        if len(results) < 2:
            print(f"==================One element exist in {city_name} ===================================")
            return
        for result in results:
            title = result.get_attribute("aria-label")
            if not title:
                print("Skipping empty result (no title).")
                continue
            for attempt in range(MAX_ATTEMPT):
                try:
                        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(result))
                        actionChains.move_to_element(result).perform()
                        time.sleep(0.1 * (attempt + 1))
                        result.click()
                except Exception as e:
                    print(f"Skipping non-clickable result: {title} | Reason: {e}")
                    continue

                # WAIT here until map finishes loading new data!
                wait_for_map_to_idle(driver)

                info = extract_place_info(title, driver)
                if info != 'retry':
                    name, address, website, plus_code = info
                    if address != "":
                        lat, lon = get_lat_lng(driver)  # Use the new bulletproof function!
                        row = [name, address[9:], website, plus_code[11:], lat, lon]
                        writer.writerow(row)
                    print(f">>> {name} | {address} | {plus_code}  | ({lat, lon})")
                    break
            for attempt in range(MAX_ATTEMPT):
                time.sleep(0.1)
                if result.location['y'] < 400:
                    break
                actionChains.send_keys(Keys.ARROW_DOWN).perform()

    print(f"Scraping {city_name} success")

city_list = [
    "Melbourne", 
    "Darwin", 
    "Brisbane", 
    "Gold Coast", 
    "Hobart", 
    "Perth", 
    "Adelaide",
    # Sydney suburbs
    # [
    #     "Sydney", "Ultimo", "Pyrmont", "Surry Hills", "Newtown", "Redfern", "Glebe", "Chippendale",
    #     "Leichhardt", "Annandale", "Marrickville", "Ashfield", "Petersham", "Dulwich Hill",
    #     "Bondi", "Bondi Junction", "Coogee","Randwick", "Clovelly", "Maroubra",
    #     "North Sydney", "Crows Nest", "Neutral Bay", "Kirribilli", "Lane Cove", "Mosman",
    #     "Chatswood", "Roseville", "Gordon","Pymble", "Wahroonga", "Hornsby",
    #     "Castle Hill", "Baulkham Hills", "Kellyville", "Rouse Hill", "Bella Vista",
    #     "Parramatta", "Auburn", "Granville", "Lidcombe", "Westmead", "Blacktown", "Seven Hills",
    #     "Penrith", "St Marys", "Mount Druitt", "Rooty Hill",
    #     "Bankstown", "Liverpool", "Cabramatta", "Fairfield", "Casula", "Green Valley",
    #     "Kogarah", "Hurstville", "Rockdale", "Bexley", "Blakehurst",
    #     "Miranda", "Cronulla", "Caringbah", "Engadine", "Sutherland", "Menai"
    # ]
]

if __name__ == "__main__":
    driver, wait, actionChains = init_driver()
    for city in city_list:
        try :
            scrape(driver, wait, actionChains, city)
        except: 
            print(f"*************** Error occurred in scraping {city} ***********************")
            continue
    driver.quit()