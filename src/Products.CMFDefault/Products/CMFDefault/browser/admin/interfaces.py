##############################################################################
#
# Copyright (c) 2010 Zope Foundation and Contributors.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Schema for portal forms.
"""

import codecs

from zope.interface import Interface
from zope.schema import ASCIILine
from zope.schema import Bool
from zope.schema import Choice
from zope.schema import TextLine

from Products.CMFDefault.formlib.vocabulary import SimpleVocabulary
from Products.CMFDefault.utils import Message as _

available_policies = (
    ('email', True, _("Generate and email members' initial password")),
    ('select', False, _("Allow members to select their initial password")))

def check_encoding(value):
    encoding = ""
    try:
        encoding = codecs.lookup(value)
    except LookupError:
        pass
    return encoding != ""


class IPortalConfig(Interface):

    """Schema for portal configuration form.
    """

    email_from_name = TextLine(
        title=_("Portal 'From' name"),
        description=_("When the portal generates mail, it uses this name as "
                      "its (apparent) sender."),
        required=False,
        missing_value='')

    email_from_address = TextLine(
        title=_("Portal 'From' address"),
        description=_("When the portal generates mail, it uses this address "
                      "as its (apparent) return address."),
        required=False,
        missing_value='')

    smtp_server = TextLine(
        title=_("SMTP server"),
        description=_("This is the address of your local SMTP (out-going "
                      "mail) server."),
        required=False,
        missing_value='')

    title = TextLine(
        title=_("Portal title"),
        description=_("This is the title which appears at the top of every "
                      "portal page."),
        required=False,
        missing_value='')

    description = TextLine(
        title=_("Portal description"),
        description=_("This description is made available via syndicated "
                      "content and elsewhere. It should be fairly brief."),
        required=False,
        missing_value='')

    validate_email = Choice(
        title=_("Password policy"),
        vocabulary=SimpleVocabulary.fromTitleItems(available_policies),
        default=False)

    default_charset = ASCIILine(
        title=_("Portal default encoding"),
        description=_("Charset used to decode portal content strings. If "
                      "empty, 'ascii' is used."),
        required=False,
        constraint=check_encoding,
        default="utf-8")

    email_charset = ASCIILine(
        title=_("Portal email encoding"),
        description=_("Charset used to encode emails send by the portal. If "
                      "empty, 'utf-8' is used if necessary."),
        required=False,
        constraint=check_encoding,
        default="utf-8")

    enable_actionicons = Bool(
        title=_("Show action icons"),
        description=_("Actions available to the user are shown as textual "
                      "links. With this option enabled, they are also shown "
                      "as icons if the action definition specifies one."),
        required=False)

    enable_permalink = Bool(
        title=_("Show permalinks"),
        description=_("If permalinks are enabled then a unique identifier is "
                      "assigned to every item of content independent of it's "
                      "id or position in a site. This requires the CMFUid "
                      "tool to be installed."),
        required=False)
