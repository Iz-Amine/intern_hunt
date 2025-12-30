
import time
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
TARGET_URL = "https://www.ycombinator.com/internships"
OUTPUT_FILE = "yc_internships_contacts.json"
SCROLL_PAUSE_TIME = 2
MAX_SCROLLS = 10  # Increase to get more companies
POLITENESS_DELAY = 1.5  # Be respectful to servers

def get_driver():
    """Setup Chrome Driver with optimal settings."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def scrape_internship_companies(driver):
    """Scrapes company links from the internships page."""
    logger.info(f"Loading {TARGET_URL}...")
    driver.get(TARGET_URL)
    time.sleep(5)
    
    company_data = {}
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    for scroll in range(MAX_SCROLLS):
        logger.info(f"Scroll {scroll + 1}/{MAX_SCROLLS}")
        
        # Parse current page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all company listings
        # Each listing typically has a link to /companies/[company-name]
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            # Match company profile links
            if '/companies/' in href and '/jobs' not in href:
                company_url = f"https://www.ycombinator.com{href}" if href.startswith('/') else href
                
                # Extract company name from URL
                company_name = href.split('/companies/')[-1].split('/')[0]
                
                if company_name and company_url not in company_data.values():
                    company_data[company_name] = company_url
        
        # Scroll down
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        
        # Check if we've reached the bottom
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            logger.info("Reached bottom of page")
            break
        last_height = new_height
    
    logger.info(f"Found {len(company_data)} unique companies")
    return company_data

def extract_email_from_text(text):
    """Extract emails using regex, filtering out common false positives."""
    emails = re.findall(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', text)
    
    # Filter out common junk
    exclude_domains = ['ycombinator.com', 'sentry.io', 'example.com', 'test.com']
    clean_emails = [e for e in emails if not any(d in e.lower() for d in exclude_domains)]
    
    return clean_emails

def extract_company_details(driver, company_name, company_url):
    """Extracts detailed information from a company's YC profile page."""
    try:
        logger.info(f"Scraping: {company_name}")
        driver.get(company_url)
        time.sleep(POLITENESS_DELAY)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        data = {
            "company_name": company_name,
            "yc_profile": company_url,
            "website": "",
            "founders": [],
            "founder_linkedin_urls": [],
            "emails_found": []
        }
        
        # 1. Extract Company Website
        # Look for external links that aren't social media
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            # Identify website link (usually prominent and not YC/social)
            if ('http://' in href or 'https://' in href) and \
               'ycombinator.com' not in href and \
               'linkedin.com' not in href and \
               'twitter.com' not in href and \
               'x.com' not in href and \
               'github.com' not in href and \
               'facebook.com' not in href:
                # Often the company website is the first external link
                data["website"] = href
                break
        
        # 2. Extract Founders Information
        # Look for "Active Founders" section
        founders_section = soup.find(string=re.compile(r"Active Founders?", re.IGNORECASE))
        
        if founders_section:
            # Navigate to the founders container
            container = founders_section.find_parent('div')
            if container:
                # Find all founder cards within this section
                # Founders usually have their name, title, and social links
                founder_cards = container.find_all_next('div', limit=20)
                
                for card in founder_cards:
                    card_text = card.get_text(strip=True)
                    
                    # Check if this looks like a founder card
                    if 'Founder' in card_text or 'Co-founder' in card_text or 'CEO' in card_text:
                        # Extract name (usually the first/bold text)
                        name_tag = card.find(['strong', 'b', 'h3', 'h4'])
                        if name_tag:
                            name = name_tag.get_text(strip=True)
                        else:
                            # Fallback: extract first line that looks like a name
                            lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                            name = lines[0] if lines else ""
                        
                        # Clean up name
                        name = name.replace('Founder', '').replace('Co-founder', '').replace('CEO', '').strip()
                        
                        # Validate name (basic heuristic)
                        if name and 2 < len(name) < 50 and not name.startswith('http'):
                            data["founders"].append(name)
                        
                        # Extract LinkedIn
                        linkedin = card.find('a', href=re.compile(r'linkedin\.com/in/', re.IGNORECASE))
                        if linkedin:
                            data["founder_linkedin_urls"].append(linkedin.get('href'))
        
        # Alternative founder extraction if above fails
        if not data["founders"]:
            # Look for any LinkedIn links as fallback
            linkedin_links = soup.find_all('a', href=re.compile(r'linkedin\.com/in/', re.IGNORECASE))
            for link in linkedin_links:
                url = link.get('href')
                # Try to get associated name
                parent = link.find_parent(['div', 'span'])
                if parent:
                    text = parent.get_text(strip=True)
                    # Extract name from text near LinkedIn link
                    name = text.split('\n')[0].strip()
                    if name and 2 < len(name) < 50:
                        data["founders"].append(name)
                        data["founder_linkedin_urls"].append(url)
        
        # 3. Extract Emails
        # Check for mailto links
        mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.IGNORECASE))
        for link in mailto_links:
            email = link.get('href').replace('mailto:', '').split('?')[0]
            data["emails_found"].append(email)
        
        # Also search page text for email patterns
        page_text = soup.get_text()
        text_emails = extract_email_from_text(page_text)
        data["emails_found"].extend(text_emails)
        
        # Remove duplicates and preserve order
        data["founders"] = list(dict.fromkeys(data["founders"]))
        data["founder_linkedin_urls"] = list(dict.fromkeys(data["founder_linkedin_urls"]))
        data["emails_found"] = list(dict.fromkeys(data["emails_found"]))
        
        logger.info(f"✓ Extracted: {data['company_name']} | Founders: {len(data['founders'])} | Website: {bool(data['website'])}")
        
        return data
        
    except Exception as e:
        logger.error(f"Error scraping {company_name}: {e}")
        return None

def save_to_json(data_list, filename):
    """Save collected data to JSON with pretty formatting."""
    if not data_list:
        logger.warning("No data to save!")
        return
    
    output = {
        "metadata": {
            "total_companies": len(data_list),
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "YC Internships"
        },
        "companies": data_list
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ Data saved to {filename}")

def main():
    driver = get_driver()
    
    try:
        # Step 1: Get all company links from internships page
        company_dict = scrape_internship_companies(driver)
        
        logger.info(f"\nStarting detailed scraping of {len(company_dict)} companies...")
        
        # Step 2: Extract details for each company
        all_data = []
        for idx, (company_name, company_url) in enumerate(company_dict.items(), 1):
            logger.info(f"\n[{idx}/{len(company_dict)}] Processing {company_name}...")
            
            result = extract_company_details(driver, company_name, company_url)
            if result:
                all_data.append(result)
            
            # Be polite to servers
            time.sleep(POLITENESS_DELAY)
        
        # Step 3: Save to JSON
        save_to_json(all_data, OUTPUT_FILE)
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("SCRAPING COMPLETE!")
        logger.info(f"Total companies scraped: {len(all_data)}")
        logger.info(f"Companies with websites: {sum(1 for d in all_data if d['website'])}")
        logger.info(f"Companies with founder info: {sum(1 for d in all_data if d['founders'])}")
        logger.info(f"Companies with LinkedIn profiles: {sum(1 for d in all_data if d['founder_linkedin_urls'])}")
        logger.info(f"Companies with emails: {sum(1 for d in all_data if d['emails_found'])}")
        logger.info(f"Output file: {OUTPUT_FILE}")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    
    finally:
        driver.quit()
        logger.info("Browser closed")

if __name__ == "__main__":
    main()
