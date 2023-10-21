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

async def scrape_coles_catalogue(browser, upcoming: bool = True, catalogue_pages: list[str] = ['page1', 'page2', 'page3']):
    '''
    Scrapes pages from the coles catalogue (if it is available).
    '''
    # Create a new page and go to the cole catalogue website
    page = await browser.newPage()
    await page.goto("https://www.coles.com.au/catalogues")

    # Open up the catalogue TODO: Test when upcoming is false. TODO: Handle case of next week's catalogue being not available
    catalogue_button = await page.waitForXPath('//a[@aria-label="View next week\'s catalogue"]') if upcoming else await page.waitForXPath('//a[@aria-label="View this week\'s catalogue"]')
    catalogue_url = await page.evaluate('(element) => element.getAttribute("href")', catalogue_button)
    await page.goto('https://www.coles.com.au' + catalogue_url)

    # Retrieve item titles (got help from ChatGPT for code below)
    await page.waitForXPath('//a[@aria-label="Specials of the Week"]') # Wait for the anchors on the pages to load
    titles = await page.evaluate('''() => {
    const titles = [];
    const elements = document.querySelectorAll(\''''+ ''.join(f'li.{cp}, '.format(cp) for cp in catalogue_pages)[:-2] + ''' .slide-content.objloaded a');
    elements.forEach((element) => {
        if (element instanceof HTMLAnchorElement) {
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
        browser = await launch(executablePath="C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
        titles = await scrape_coles_catalogue(browser, upcoming=False)
        print('from catalogue:', titles)
    except Exception as e:
        print("Error:", str(e))
    finally:
        # Close the browser
        await browser.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())