#!/usr/bin/env python
#
# A library that provides a Python interface to the Telegram Bot API
# Copyright (C) 2015-2018
# Leandro Toledo de Souza <devs@python-telegram-bot.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser Public License for more details.
#
# You should have received a copy of the GNU Lesser Public License
# along with this program.  If not, see [http://www.gnu.org/licenses/].

import pytest

from telegram import ChatPermissions


@pytest.fixture(scope="class")
def chat_permissions():
    return ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                           can_send_polls=True, can_send_other_messages=True,
                           can_add_web_page_previews=True, can_change_info=True,
                           can_invite_users=True, can_pin_messages=True)


class TestChatPermissions(object):
    can_send_messages = True
    can_send_media_messages = True
    can_send_polls = True
    can_send_other_messages = False
    can_add_web_page_previews = False
    can_change_info = False
    can_invite_users = None
    can_pin_messages = None

    def test_de_json(self, bot):
        json_dict = {
            'can_send_messages': self.can_send_messages,
            'can_send_media_messages': self.can_send_media_messages,
            'can_send_polls': self.can_send_polls,
            'can_send_other_messages': self.can_send_other_messages,
            'can_add_web_page_previews': self.can_add_web_page_previews,
            'can_change_info': self.can_change_info,
            'can_invite_users': self.can_invite_users,
            'can_pin_messages': self.can_pin_messages
        }
        permissions = ChatPermissions.de_json(json_dict, bot)

        assert permissions.can_send_messages == self.can_send_messages
        assert permissions.can_send_media_messages == self.can_send_media_messages
        assert permissions.can_send_polls == self.can_send_polls
        assert permissions.can_send_other_messages == self.can_send_other_messages
        assert permissions.can_add_web_page_previews == self.can_add_web_page_previews
        assert permissions.can_change_info == self.can_change_info
        assert permissions.can_invite_users == self.can_invite_users
        assert permissions.can_pin_messages == self.can_pin_messages

    def test_to_dict(self, chat_permissions):
        permissions_dict = chat_permissions.to_dict()

        assert isinstance(permissions_dict, dict)
        assert permissions_dict['can_send_messages'] == chat_permissions.can_send_messages
        assert (permissions_dict['can_send_media_messages']
                == chat_permissions.can_send_media_messages)
        assert permissions_dict['can_send_polls'] == chat_permissions.can_send_polls
        assert (permissions_dict['can_send_other_messages']
                == chat_permissions.can_send_other_messages)
        assert (permissions_dict['can_add_web_page_previews']
                == chat_permissions.can_add_web_page_previews)
        assert permissions_dict['can_change_info'] == chat_permissions.can_change_info
        assert permissions_dict['can_invite_users'] == chat_permissions.can_invite_users
        assert permissions_dict['can_pin_messages'] == chat_permissions.can_pin_messages
