import argparse
import re
import asyncio
import pyppeteer
from datetime import datetime
import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText # For formatting
import ssl # For additional layer of security
from dotenv import load_dotenv
import os

OUT_FOLDER = 'out'

def match_items(alert_items: list[str], catalogue_items: list[str]) -> list[str]:
    '''
    Finds case-insensitive occurances of match_items inside catalogue_items.
    '''
    matches = []
    for alert_item in alert_items:
        alert_item = alert_item.lower()
        for catalogue_item in catalogue_items:
            catalogue_item = catalogue_item.lower()
            if alert_item in catalogue_item:
                matches.append(f'{alert_item}: {catalogue_item}')
    return matches

def read_alert_items(file_name: str ='items.txt'):
    '''
    Reads file contents of provided file with hashtags (#) acting as comments (ignored).
    '''
    try:
        alert_items = []
        with open(file_name, 'r') as file:
            for line in file:
                # Remove leading and trailing whitespaces
                line = line.strip()
                
                # Handle line continuation (if line ends with '\')
                while line.endswith('\\'):
                    next_line = next(file, '').strip()
                    line = line[:-1] + next_line

                # Split the line at the first '#' character to remove comments
                parts = re.split(r'(?<!\\)#', line, 1)
                line = parts[0].strip()

                # Check if the line is empty after removing comments
                if not line:
                    continue

                # Unescape escaped '#' characters within the line (e.g., '\#item' becomes '#item')
                line = line.replace('\\#', '#')

                # Add the line to the list
                alert_items.append(line)

        return alert_items
    except FileNotFoundError:
        print(f"File '{file_name}' not found.")
        return []

def format_email(date_time: str, upcoming: bool,
                 coles_matches: list[str] = [], woolworths_matches: list[str] = [],
                 coles_catalogue_items: list[str] = [], woolworths_catalogue_items: list[str] = []) -> EmailMessage:
    '''
    Formats an email to be sent without specifying the to and from.
    '''
    nl = '\n'   # New line
    msg = EmailMessage()
    msg['Subject'] = f'{date_time} (upcoming={upcoming}) Catalogue Alert'
    body = f'''
<h1>Catalogue Alerter</h1>
Triggered at {date_time}

<h2>Alerts<h2>
<h3><font color="red">Coles Alerts</font></h3>
<ui>
{''.join(f'<li>{match}</li>' for match in coles_matches)}
</ui>

<h3><font color="green">Woolworths Alerts</font></h3>
<ui>
{''.join(f'<li>{match}</li>' for match in woolworths_matches)}
</ui>

<br>
<br>

<h2>Catalogue Items<h2>
<h3><font color="red">Coles Catalogue Items</font></h3>
<ui>
{''.join(f'<li>{item}</li>' for item in coles_catalogue_items)}
</ui>

<h3><font color="red">Woolworths Catalogue Items</font></h3>
<ui>
{''.join(f'<li>{item}</li>' for item in woolworths_catalogue_items)}
</ui>
'''
    msg.set_content(MIMEText(body, 'html'))
    return msg

async def scrape_coles_catalogue(browser, upcoming: bool = False, catalogue_pages: list[str] = []):
    '''
    Scrapes pages from the Coles catalogue (if it is available).
    '''
    # Create a new page and go to the cole catalogue website
    page = await browser.newPage()
    await page.goto("https://www.coles.com.au/catalogues")

    # Open up the catalogue and handle exception scenarios
    catalogue_button = None
    try:
        # Use aria-label to select the upcoming or current catalogue
        button_to_retrieve = '"View next week\'s catalogue"' if upcoming else '"View this week\'s catalogue"'
        catalogue_button = await page.waitForXPath(f'//a[@aria-label={button_to_retrieve}]')
    except pyppeteer.errors.TimeoutError as timeout_error:
        print(f'Failed to retrieve Coles catalogue button {button_to_retrieve} within 30 seconds')
        print(timeout_error)
        return []
    except Exception as exception:
        print(f'Something went wrong when trying to retrieve Coles catalogue button {button_to_retrieve}')
        print(exception)
        return []
    catalogue_url = await page.evaluate('(element) => element.getAttribute("href")', catalogue_button)
    await page.goto('https://www.coles.com.au' + catalogue_url)

    # Retrieve item titles
    await page.waitForXPath('//a[@aria-label="Specials of the Week"]') # Wait for the anchors on the pages to load
    titles = []
    if len(catalogue_pages) > 0:
        titles = await page.evaluate('''() => {
            const titles = [];
            const pageNames = [''' + ''.join(f'"{cp}", ' for cp in catalogue_pages)[:-2] + '''];
            const allElements = [];

            pageNames.forEach(pageName => {
                const selector = `li.${pageName} .slide-content.objloaded a[href*="product"]`;
                const elements = Array.from(document.querySelectorAll(selector));
                allElements.push(...elements);
            });

            allElements.forEach((element) => {
                if (element instanceof HTMLAnchorElement && element.title != '' && titles.indexOf(element.title) == -1) {
                    titles.push(element.title);
                }
            });
            return titles;
        }''')
    else:
        titles = await page.evaluate('''() => {
            const titles = [];
            const allElements = [];

            const elements = Array.from(document.querySelectorAll('.slide-content.objloaded a[href*="product"]'));
            allElements.push(...elements);

            allElements.forEach((element) => {
                if (element instanceof HTMLAnchorElement && element.title != '' && titles.indexOf(element.title) == -1) {
                    titles.push(element.title);
                }
            });
            return titles;
        }''')

    return titles

async def scrape_woolworths_catalogue(browser, postcode: str, upcoming: bool = False, catalogue_pages: list[str] = []):
    '''
    Scrapes pages from the woolworths catalogue (if it is available).
    '''
    # Create a new page and go to the woolworths catalogue website
    page = await browser.newPage()
    await page.setUserAgent("Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322)") # Pyppeteer user agent is blocked by Woolworths so we change it
    await page.goto("https://www.woolworths.com.au/shop/catalogue")

    # Provide the postcode and open the first location that pops up
    try:
        catalogue_location_autocomplete = await page.waitForXPath('//input[@id="wx-digital-catalogue-autocomplete"]')
        await catalogue_location_autocomplete.type(postcode, options={'delay': 10})
        catalogue_location_first_autocomplete = await page.waitForXPath('//li[@id="wx-digital-catalogue-autocomplete-item-0"]')
        await page.evaluate('button => button.click()', catalogue_location_first_autocomplete)    # Using 'await catalogue_location_first_autocomplete.click()' is unreliable
    except pyppeteer.errors.TimeoutError as timeout_error:
        print(f'Failed to retrieve elements to select the Woolworths location using the provided postcode within 30 seconds')
        print(timeout_error)
        return []
    except Exception as exception:
        print('Something went wrong when trying to retrieve elements to select the Woolworths location using the provided postcode')
        print(exception)
        return []

    # Handle exception scenarios including timeout due to element not found
    catalogue_button = None
    try:
        if upcoming:
            # BUG: Woolworths scraper will not work for the upcoming catalogue as the xpath has not been updated to work with the updated woolworths website
            # BUG: The Woolworths xpath may need to be more specific to avoid selecting more than one catalogue
            print('WARNING: A bug in the program prevents it from scraping the Woolworths upcoming catalogue')
            catalogue_button = await page.waitForXPath('//div[@class="catalogue-content" and ./h3[@class="heading5" and contains(text(), "Weekly Specials")] and ./p[@class="disclaimer-info"]]/a[@class="read-catalogue"]')
        else:
            catalogue_button = await page.waitForXPath('//div[@class="tile_component_content__pkyso" and ./div[@class="tile_component_heading__6SeSl" and contains(text(), "Weekly Specials")]]/a[@class="core-button core-button-secondary"]')
    except pyppeteer.errors.TimeoutError as timeout_error:
        button_type = 'upcoming' if upcoming else 'not upcoming'
        print(f'Failed to retrieve Woolworths {button_type} catalogue button within 30 seconds')
        print(timeout_error)
        return []
    except Exception as exception:
        print(f'Something went wrong when trying to retrieve Coles catalogue button {button_to_retrieve}')
        print(exception)
        return []
    catalogue_url = await page.evaluate('(element) => element.getAttribute("href")', catalogue_button)
    await page.goto('https://www.woolworths.com.au' + catalogue_url, options={'waitUntil':'networkidle0'}) # Wait for the anchors on the pages to load
    
    # Retrieve item titles
    if len(catalogue_pages) > 0:
        titles = await page.evaluate('''() => {
            const titles = [];
            const pageNames = [''' + ''.join(f'"{cp}", ' for cp in catalogue_pages)[:-2] + '''];
            const allElements = [];

            pageNames.forEach(pageName => {
            const selector = `li.${pageName} .slide-content.objloaded a[href*="product"]`;
            const elements = Array.from(document.querySelectorAll(selector));
            allElements.push(...elements);
            });

            allElements.forEach((element) => {
                if (element instanceof HTMLAnchorElement && element.title != '' && titles.indexOf(element.title) == -1) {
                    titles.push(element.title);
                }
            });
            return titles;
        }''')
    else:
        titles = await page.evaluate('''() => {
            const titles = [];
            const allElements = [];

            const elements = Array.from(document.querySelectorAll('.slide-content.objloaded a[href*="product"]'));
            allElements.push(...elements);

            allElements.forEach((element) => {
                if (element instanceof HTMLAnchorElement && element.title != '' && titles.indexOf(element.title) == -1) {
                    titles.push(element.title);
                }
            });
            return titles;
        }''')

    return titles

async def main():
    # Reference: https://www.geeksforgeeks.org/how-to-pass-a-list-as-a-command-line-argument-with-argparse/
    def list_of_strings(arg):
        return arg.split(',')
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Catalogue Alerter')
    parser.add_argument('--read', '-r', type=str, default='items.txt', help='File name to read items to alert on (default: items.txt)')
    parser.add_argument('--output-alerts', '-a', action=argparse.BooleanOptionalAction, default=True, help='Append alerts to files')
    parser.add_argument('--output-items', '-i', action=argparse.BooleanOptionalAction, default=False, help='Append items found in both catalogues to files')
    parser.add_argument('--postcode', '-p', type=str, help='Postcode to use when scraping from Woolworths (required if scraping from Woolworths)')
    parser.add_argument('--headless-mode', action=argparse.BooleanOptionalAction, default=True, help='Runs the browser without a user interface')
    parser.add_argument('--chrome-path', '-x', type=str, help='Absolute path to the achrome file executable')
    parser.add_argument('--coles', action=argparse.BooleanOptionalAction, default=True, help='Searches the Coles catalogue')
    parser.add_argument('--woolworths', action=argparse.BooleanOptionalAction, default=True, help='Searches the woolworths catalogue')
    parser.add_argument('--upcoming', action=argparse.BooleanOptionalAction, default=False, help='To search the upcoming catalogues')
    parser.add_argument('--coles-pages', type=list_of_strings, default=[], help='Provide a list of pages to search in the coles catalogue, e.g. page0,page1,page2 where providing nothing has the program search all pages')
    parser.add_argument('--woolworths-pages', type=list_of_strings, default=[], help='Provide a list of pages to search in the woolworths catalogue, e.g. page0,page1,page2 where providing nothing has the program search all pages')
    parser.add_argument('--email', '-e', type=list_of_strings, default=[], help='Provide a list of email addresses to send alerts and catalogue lists to. You must have a .env file to use this functionality, see env.example.txt for an example')
    args = parser.parse_args()

    # Ensure postcode is provided if scraping from woolworths
    if args.woolworths and args.postcode is None:
        parser.error('--woolworths requires --postcode (-p). Note --woolworths is true by default and can be set to false using --no-woolworths')

    # Read items arguments
    alert_items = read_alert_items(args.read)
    chrome_path = args.chrome_path
    try:
        # pyppeteer will use a default executable path if args.chrome_path is None
        browser = await pyppeteer.launch(executablePath=chrome_path, headless=args.headless_mode)
        
        # Search the Coles catalogue
        if args.coles:
            coles_catalogue_items = await scrape_coles_catalogue(browser, upcoming=args.upcoming, catalogue_pages=args.coles_pages)
            coles_matches = match_items(alert_items, coles_catalogue_items)
            print(f'Coles matches: {coles_matches}')

        # Search the Woolworths catalogue
        if args.woolworths:
            woolworths_catalogue_items = await scrape_woolworths_catalogue(browser, postcode=args.postcode, upcoming=args.upcoming, catalogue_pages=args.woolworths_pages)
            woolworths_matches = match_items(alert_items, woolworths_catalogue_items)
            print(f'Woolworths matches: {woolworths_matches}')

        # Write catalogue items
        if args.output_items:
            if args.coles:
                with open('out/coles_catalogue.log', 'a', encoding='utf-8') as file:
                    for item in coles_catalogue_items:
                        file.write(f'{datetime.now()} catalogue=coles upcoming={args.upcoming} catalogue_pages={args.coles_pages} title={item}\n')
            if args.woolworths:
                with open('out/woolworths_catalogue.log', 'a', encoding='utf-8') as file:
                    for item in woolworths_catalogue_items:
                        file.write(f'{datetime.now()} catalogue=woolworths upcoming={args.upcoming} catalogue_pages={args.woolworths_pages} postcode={args.postcode} title={item}\n')
        
        # Write alerts
        if args.output_alerts:
            if args.coles:
                with open('out/coles_alerts.log', 'a', encoding='utf-8') as file:
                    for match in coles_matches:
                        file.write(f'{datetime.now()} (upcoming={args.upcoming}) {match}')
            if args.woolworths:
                with open('out/woolworths_alerts.log', 'a', encoding='utf-8') as file:
                    for match in woolworths_matches:
                        file.write(f'{datetime.now()} (upcoming={args.upcoming}) {match}')

        if len(args.email) > 0:
            # Load environment variables from .env file
            load_dotenv()
            gmail_address = os.getenv('GMAIL_ADDRESS')
            gmail_app_password = os.getenv('GMAIL_APP_PASSWORD')
            if gmail_address == None or gmail_app_password == None:
                raise IOError('.env or environment variables GMAIL_ADDRESS or GMAIL_APP_PASSWORD are missing')
            
            # Prepare default values for variables to avoid errors
            coles_matches = [] if 'coles_matches' not in locals() else coles_matches
            woolworths_matches = [] if 'woolworths_matches' not in locals() else woolworths_matches
            coles_catalogue_items = [] if 'coles_catalogue_items' not in locals() else coles_catalogue_items
            woolworths_catalogue_items = [] if 'woolworths_catalogue_items' not in locals() else woolworths_catalogue_items

            # Prepare email
            dt = datetime.now().strftime("%Y-%m-%d %H:%M")
            msg = format_email(dt, args.upcoming,
                               coles_matches,
                               woolworths_matches,
                               coles_catalogue_items,
                               woolworths_catalogue_items)
            msg['From'] = gmail_address
            msg['To'] = ', '.join(args.email)

            # Authenticate to GMail and send email
            ssl_context = ssl.create_default_context()
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl_context) as smtp:  # Gmail uses port 465 for SMTPS (Simple Mail Transfer Protocol Secure)
                smtp.login(gmail_address, gmail_app_password)
                smtp.sendmail(gmail_address, args.email, msg.as_string())

    except Exception as e:
        print('Error:', type(e), '-', str(e))
    finally:
        # Close the browser
        if 'browser' in locals():
            await browser.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())