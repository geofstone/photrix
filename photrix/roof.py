__author__ = "Eric Dose :: New Mexico Mira Project, Albuquerque"

import winsound
from time import sleep
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from util import hhmm_from_datetime_utc

STATUS_URL = 'https://beta.deepskywest.com/status.php'
HTTP_OK_CODE = 200  # "OK. The request has succeeded."
MAX_CONSECUTIVE_TIMEOUTS = 60
SECONDS_BETWEEN_STARTUP_QUERIES = 5
SECONDS_BETWEEN_ONGOING_QUERIES = 60
QUERIES_REQUIRED = 1
TAG_TO_TEST = 'beta roof status'
CLOSED_TAGS = ['closing', 'closed']
OPENED_TAGS = ['opening', 'open']
# PATTERN_HAS_OPENED = 1 * ['closed'] + QUERIES_REQUIRED * ['open']
# PATTERN_HAS_CLOSED = 1 * ['open'] + QUERIES_REQUIRED * ['closed']
SOUND_HAS_OPENED = 'SystemAsterisk'  # = Win 10 Asterisk; use Sonata/Windows Error.wav
SOUND_HAS_CLOSED = 'SystemHand'      # = Win 10 Critical Stop; use Sonata/Windows Critical Stop.wav
SOUND_REPETITIONS = 100


def trial():
    """ Make noise if roof opens or closes, according to small HTML table from DeepSkyWest.com"""
    print('Playing OPENED sound twice, then CLOSED sound twice...')
    winsound.PlaySound(SOUND_HAS_OPENED, winsound.SND_ALIAS)
    winsound.PlaySound(SOUND_HAS_OPENED, winsound.SND_ALIAS)
    winsound.PlaySound(SOUND_HAS_CLOSED, winsound.SND_ALIAS)
    winsound.PlaySound(SOUND_HAS_CLOSED, winsound.SND_ALIAS)

    status_list = (QUERIES_REQUIRED + 1) * ['-']
    n_timeouts = 0
    while True:
        r = None  # (initialize to keep IDE happy)
        try:
            r = requests.get(STATUS_URL)
        except requests.exceptions.Timeout:
            n_timeouts += 1
            print(' >>>>> Warning:', str(n_timeouts), 'consecutive timeouts.')
            if n_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                print(' >>>>> ERROR:', str(MAX_CONSECUTIVE_TIMEOUTS), 'consecutive timeouts; stopping')
                exit(1)
            sleep(10)
            continue
        except requests.exceptions.RequestException as e:
            print(e)
            exit(1)
        if r.status_code != HTTP_OK_CODE:
            print(' >>>>> Could not get', STATUS_URL)
            return
        n_timeouts = 0
        soup = BeautifulSoup(r.text, 'html.parser')
        trs = soup.find_all('tr')
        roof_status = '-'
        for tr in trs:
            tds = tr.find_all('td')
            if tds[0].text.lower() == TAG_TO_TEST:
                roof_status = tds[1].text.lower()
                break
        status_list.append(roof_status)  # so that earliest status is first list item (time reads L->R).
        status_list = status_list[1:]
        hhmm = hhmm_from_datetime_utc(datetime.now(timezone.utc))
        # print(hhmm + ': is', status_list[-1], ' >>> ', '.'.join(status_list))
        print(hhmm + ': is', status_list[-1])
        if has_opened(status_list):
            print(' >>>>> OPENED at', hhmm)
            for i in range(SOUND_REPETITIONS):
                winsound.PlaySound(SOUND_HAS_OPENED, winsound.SND_ALIAS)
            # return  # let's try leaving it running for further notifications (20200219).
        elif has_closed(status_list):
            print(' >>>>> CLOSED at', hhmm)
            for i in range(SOUND_REPETITIONS):
                winsound.PlaySound(SOUND_HAS_CLOSED, winsound.SND_ALIAS)
            # return  # let's try leaving it running for further notifications (20200219).
        else:
            if any([status == '-' for status in status_list]):
                sleep(SECONDS_BETWEEN_STARTUP_QUERIES)
            else:
                sleep(SECONDS_BETWEEN_ONGOING_QUERIES)


def has_opened(status_list):
    return (status_list[0] in CLOSED_TAGS) and (status_list[1] in OPENED_TAGS)


def has_closed(status_list):
    return (status_list[0] in OPENED_TAGS) and (status_list[1] in CLOSED_TAGS)


if __name__ == '__main__':
    trial()
