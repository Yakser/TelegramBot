import requests
from time import sleep

TOKEN = "991918669:AAGcmQcQYprrvUj-pSA2yZfBsGGTHQDBY5Y"
MAIN_URL = f"https://api.telegram.org/bot{TOKEN}/"


def get_updates_json(request):
    #   TODO
    params = {'timeout': 100, 'offset': None}
    response = requests.get(request + 'getUpdates')
    return response.json()


def last_update(data):
    results = data['result']
    total_updates = [len(results) - 1]
    return results[total_updates]


def get_chat_id(update):
    return update['message']['chat']['id']


def send_message(chat, text):
    params = {'chat_id': chat, 'text': text}
    response = requests.post(MAIN_URL + 'sendMessage', data=params)
    return response


def main():
    update_id = last_update(get_updates_json(MAIN_URL))['update_id']
    while True:
        if update_id == last_update(get_updates_json(MAIN_URL))['update_id']:
            send_message(get_chat_id(last_update(get_updates_json(MAIN_URL))), 'test')
            update_id += 1
        sleep(0.1)



if __name__ == '__main__':
    main()

"""
chat_id = get_chat_id(last_update(get_updates_json(MAIN_URL)))
send_message(chat_id, 'Your message goes here')"""