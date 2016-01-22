from bs4 import BeautifulSoup
import csv
import datetime
import logging
import logging.config
#import matplotlib.pyplot as plt
import os
import os.path
import pytz
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import sys
import time

# -*- Settings -*-

CRITICAL_MIN_TEMP = 1
CRITICAL_MAX_TEMP = 9

MIN_TEMP = 1
MAX_TEMP = 9

DEMANDED_TEMP = MIN_TEMP + ((MAX_TEMP - MIN_TEMP)/2) # dziala dla dodatnich na pewno

RESULTS_LIMIT = 10**5
LOG_DIR = 'log/'
LOGGING = {
    'version': 1,
    #'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(name)s %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(name)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.WatchedFileHandler',
            'encoding': 'utf-8',
            'filename': os.path.join(LOG_DIR, 'app.log'),
            'formatter': 'verbose',
        },
        'file_debug': {
            'level': 'DEBUG',
            'class': 'logging.handlers.WatchedFileHandler',
            'encoding': 'utf-8',
            'filename': os.path.join(LOG_DIR, 'debug.log'),
            'formatter': 'verbose',
        },
    },

    'root': {
        'handlers': ['console', 'file', 'file_debug',],
        'level': 'DEBUG',
    },
    'loggers': {
        'selenium': {
            'handlers': ['file_debug'],
            'propagate': False,
            'level': 'DEBUG',
        },
        'easyprocess': {
            'handlers': ['file_debug'],
            'propagate': False,
            'level': 'DEBUG',
        },
    }
}

# -*- EO: Settings -*-

logging.config.dictConfig(LOGGING)
log = logging.getLogger()

class Site(object):
    TIME_ZONE = pytz.timezone('Europe/Warsaw')

    def __init__(self, driver):
        self.driver = driver
        self.login()
        self.go_to_datatab()

    def login(self):
        driver = self.driver
        log.debug('Fetching main page')
        driver.get("https://www.wifisensorcloud.com/")

        #Log in
        driver.find_element_by_id("cph1_username").send_keys("szuetam@gmail.com")
        driver.find_element_by_name("ctl00$cph1$password").send_keys("DupaDupa08")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "cph1_signin")))
        driver.find_element_by_id("cph1_signin").click()
        log.info('Login sent')

    def go_to_datatab(self):
        driver = self.driver
        log.debug('Going to datatab')
        #Click "My devices"
        WebDriverWait(driver, 10).until( EC.presence_of_element_located((By.ID, "devices")))
        driver.find_element_by_id("devices").click()
        
        #Pick "sensor niwiski"
        driver.find_element_by_id("cph1_devices_sensorname_0").click()

        #Enter "View Data"
        WebDriverWait(driver, 10).until( EC.text_to_be_present_in_element_value((By.ID, "cph1_devices_selected_0"), "1"))
        WebDriverWait(driver, 10).until( EC.presence_of_element_located((By.ID, "cph1_viewgraph")))
        time.sleep(5)
        driver.find_element_by_id("cph1_viewgraph").click()
        time.sleep(11)

        #Enter datatab
        WebDriverWait(driver, 10).until( EC.presence_of_element_located((By.ID, "cph1_datatab")))
        driver.find_element_by_id("cph1_datatab").click()

        #Ensured it loaded
        WebDriverWait(driver, 10).until( EC.presence_of_element_located((By.ID, "datesortdesc")))
        log.info('On datatab')

    def page_grab(self, page_num):
        driver = self.driver
        log.debug('Grab page: %d', page_num)
        driver.execute_script("selectPage(%d)" % (page_num,))
        time.sleep(10)
        log.info('Grabbed page: %d', page_num)
        return driver.page_source

    def page_grab_since(self, last_result):
        grab_results = {}
        for page_num in range(1, 19):
            source = self.page_grab(page_num)
            grab_results.update(self.page_parse(source))
            log.info("Grabed and Parsed page %d", page_num)
            if min(grab_results) < last_result:
                break
        return grab_results

    def page_parse_row(self, row):
        row = row.findAll('tr')[0]
        aux = row.findAll('td', recursive=False)
    
        temp_value = aux[1]
        for temp_value in temp_value.findAll('span'):
            temp_value = temp_value.string
            temp_value = float(temp_value[:-2])
    
        time_value=self.TIME_ZONE.localize(datetime.datetime.strptime(aux[0].string.replace(' ', '').replace('\xa0', ' ').replace('\n', ' ')," %d/%m/%Y %H:%M:%S "))

        return time_value, temp_value

    def page_parse(self, source):
        bs2 = BeautifulSoup(source)
        bs = bs2.find(id='cph1_readingsupdatepanel')
        bs = bs.find('div', recursive=False)
        bs = bs.find('table', recursive=False)
        bs = bs.find('tbody', recursive=False)

        page_results = {}
        for row in bs.findAll('tr', recursive=False):
            time_value, temp_value = self.page_parse_row(row)
            page_results[time_value] = temp_value
        return page_results

    def results(self):
        if not hasattr(self, '_results'):
            base_path = os.path.join(os.path.dirname(__file__), 'data')
            if not os.path.exists(base_path):
                os.makedirs(base_path)
            results_path = os.path.join(base_path, 'results.csv')

            results = {}
            try:
                with open(results_path, 'r') as f:
                    csv_reader = csv.reader(f)
                    for row_no, row in enumerate(csv_reader):
                        if not row_no < RESULTS_LIMIT:
                            break
                        stamp = self.TIME_ZONE.localize(datetime.datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S'))
                        value = float(row[1])
                        results[stamp] = value
                log.info('Got %d results since %s till %s from cache.', len(results), min(results), max(results))
            except (ValueError, OSError):
                log.warning('No previous results found. Continuing with an empty dict.')

            try:
                last_result = max(results)
            except ValueError:
                last_result = self.TIME_ZONE.localize(datetime.datetime.min + datetime.timedelta(days=1))

            results.update(self.page_grab_since(last_result))

            with open(results_path, 'w') as f:
                csv_writer = csv.writer(f)
                for key in reversed(sorted(results)):
                    csv_writer.writerow([key.strftime('%Y-%m-%d %H:%M:%S'), '%.2f' % results[key]])

            self._results = results
        return self._results

    def sanepid_results(self):
        # przetwarzanie danych pod sanepid
        sanepid = {}
        
        #dla kazdego klucza z results robi sie klucz w sanepid z dokladnoscia co do godziny i uzupelnia go jesli jest lepszy niz wczesniejszy ktory tam byl 
        results = self.results()
        for k in results.keys():
            kh = datetime.datetime(k.year, k.month, k.day, k.hour)
            if not kh in sanepid.keys():
                sanepid.update({kh: results[k]})
            else:
                if abs(results[k] - DEMANDED_TEMP) < abs(DEMANDED_TEMP - sanepid[kh]):
                    sanepid.update({kh: results[k]})
        return sanepid


def initialize_virtual_display():
    log.info('Initializing display')
    display = Display(visible=0, size=(800, 600))
    display.start()
    return display

def initialize_driver():
    log.info('Starting browser driver')
    chrome_options = webdriver.ChromeOptions()
    prefs = {"profile.managed_default_content_settings.images":1}
    chrome_options.add_experimental_option("prefs",prefs)
    driver = webdriver.Chrome(
        chrome_options=chrome_options,
        service_args=["--verbose", "--log-path=%s" % (os.path.join(LOG_DIR, 'driver.log'),)],
    )

    driver.set_window_size(1400,1000)
    driver.implicitly_wait(10)
    return driver

sys.setrecursionlimit(100000)

def main():
    start_time = datetime.datetime.now()
    display = initialize_virtual_display()
    try:
        driver = initialize_driver()
        try:
            site = Site(driver)
            site.results()
        finally:
            log.info('Quitting driver...')
            driver.quit()
    finally:
        log.info('Stopping display...')
        display.stop()

    #PrintPlot(site.sanepid_results())
    delta = datetime.datetime.now() - start_time
    log.info('It took only %s, bye!', delta)
    NagiosOut(site.results())

def PrintPlot(sanepid_results):
    sorted_results_sanepid = sorted(sanepid_results.items(), key=lambda t: t[0])
    plot_data_time = []
    plot_data_temp = []
    plot_data_help = []
    plot_data_help_tick = []
    a=0
    b=0
    # figuring out range of data to print
    year_t = 2016
    month_t = 1
    month = str(year_t) + "-" + str(month_t).zfill(2)
    od = None
    #to jest ustalanie zakresu od do
    for tup in sorted_results_sanepid:
        if od == None and tup[0].strftime("%Y-%m") == str(year_t)  + "-" + str(month_t).zfill(2):
            od = b
        if tup[0].strftime("%Y-%m") == str(year_t) + "-" + str(month_t).zfill(2):
            do = b
        b=b+1
   
    #drukowanie od do
    for tup in sorted_results_sanepid[od:do]:
        a=a+1
        plot_data_help.append(a)
        #print(tup[0].strftime("%Y-%m-%d %H"))
        if tup[0].strftime("%H") == "00":
            #print(tup[0].strftime("%H") + "hura")
            plot_data_help_tick.append(a)
            if tup[0].strftime("%d") == "01":
                plot_data_time.append(tup[0].strftime("%Y-%m-%d"))
            elif tup[0].strftime("%H") == "00":
                plot_data_time.append(tup[0].strftime("%d"))
        #print(plot_data_help_tick)
        #print(plot_data_help)
        plot_data_temp.append(tup[1])
    # Plot the limit ranges.
    plt.fill_between([0, do-od], [2, 2], [0, 0], color='red', alpha=.16, linewidth=0)
    plt.fill_between([0, do-od], [10, 10], [8, 8], color='red', alpha=.16, linewidth=0)
    #plt.fill_between([0, 59], [30, 30], [15, 15], color='#0000ff', alpha=.04, linewidth=0)
    plt.plot(plot_data_help, plot_data_temp)
    plt.axis([0, do-od, 0, 10])
    plt.grid(True)
    plt.ylabel('temp')
    plt.xlabel('time',)
    plt.xticks(plot_data_help_tick, plot_data_time, rotation='vertical')
    plt.yticks([0,1,2,3,4,5,6,7,8,9,10], [0,1,2,3,4,5,6,7,8,9,10])
    plt.subplots_adjust(bottom=0.3)
    plt.title(month + " Niviski temp")
    #plt.show()
    plt.savefig(month+'.pdf')

def NagiosOut(results):
    sorted_results = sorted(results.items(), key=lambda t: t[0])

    #wyplucie danych pod nagiosa
    last_temp = sorted_results[-1][1]
    last_temp_time = sorted_results[-1][0].strftime("%Y-%m-%d %H:%M:%S")
    if last_temp < MAX_TEMP and last_temp > MIN_TEMP:
        print("OK       - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
        sys.exit(0)
    elif last_temp > critical_max_temp:
            print("CRITICAL - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(2)
    elif last_temp < CRITICAL_MIN_TEMP:
            print("CRITICAL - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(2)
    elif last_temp < MIN_TEMP:
            print("WARNING  - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(1)
    elif last_temp > MAX_TEMP:
            print("WARNING  - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(1)
    else:
            print("UNKNOWN  - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(3)

#TODO jeśli nie odczytuje sie dluzej zeby byl critical
# todo co minute ustawić i nagiosa i wifistrone


if __name__ == '__main__':
    main()
