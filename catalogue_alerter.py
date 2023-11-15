import argparse
import re
import asyncio
import pyppeteer
from datetime import datetime

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

async def scrape_coles_catalogue(browser, upcoming: bool = True, catalogue_pages: list[str] = ['page1', 'page2', 'page3']):
    '''
    Scrapes pages from the Coles catalogue (if it is available).
    '''
    # Create a new page and go to the cole catalogue website
    page = await browser.newPage()
    await page.goto("https://www.coles.com.au/catalogues")

    # Open up the catalogue and handle exception scenarios
    catalogue_button = None
    try:
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

    # Retrieve item titles (got help from ChatGPT for code below)
    await page.waitForXPath('//a[@aria-label="Specials of the Week"]') # Wait for the anchors on the pages to load
    titles = await page.evaluate('''() => {
        const titles = [];
        const pageNames = [''' + ''.join(f'"{cp}", ' for cp in catalogue_pages)[:-2] + '''];
        const allElements = [];

        pageNames.forEach(pageName => {
        const selector = `li.${pageName} .slide-content.objloaded a`;
        const elements = Array.from(document.querySelectorAll(selector));
        allElements.push(...elements);
        });

        allElements.forEach((element) => {
            if (element instanceof HTMLAnchorElement && element.title != '') {
                titles.push(element.title);
            }
        });
        return titles;
    }''')

    return titles

async def scrape_woolworths_catalogue(browser, postcode: str, upcoming: bool = True, catalogue_pages: list[str] = ['page0', 'page1', 'page2']):
    '''
    Scrapes pages from the woolworths catalogue (if it is available).
    '''
    # Create a new page and go to the woolworths catalogue website
    page = await browser.newPage()
    await page.setUserAgent("Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322)"); # Pyppeteer user agent is blocked by Woolworths so we change it
    await page.goto("https://www.woolworths.com.au/shop/catalogue")

    # Provide the postcode and open the first location that pops up
    try:
        catalogue_location_autocomplete = await page.waitForXPath('//input[@id="wx-digital-catalogue-autocomplete"]')
        await catalogue_location_autocomplete.type(postcode)
        catalogue_location_first_autocomplete = await page.waitForXPath('//li[@id="wx-digital-catalogue-autocomplete__option--0"]')
        await catalogue_location_first_autocomplete.click()
        # await page.waitForNavigation()
    except pyppeteer.errors.TimeoutError as timeout_error:
        print(f'Failed to retrieve elements to select the Woolworths location using the provided postcode within 30 seconds')
        print(timeout_error)
        return []
    except Exception as exception:
        print('Something went wrong when trying to retrieve elements to select the Woolworths location using the provided postcode')
        print(exception)
        return []

    # TODO: Test and accomodate upcoming catalogue
    # Note that Woolworths does not have an upcoming catalogue option
    # The Woolworths xpath is more specific to avoid selecting more than one catalogue
    catalogue_button = await page.waitForXPath('//div[@class="catalogue-content" and ./h3[@class="heading5" and contains(text(), "Weekly Specials")]]/a[@class="read-catalogue"]') # Element is dynamically loaded in so we must wait for it to become visible.
    catalogue_url = await page.evaluate('(element) => element.getAttribute("href")', catalogue_button)
    await page.goto('https://www.woolworths.com.au' + catalogue_url, options={'waitUntil':'networkidle0'}) # Wait for the anchors on the pages to load
    
    # Retrieve item titles (got help from ChatGPT for code below)
    titles = await page.evaluate('''() => {
        const titles = [];
        const pageNames = [''' + ''.join(f'"{cp}", ' for cp in catalogue_pages)[:-2] + '''];
        const allElements = [];

        pageNames.forEach(pageName => {
        const selector = `li.${pageName} .slide-content.objloaded a`;
        const elements = Array.from(document.querySelectorAll(selector));
        allElements.push(...elements);
        });

        allElements.forEach((element) => {
            if (element instanceof HTMLAnchorElement && element.title != '') {
                titles.push(element.title);
            }
        });
        return titles;
    }''')

    return titles

async def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Catalogue Alerter')
    parser.add_argument('--read', '-r', type=str, default='items.txt', help='File name to read items to alert on')
    parser.add_argument('--output-alerts', '-a', action=argparse.BooleanOptionalAction, default=True, help='Append alerts to files')
    parser.add_argument('--output-items', '-i', action=argparse.BooleanOptionalAction, default=False, help='Append items found in both catalogues to files')
    parser.add_argument('--post-code', '-p', required=True, type=str, help='Postcode to use when scraping from Woolworths')
    parser.add_argument('--headless-mode', action=argparse.BooleanOptionalAction, default=True, help="Runs the browser without a user interface")
    parser.add_argument('--chrome-path', '-e', type=str, help='Absolute path to the achrome file executable')
    args = parser.parse_args()

    print(args)

    # Read items arguments
    alert_items = read_alert_items(args.read)
    chrome_path = args.chrome_path
    try:
        # For testing purposes only
        chrome_path = "C:\Program Files\Google\Chrome\Application\chrome.exe"

        # pyppeteer will use a default executable path if args.chrome_path is None
        browser = await pyppeteer.launch(executablePath=chrome_path, headless=args.headless_mode)
        
        # Search the Coles catalogue
        coles_catalogue_items = await scrape_coles_catalogue(browser, upcoming=False)
        coles_matches = match_items(alert_items, coles_catalogue_items)
        print(f'Coles matches: {coles_matches}')

        # Search the Woolworths catalogue
        woolworths_catalogue_items = await scrape_woolworths_catalogue(browser, postcode=args.post_code, upcoming=False)
        woolworths_matches = match_items(alert_items, woolworths_catalogue_items)
        print(f'Woolworths matches: {woolworths_matches}')

        # Write catalogue items
        if args.output_items:
            with open('out/coles_catalogue.log', 'a', encoding='utf-8') as file:
                for item in coles_catalogue_items:
                    file.write(f'{datetime.now().strftime("%Y-%m-%d")} {item}\n')
            with open('out/woolworths_catalogue.log', 'a', encoding='utf-8') as file:
                for item in woolworths_catalogue_items:
                    file.write(f'{datetime.now().strftime("%Y-%m-%d")} {item}\n')
        
        # Write alerts
        if args.output_alerts:
            with open('out/coles_alerts.log', 'a', encoding='utf-8') as file:
                for match in coles_matches:
                    file.write(f'{datetime.now().strftime("%Y-%m-%d")} {match}')
            with open('out/woolworths_alerts.log', 'a', encoding='utf-8') as file:
                for match in woolworths_matches:
                    file.write(f'{datetime.now().strftime("%Y-%m-%d")} {match}')

        # TODO: email alerts
    except Exception as e:
        print('Error:', type(e), '-', str(e))
    finally:
        # Close the browser
        if 'browser' in locals():
            await browser.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())