import argparse
import re
import asyncio
from pyppeteer import launch

OUT_FOLDER = 'out'

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

async def scrape_upcoming_coles_catalogue_pages(browser, catalogue_pages_to_scrape: list[str] = ['page1', 'page2']):
    '''
    Scrapes pages from the upcoming coles catalogue (if it is available).
    '''    
    # Create a new page and go to coles catalogue website
    page = await browser.newPage()  # Launch a headless Chromium browser
    await page.goto("https://www.coles.com.au/catalogues")

    # TODO: Check if catalogue is available (perhaps using: current_catalogue_button = await page.waitForXPath('//a[@aria-label="View next week\'s catalogue"]'))
    await page.evaluate(r'''document.evaluate('//a[@aria-label="View next week\'s catalogue"]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click();''')

    # TODO: Fix error
        # Future exception was never retrieved
        # future: <Future finished exception=NetworkError('Protocol error (Target.sendMessageToTarget): No session with given id')>
        # pyppeteer.errors.NetworkError: Protocol error (Target.sendMessageToTarget): No session with given id
    await page.waitForXPath('//li[@class="page1"]')    

    await page.screenshot({'path': f'{OUT_FOLDER}/catalogue_screenshot.png'})
    
    await page.close()

async def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Catalogue Alerter')
    parser.add_argument('--read', '-r', type=str, default='items.txt', help='File name to read items to alert on')
    parser.add_argument('--output-alerts', '-o', type=str, default='alerts.txt', help='File name to output alerts')
    parser.add_argument('--output-catalogue', '-c', type=str, help='File name to output catalogue items')
    args = parser.parse_args()

    # Read items to alert on
    alert_items = read_alert_items(args.read)
    print(alert_items)

    try:
        browser = await launch()
        await scrape_upcoming_coles_catalogue_pages(browser)
    except Exception as e:
        print("Error:", str(e))
    finally:
        # Close the browser
        await browser.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())