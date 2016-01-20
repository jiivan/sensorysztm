import platform
#import matplotlib.pyplot as plt
import linecache
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time
import datetime
import pickle
from bs4 import BeautifulSoup
import operator
import os
import os.path
import sys
import pytz

tz = pytz.timezone('Europe/Warsaw')
min_temp = 1
max_temp = 9
last_temp = 0
last_temp_time = None

demanded_temp = min_temp + ((max_temp - min_temp)/2) # dziala dla dodatnich na pewno

critical_min_temp = 1
critical_max_temp = 9

source_path = os.path.dirname(os.path.realpath(sys.argv[0])) + '/'


def PrintException():
        exc_type, exc_obj, tb = sys.exc_info()
        f = tb.tb_frame
        lineno = tb.tb_lineno
        filename = f.f_code.co_filename
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))


def PageGrab(Num):
    #TODO add closing chrome window engin etc after execution
    #TODO optimize to not load images css etc
    display = Display(visible=0, size=(800, 600))
    display.start()
    try:
        #zależne od platformy
        chromeOptions = webdriver.ChromeOptions()
        prefs = {"profile.managed_default_content_settings.images":1}
        chromeOptions.add_experimental_option("prefs",prefs)
        if platform.system() == "Darwin":
            driver = webdriver.Chrome(chrome_options=chromeOptions)
        else:
            chromedriver = "/home/mateusz.kowalczyk/wifitempsensor/wifitempsensor/chromedriver"
            if not os.access(chromedriver, os.X_OK):
                print("chromedriver nie jest wykonywalny")
                sys.exit(1)
            os.environ["webdriver.chrome.driver"] = chromedriver
            driver = webdriver.Chrome(chromedriver)

        driver.set_window_size(1400,1000)
        driver.implicitly_wait(10)

        driver.get("https://www.wifisensorcloud.com/")

        #Log in
        elem = driver.find_element_by_id("cph1_username").send_keys("szuetam@gmail.com")
        elem2 = driver.find_element_by_name("ctl00$cph1$password").send_keys("DupaDupa08")
        elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "cph1_signin"))
        )
        guzik = driver.find_element_by_id("cph1_signin")
        guzik.click()

        #Click "My devices"
        elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "devices"))
        )
        mydev = driver.find_element_by_id("devices")
        mydev.click()
        
        #Pick "sensor niwiski"
        driver.find_element_by_id("cph1_devices_sensorname_0").click()

        #Enter "View Data"
        elem = WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element_value((By.ID, "cph1_devices_selected_0"), "1")
        )
        elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "cph1_viewgraph"))
        )
        time.sleep(5)
        driver.find_element_by_id("cph1_viewgraph").click()
  
        #print("start 10sec wait")
        #time.sleep(10)
        #print("end wait")
        time.sleep(11)

        #Enter datatab
        elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "cph1_datatab"))
        )
        driver.find_element_by_id("cph1_datatab").click()

        #Ensured it loaded
        elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "datesortdesc"))
        )
        driver.execute_script("selectPage(" + str (Num) + ")")
        time.sleep(10)
        with open(source_path + 'data/source.html', 'wb') as handle:
            pickle.dump(driver.page_source, handle)

        driver.quit()
    except:
        display.stop()
        global last_temp
        global last_temp_time
        print("UNKNOWN  - no read temp sth went wrong " + str(last_temp) + " @ " + str(last_temp_time) + ". | /=" + str(last_temp))
        PrintException()
        sys.exit(3)
    display.stop()



#os.system("python3 test-selenium.py >/dev/null 2>/dev/null")

sys.setrecursionlimit(100000)

results = {}

def PageParse():
    with open(source_path + 'data/source.html', 'rb') as handle:
        page_source = pickle.load(handle)

    t = page_source
    bs2 = BeautifulSoup(t)
    bs = bs2.find(id='cph1_readingsupdatepanel')
    bs = bs.find('div', recursive=False)
    bs = bs.find('table', recursive=False)
    bs = bs.find('tbody', recursive=False)
    
    for row in bs.findAll('tr', recursive=False):
        #print("row should be tr big----------------------------------------B")
        #print(row)
        row = row.findAll('tr')[0]
        #print("row should be 1st tr small in big one-----------------------S")
        #print(row)
        aux = row.findAll('td', recursive=False)
    
        #print("aux should be sth")
        #print(aux)
        #print("aux[1] should be temp---------------------------------------t")
        #print(aux[1])
        temp_value = aux[1]
        #print(temp_value.findAll('span'))
        for temp_value in temp_value.findAll('span'):
            #print(temp_value)
            temp_value = temp_value.string
            temp_value = float(temp_value[:-2])
    
        #print("aux[0] should be datetime-----------------------------------temp")
        #print(aux[0])
        time_value=\
                    tz.localize(datetime\
                       .datetime\
                            .strptime\
                               (\
                                   aux[0]\
                                       .string\
                                            .replace(' ', '')\
                                                .replace('\xa0', ' ')\
                                                    .replace('\n', ' '),\
                                " %d/%m/%Y %H:%M:%S "\
                            ))

        results[time_value] = temp_value
        #print(time_value, results[time_value])
    
    #tu sie konczy parsowanie i zaczyna sie przetwarzanie zapisywanie itp
    
    #ladowanie danych calosciowych
    try:
        new = pickle.load(open(source_path + 'data/data.dat', 'rb'))
        results.update(new)
    except:
        print("No base data file existed before")

    # przetwarzanie danych pod sanepid
    sanepid = {}
    
    #dla kazdego klucza z results robi sie klucz w sanepid z dokladnoscia co do godziny i uzupelnia go jesli jest lepszy niz wczesniejszy ktory tam byl 
    for k in results.keys():
        kh = datetime.datetime(k.year, k.month, k.day, k.hour)
        if not kh in sanepid.keys():
            sanepid.update({kh: results[k]})
        else:
            if abs(results[k] - demanded_temp) < abs(demanded_temp - sanepid[kh]):
                sanepid.update({kh: results[k]})

    #zapis uzupelnionych juz results do pliku
    pickle.dump(results, open(source_path + 'data/data.dat', 'wb'))

    #posortowane wersje results i sanepid
    sorted_results = sorted(results.items(), key=operator.itemgetter(0))
    global sorted_results_sanepid
    sorted_results_sanepid = sorted(sanepid.items(), key=operator.itemgetter(0))
    #for res in sorted_results_sanepid:
    #    print(res)
    #zapis danych sanepidowych
    pickle.dump(sanepid, open(source_path + 'data/data_sanepid.dat', 'wb'))

    #wyplucie danych pod nagiosa
    global last_temp
    global last_temp_time
    last_temp = sorted_results[-1][1]
    last_temp_time = sorted_results[-1][0].strftime("%Y-%m-%d %H:%M:%S")

def PrintPlot():
    global sorted_results_sanepid
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

def NagiosOut():
    global last_temp
    global last_temp_time
    if last_temp < max_temp and last_temp > min_temp:
        print("OK       - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
        sys.exit(0)
    elif last_temp > critical_max_temp:
            print("CRITICAL - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(2)
    elif last_temp < critical_min_temp:
            print("CRITICAL - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(2)
    elif last_temp < min_temp:
            print("WARNING  - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(1)
    elif last_temp > max_temp:
            print("WARNING  - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(1)
    else:
            print("UNKNOWN  - temp " + str(last_temp) + " @ " + last_temp_time + ". | /=" + str(last_temp))
            sys.exit(3)

def PageGrabParseAll():
    for Num in range(18):
        Num=Num+1
        PageGrab(Num)
        PageParse()
        print("Grabed and Parsed page " + str(Num))

PageGrabParseAll()
PrintPlot()
NagiosOut()

#TODO jeśli nie odczytuje sie dluzej zeby byl critical
# todo if ustawic w kolejnosci zeby to mialo sens
# todo co minute ustawić i nagiosa i wifistrone
