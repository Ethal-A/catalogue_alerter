import argparse
import re
import asyncio
import pyppeteer

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
    # FIX: Only captures anchors on last page
    titles = await page.evaluate('''() => {
    const titles = [];
    const elements = document.querySelectorAll(\''''+ ''.join(f'li.{cp}, ' for cp in catalogue_pages)[:-2] + ''' .slide-content.objloaded a');
    elements.forEach((element) => {
        if (element instanceof HTMLAnchorElement) {
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
    await page.goto("https://www.woolworths.com.au/shop/catalogue")

    # Provide the postcode and open the first location that pops up
    try:
        catalogue_location_autocomplete = await page.waitForXPath('//input[@id="wx-digital-catalogue-autocomplete"]')
        await catalogue_location_autocomplete.type(postcode)
        catalogue_location_first_autocomplete = await page.waitForXPath('//li[@id="wx-digital-catalogue-autocomplete__option--0"]')
        await catalogue_location_first_autocomplete.click()
    except pyppeteer.errors.TimeoutError as timeout_error:
        print(f'Failed to retrieve elements to select the Woolworths location using the provided postcode within 30 seconds')
        print(timeout_error)
        return []
    except Exception as exception:
        print('Something went wrong when trying to retrieve elements to select the Woolworths location using the provided postcode')
        print(exception)
        return []

    # TODO: Test and accomodate upcoming catalogue
    # TODO: Handle exception scenarios
    # FIX: Getting error 'Error: Node is either not visible or not an HTMLElement'
    # Open up the catalogue
    catalogue_button = await page.waitForXPath('//a[@class="read-catalogue"]') # Element is dynamically loaded in so we must wait for it to become visible.
    await catalogue_button.click()

    # Retrieve item titles (got help from ChatGPT for code below)
    await page.waitForXPath('//div[@id="sf-catalogue"]') # Wait for the anchors on the pages to load
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
    parser.add_argument('--output-alerts', '-o', type=str, default='alerts.txt', help='File name to output alerts')
    parser.add_argument('--output-catalogue', '-c', type=str, help='File name to output catalogue items')
    args = parser.parse_args()

    # Read items to alert on
    alert_items = read_alert_items(args.read)
    try:
        # TODO: Make the executable path an input that the user can provide
        browser = await pyppeteer.launch(executablePath="C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
        coles_catalogue_items = await scrape_coles_catalogue(browser, upcoming=False)
        woolworths_catalogue_items = await scrape_woolworths_catalogue(browser, postcode='TODO', upcoming=False)
        coles_matches = match_items(alert_items, coles_catalogue_items)
        woolworths_matches = match_items(alert_items, woolworths_catalogue_items)

        # Print results
        print(f'woolworths: {woolworths_catalogue_items}')
        print(f'Woolworths matches: {woolworths_matches}')
        print(f'Coles matches: {coles_matches}')
    except Exception as e:
        print("Error:", str(e))
    finally:
        # Close the browser
        await browser.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())