# Disclaimer
**This program is not affilated with Woolworths, Coles or any organisation.** Furthermore, there is no gaurantee that the information gathered and presented to the user is accurate.

# Catalogue Alerter
Ever wish someone would tell you when your favourite chocolate bar is on special? Especially after work on a Wednesday when you go do your shopping?

Catalogue Alerter is a simple one file program that searches the Woolowrths and Coles catalogues for items you have listed. It then provides a list of all matched items to you through email, file output or just in the terminal window. By being a a single Python file Catalogue Alerter has the benefit that it can be run from almost anywhere and easily setup as a scheduled task.

There is a large list of options available for users from deciding whether to search upcoming or current catalogues to limiting what pages in each catalogue the program looks at.

## Setup
Prior to using Catalogue Alerter the user must:
1. Install Python
2. Install a Chrome
3. Install the [Pyppeteer library](https://miyakogi.github.io/pyppeteer/)

Additionally, if users want to use the email functionality they will need to complete the necessary setup below.

When running the application, it is **highly recommended** to use the `--chrome-path` or `-x` optional argument to provide the path to your local Chrome executable. This is because Pyppeteer uses an old version of Chrome which does not support newer features utilised by modern websites. One of your first steps to troubleshooting the program will be to ensure you are running a local, updated version of Chrome.

## Running
To run the program, simply run the command `python catalogue_alerter.py` inside a terminal within the same directory as the `catalogue_alerter.py` file.

### Optional Arguments
```
optional arguments:
  -h, --help            show this help message and exit
  --read READ, -r READ  File name to read items to alert on (default: items.txt)
  --output-alerts, --no-output-alerts, -a
                        Append alerts to files (default: True)
  --output-items, --no-output-items, -i
                        Append items found in both catalogues to files (default: False)
  --postcode POSTCODE, -p POSTCODE
                        Postcode to use when scraping from Woolworths (required if scraping from Woolworths)
  --headless-mode, --no-headless-mode
                        Runs the browser without a user interface (default: True)
  --chrome-path CHROME_PATH, -x CHROME_PATH
                        Absolute path to the achrome file executable
  --coles, --no-coles   Searches the Coles catalogue (default: True)
  --woolworths, --no-woolworths
                        Searches the woolworths catalogue (default: True)
  --upcoming, --no-upcoming
                        To search the upcoming catalogues (default: False)
  --coles-pages COLES_PAGES
                        Provide a list of pages to search in the coles catalogue, e.g. page0,page1,page2 where providing nothing has the program search all pages
  --woolworths-pages WOOLWORTHS_PAGES
                        Provide a list of pages to search in the woolworths catalogue, e.g. page0,page1,page2 where providing nothing has the program search all pages
  --email EMAIL, -e EMAIL
                        Provide a list of email addresses to send alerts and catalogue lists to. You must have a .env file to use this functionality, see env.example.txt for an example
```


## Listing Items to Search For
The `catalogue_alerter.py` will attempt to read an `items.txt` file within the same directory. Each line in `items.txt` is treated as a separate item to search for. You may include comments in the `items.txt` file using the hashtag symbol (#). To include a hashtag in an item title symbol provide a backslash (\\) before the hashtag (\\#). Item titles are not case sensitive and spaces between text in the item title are treated as spaces in the title itself when searching for the item.

I highly recommend you test the program using items you know are in the catalogue first to get an understanding of how to write content inside the `items.txt` file.

## Sending Emails
This program uses Google's GMail to send emails and you will need to setup a Google account to use the email functionality.

`catalogue_alerter.py` will attempt to read the the variables `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` from the `.env` file in the same directory when trying to send an email. If the file or credentials do not exist or are incorrect, the program will throw an error.

How to get an app password:
1. Go to 'manage you google account'
2. Under 'security' add 2-step verification (if you have not already)
3. Go to https://myaccount.google.com/apppasswords
4. Create a new app specific password (you may choose whatever name you want)

Once you have your app password copy the content below into a file titled `.env`: <br>
GMAIL_ADDRESS="example<span>@gmail.com" <br> <!-- a <span> is used here to prevent this line from becoming a hyperlink -->
GMAIL_APP_PASSWORD="example app password" <br>

The screenshot below displays what emails look like. The subject of email was '2024-02-21 21:54 (upcoming=False) Catalogue Alert'. The command and options used were `python catalogue_alerter.py --chrome-path "C:\Program Files\Google\Chrome\Application\chrome.exe" --postcode <postcode> --no-headless-mode --no-upcoming --woolworths-pages page0,page1 --coles-pages page0,page1 --email <email>` where \<postcode> and \<email> were replaced with a postcode and email address. Note that not all options used in the command are necessary such as `--no-headless-mode`.

![Email Example](/images/Email%20Example.png)

## Troubleshooting
Ensure you are using the `--chrome-path` or `-x` optional argument to provide the path to your local Chrome executable. Pyppeteer uses an old version of Chrome which does not support newer features utilised by modern websites.

If you are experiencing a timeout error, try running the same command with `--no-headless-mode`. This will sometimes fix the issue.

Check out what the program itself is seeing using the optional argument `--no-headless-mode`. When you run the program with this optional argument, it will open a visible Chrome browser abd show you what it is seeing and doing.

## Known Bugs
At the moment there is a bug preventing the scrape of the Woolworths upcoming catalogue.