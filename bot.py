import requests
import json
from time import sleep

TOKEN = "991918669:AAGcmQcQYprrvUj-pSA2yZfBsGGTHQDBY5Y"
MAIN_URL = f"https://api.telegram.org/bot{TOKEN}/"


def get_data():
    with requests.get("https://api.github.com/orgs/fedora-infra/repos") as r:
        data = json.loads(r.text)
    return data


def get_forks_count():
    output_message = ""
    for x in get_data():
        output_message += x["name"] + ": " + str(x["forks_count"]) + "\n"
    return output_message


def get_repo_forks(name):
    for x in get_data():
        if name in x["name"]:
            return x["forks"]
    return "Repository not found."


def get_updates_json(request):
    params = {'timeout': 10, 'offset': None}
    response = requests.get(request + 'getUpdates', data=params)
    return response.json()


def last_update(data):
    results = data['result']
    return results[len(results) - 1]


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
            last_chat_text = last_update(get_updates_json(MAIN_URL))['message']['text']

            send_message(get_chat_id(last_update(get_updates_json(MAIN_URL))), get_repo_forks(last_chat_text))

            update_id += 1
        sleep(0.1)


if __name__ == '__main__':
    main()
