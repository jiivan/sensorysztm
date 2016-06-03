from bs4 import BeautifulSoup
import csv
import calendar
import datetime
import logging
import logging.config
import math
import matplotlib.dates
import matplotlib.pyplot as plt
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
            base_path = os.path.dirname(__file__)
            data_path = os.path.join(base_path, 'data')
            tmp_path = os.path.join(base_path, 'tmp')
            output_path = os.path.join(base_path, 'output')
            for dirpath in (data_path, tmp_path, output_path):
                if not os.path.exists(dirpath):
                    os.makedirs(dirpath)
            results_path = os.path.join(data_path, 'results.csv')

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
            kh = self.TIME_ZONE.localize(datetime.datetime(k.year, k.month, k.day, k.hour))
            if (kh not in sanepid) or (abs(results[k] - DEMANDED_TEMP) < abs(DEMANDED_TEMP - sanepid[kh])):
                sanepid[kh] = results[k]
        return sanepid

    def results_holes(self):
        """Sprawdzenie czy nie ma dziur w wynikach."""
        last_stamp = None
        for stamp in sorted(self.results()):
            if last_stamp is None:
                last_stamp = stamp
                continue
            delta = stamp - last_stamp
            if delta > datetime.timedelta(hours=1):
                log.warning('Hole %s between %s and %s', delta, last_stamp, stamp)
            last_stamp = stamp


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

    print_plot(site.sanepid_results())
    print_plot(site.results(), '-full')
    pdf_table(site.sanepid_results())
    dump_csv(site.results())
    delta = datetime.datetime.now() - start_time
    site.results_holes()
    log.info('It took only %s, bye!', delta)
    NagiosOut(site.results())

def get_dates_from_argv(data):
    if len(sys.argv) < 2:
        end_date = max(data)
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = datetime.datetime.strptime(sys.argv[1], '%Y-%m')
        end_date = start_date.replace(day=calendar.monthrange(start_date.year, start_date.month)[1])
    def _localize(d):
        if (d.tzinfo is not None) and (d.tzinfo.utcoffset(d) is not None):
            return d
        return Site.TIME_ZONE.localize(d)
    start_date = _localize(start_date)
    end_date = _localize(end_date)
    return start_date, end_date

def dump_csv(results):
    start_date, end_date = get_dates_from_argv(results)
    log.info('dump_csv %s-%s', start_date, end_date)

    base_path = os.path.dirname(__file__)
    output_path = os.path.join(base_path, 'output')
    results_path = os.path.join(output_path, start_date.strftime('temp-%Y-%m.csv'))
    with open(results_path, 'w') as f:
        csv_writer = csv.writer(f)
        for key in sorted(results):
            if key < start_date or key > end_date:
                continue
            csv_writer.writerow([key.strftime('%Y-%m-%d %H:%M:%S'), '%.2f' % results[key]])

def print_plot(sanepid_results, suffix=''):
    log.info('Plotting...')
    x_ticks = []
    y_values = []
    x_values = []
    x_ticks_values = []
    start_date, end_date = get_dates_from_argv(sanepid_results)

    log.info('print_plot %s - %s', start_date, end_date)

    for stamp in sorted(sanepid_results):
        if stamp < start_date:
            continue
        if stamp >= end_date:
            break
        x_values.append(matplotlib.dates.date2num(stamp))
        y_values.append(sanepid_results[stamp])

        if stamp.hour == 0:
            x_stamp = matplotlib.dates.date2num(stamp)
            if stamp.day == 1:
                label = stamp.strftime("%Y-%m-%d")
            else:
                label = stamp.strftime("%d")
            if x_ticks and x_ticks[-1] == label:
                continue
            x_ticks.append(label)
            x_ticks_values.append(x_stamp)
    # Plot the limit ranges.
    plt.fill_between([x_values[0], x_values[-1]], [2, 2], [0, 0], color='red', alpha=.16, linewidth=0)
    plt.fill_between([x_values[0], x_values[-1]], [10, 10], [8, 8], color='red', alpha=.16, linewidth=0)
    plt.plot_date(x_values, y_values, '-')
    plt.axis([x_values[0], x_values[-1], 0, 10])
    plt.grid(True)
    plt.ylabel('temp')
    plt.xlabel('time',)
    plt.xticks(x_ticks_values, x_ticks, rotation='vertical')
    plt.yticks(range(11), range(11))
    plt.subplots_adjust(bottom=0.3)

    plt.title("%s Niviski temp" % (start_date.strftime('%Y-%m'),))
    #plt.show()
    plt.savefig('output/temp-%s%s-wykres.pdf' % (start_date.strftime('%Y-%m'), suffix))

def pdf_table(sanepid_results):
    month_d, end_date = get_dates_from_argv(sanepid_results)
    month_d = month_d.date()

    log.info('pdf_table %s -%s', month_d, end_date)

    latex_template = r'''
        \documentclass[6pt]{article}
        \usepackage[margin=1cm]{geometry}
        \usepackage{rotating}
        \usepackage{xcolor}
        \pagestyle{empty}
        \begin{document}
        \begin{center}
            {\fontsize{1.6cm}{0.81cm}\selectfont %s}

            %s
        \end{center}
        \end{document}
    '''
    tabular_template = r'''
            \renewcommand{\tabcolsep}{0.2mm}
            \renewcommand{\arraystretch}{0.45}
            \begin{tabular}{%s}
                \hline
                %%s \\
                \hline
            \end{tabular}
    '''
    cols = r'|p{0.4cm} p{2.9mm} p{5mm}|' * 10
    tabular_template %= cols


    days = {}
    month_days = calendar.monthrange(month_d.year, month_d.month)[1]
    for offset in range(math.ceil(month_days / 10)*10):
        date = month_d + datetime.timedelta(days=offset)
        days[date] = [None] * 24

    for stamp in sanepid_results:
        try:
            days[stamp.date()][stamp.hour] = sanepid_results[stamp]
        except KeyError:
            continue

    table = []
    sorted_days = sorted(days)
    for weeknum in range(math.ceil(len(days) / 10)):
        for hour in range(24):
            current_row = []
            table.append(current_row)
            for weekday in range(weeknum*10, (weeknum*10)+10):
                try:
                    date = sorted_days[weekday]
                except IndexError:
                    break
                if date.month != month_d.month:
                    current_row.extend(['']*3)
                    continue
                if not hour:
                    date_str = r'\raisebox{0.0cm}{\rotatebox{00}{%s}}' % date.strftime('%Y-%m-%d')
                    date_str = r'%s' % date.strftime('%d')
                else:
                    date_str = ''
                current_row.append(date_str)
                current_row.append('%02d' % hour)
                try:
                    value = days[date][hour]
                    #import random
                    #if random.random() < 0.1:
                    #    if random.random() < 0.5:
                    #        value = MIN_TEMP - 1
                    #    else:
                    #        value = MAX_TEMP + 1
                    current_row.append('%.1f' % value)
                    if value < MIN_TEMP:
                        current_row[-1] = r'\textcolor{blue}{%s}' % current_row[-1]
                    elif value > MAX_TEMP:
                        current_row[-1] = r'\textcolor{red}{%s}' % current_row[-1]
                except TypeError:
                    current_row.append('--')
    latex_rows = (' & '.join(r'{\fontsize{0.02cm}{0.01cm}\selectfont %s}' % v for v in row) for row in table)
    latex_tables = []
    for cnt, row in enumerate(latex_rows):
        if cnt % 24 == 0:
            log.debug('cnt %d new row', cnt)
            if cnt:
                latex_table = ' \\\\\n'.join(current_week)
                latex_tables.append(tabular_template % latex_table)
            current_week = []
        current_week.append(row)
        if cnt == len(table)-1:
            latex_table = ' \\\\\n'.join(current_week)
            latex_tables.append(tabular_template % latex_table)

    filename = month_d.strftime("tmp/temp-%Y-%m-tabela.tex")
    with open(filename, 'w') as f:
        f.write(latex_template % (month_d.strftime('%Y-%m'), '\n'.join(latex_tables),))

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
