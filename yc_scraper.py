import time
import csv
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
TARGET_URL = "https://www.ycombinator.com/internships"
OUTPUT_FILE = "yc_internships_data.csv"
SCROLL_PAUSE_TIME = 2  # Time to wait after scrolling for content to load
MAX_COMPANIES = 10     # Limit for testing. Set to 100+ for full run.

def get_driver():
    """Setup Chrome Driver with options to be less detectable."""
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless") # Uncomment this to run in background (no visible window)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def scrape_internship_links(driver):
    """Scrolls the internship page and grabs company profile URLs."""
    print(f"Loading {TARGET_URL}...")
    driver.get(TARGET_URL)
    time.sleep(5)  # Initial load wait

    company_links = set()
    
    # Scroll logic to load more items (YC uses infinite scroll)
    # For this demo, we scroll 3 times. Increase range for more results.
    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        
        # Parse current state
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find links that look like /companies/xxx
        # YC usually links the company name or logo to the profile
        for a in soup.find_all('a', href=True):
            if "/companies/" in a['href'] and "jobs" not in a['href']:
                full_link = f"https://www.ycombinator.com{a['href']}"
                company_links.add(full_link)
                
                if len(company_links) >= MAX_COMPANIES:
                    break
        
        if len(company_links) >= MAX_COMPANIES:
            break

    print(f"Found {len(company_links)} unique companies.")
    return list(company_links)

def extract_company_data(driver, url):
    """Visits a company page and extracts details."""
    try:
        driver.get(url)
        time.sleep(2) # Politeness wait
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        data = {
            "Company Name": "N/A",
            "Website": "N/A",
            "Founders": [],
            "Founder LinkedIns": [],
            "Emails": [],
            "YC Link": url
        }

        # 1. Company Name
        h1 = soup.find('h1')
        if h1:
            data["Company Name"] = h1.get_text(strip=True)

        # 2. Website
        # Look for links in the top section usually containing external URLs
        # Based on your screenshots, it's often a link with text or icon
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            # Simple heuristic: if it's not a YC link and not social media, it's likely the website
            if "http" in href and "ycombinator" not in href and "linkedin" not in href and "twitter" not in href:
                # Often the website link is near the top
                if link.parent.name in ['div', 'span', 'h1', 'h2']: 
                    data["Website"] = href
                    break # Take the first valid external link found

        # 3. Founders & LinkedIns
        # YC pages usually have a "Founders" section. 
        # We look for divs that contain "Founder" text or look like cards.
        founder_divs = soup.find_all('div', class_=lambda x: x and 'founder' in x.lower() if x else False)
        
        # If class search fails, look for specific layout based on your screenshot
        if not founder_divs:
            # Fallback: Search for the "Active Founders" header and get siblings
            header = soup.find(string=re.compile("Active Founders"))
            if header:
                parent_section = header.find_parent('div').find_parent('div')
                if parent_section:
                    founder_divs = parent_section.find_all('div', recursive=False)

        for div in founder_divs:
            # Get Name (usually the bold text or first div)
            name = div.get_text(strip=True).split('Founder')[0] # Clean up text
            # Get LinkedIn
            linkedin_link = div.find('a', href=re.compile("linkedin.com"))
            
            if name and len(name) < 50: # Sanity check on name length
                data["Founders"].append(name)
            if linkedin_link:
                data["Founder LinkedIns"].append(linkedin_link['href'])

        # 4. Emails (Hardest part)
        # Check for mailto links
        mailto = soup.select_one('a[href^="mailto:"]')
        if mailto:
            data["Emails"].append(mailto['href'].replace("mailto:", ""))
        
        # Regex search in text (for visible emails like contact@domain.com)
        text_emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", soup.get_text())
        # Filter out junk emails
        clean_emails = [e for e in text_emails if "ycombinator" not in e and "sentry" not in e] 
        data["Emails"].extend(clean_emails)

        # Cleanup lists
        data["Founders"] = ", ".join(list(set(data["Founders"])))
        data["Founder LinkedIns"] = ", ".join(list(set(data["Founder LinkedIns"])))
        data["Emails"] = ", ".join(list(set(data["Emails"])))

        print(f"Scraped: {data['Company Name']}")
        return data

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    driver = get_driver()
    try:
        # Step 1: Get Links
        links = scrape_internship_links(driver)
        
        # Step 2: Scrape Details
        all_data = []
        for link in links:
            result = extract_company_data(driver, link)
            if result:
                all_data.append(result)
        
        # Step 3: Save to CSV
        keys = ["Company Name", "Website", "Founders", "Founder LinkedIns", "Emails", "YC Link"]
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_data)
            
        print(f"\nDone! Data saved to {OUTPUT_FILE}")
        
    finally:
        driver.quit()
import time
import csv
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
TARGET_URL = "https://www.ycombinator.com/internships"
OUTPUT_FILE = "yc_internships_data.csv"
SCROLL_PAUSE_TIME = 2  # Time to wait after scrolling for content to load
MAX_COMPANIES = 10     # Limit for testing. Set to 100+ for full run.

def get_driver():
    """Setup Chrome Driver for WSL (Headless)."""
    options = webdriver.ChromeOptions()
    
    # --- REQUIRED FOR WSL ---
    options.add_argument("--headless")              # Run without a visible UI
    options.add_argument("--no-sandbox")            # Bypass OS security model (needed for Docker/WSL)
    options.add_argument("--disable-dev-shm-usage") # Overcome limited resource problems
    options.add_argument("--window-size=1920,1080") # meaningful size for scraping
    
    # Initialize driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def scrape_internship_links(driver):
    """Scrolls the internship page and grabs company profile URLs."""
    print(f"Loading {TARGET_URL}...")
    driver.get(TARGET_URL)
    time.sleep(5)  # Initial load wait

    company_links = set()
    
    # Scroll logic to load more items (YC uses infinite scroll)
    # For this demo, we scroll 3 times. Increase range for more results.
    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        
        # Parse current state
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find links that look like /companies/xxx
        # YC usually links the company name or logo to the profile
        for a in soup.find_all('a', href=True):
            if "/companies/" in a['href'] and "jobs" not in a['href']:
                full_link = f"https://www.ycombinator.com{a['href']}"
                company_links.add(full_link)
                
                if len(company_links) >= MAX_COMPANIES:
                    break
        
        if len(company_links) >= MAX_COMPANIES:
            break

    print(f"Found {len(company_links)} unique companies.")
    return list(company_links)

def extract_company_data(driver, url):
    """Visits a company page and extracts details."""
    try:
        driver.get(url)
        time.sleep(2) # Politeness wait
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        data = {
            "Company Name": "N/A",
            "Website": "N/A",
            "Founders": [],
            "Founder LinkedIns": [],
            "Emails": [],
            "YC Link": url
        }

        # 1. Company Name
        h1 = soup.find('h1')
        if h1:
            data["Company Name"] = h1.get_text(strip=True)

        # 2. Website
        # Look for links in the top section usually containing external URLs
        # Based on your screenshots, it's often a link with text or icon
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            # Simple heuristic: if it's not a YC link and not social media, it's likely the website
            if "http" in href and "ycombinator" not in href and "linkedin" not in href and "twitter" not in href:
                # Often the website link is near the top
                if link.parent.name in ['div', 'span', 'h1', 'h2']: 
                    data["Website"] = href
                    break # Take the first valid external link found

        # 3. Founders & LinkedIns
        # YC pages usually have a "Founders" section. 
        # We look for divs that contain "Founder" text or look like cards.
        founder_divs = soup.find_all('div', class_=lambda x: x and 'founder' in x.lower() if x else False)
        
        # If class search fails, look for specific layout based on your screenshot
        if not founder_divs:
            # Fallback: Search for the "Active Founders" header and get siblings
            header = soup.find(string=re.compile("Active Founders"))
            if header:
                parent_section = header.find_parent('div').find_parent('div')
                if parent_section:
                    founder_divs = parent_section.find_all('div', recursive=False)

        for div in founder_divs:
            # Get Name (usually the bold text or first div)
            name = div.get_text(strip=True).split('Founder')[0] # Clean up text
            # Get LinkedIn
            linkedin_link = div.find('a', href=re.compile("linkedin.com"))
            
            if name and len(name) < 50: # Sanity check on name length
                data["Founders"].append(name)
            if linkedin_link:
                data["Founder LinkedIns"].append(linkedin_link['href'])

        # 4. Emails (Hardest part)
        # Check for mailto links
        mailto = soup.select_one('a[href^="mailto:"]')
        if mailto:
            data["Emails"].append(mailto['href'].replace("mailto:", ""))
        
        # Regex search in text (for visible emails like contact@domain.com)
        text_emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", soup.get_text())
        # Filter out junk emails
        clean_emails = [e for e in text_emails if "ycombinator" not in e and "sentry" not in e] 
        data["Emails"].extend(clean_emails)

        # Cleanup lists
        data["Founders"] = ", ".join(list(set(data["Founders"])))
        data["Founder LinkedIns"] = ", ".join(list(set(data["Founder LinkedIns"])))
        data["Emails"] = ", ".join(list(set(data["Emails"])))

        print(f"Scraped: {data['Company Name']}")
        return data

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    driver = get_driver()
    try:
        # Step 1: Get Links
        links = scrape_internship_links(driver)
        
        # Step 2: Scrape Details
        all_data = []
        for link in links:
            result = extract_company_data(driver, link)
            if result:
                all_data.append(result)
        
        # Step 3: Save to CSV
        keys = ["Company Name", "Website", "Founders", "Founder LinkedIns", "Emails", "YC Link"]
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_data)
            
        print(f"\nDone! Data saved to {OUTPUT_FILE}")
        
    finally:
        driver.quit()
