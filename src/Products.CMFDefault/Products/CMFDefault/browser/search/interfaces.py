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
"""Search Form Schema.
"""

from datetime import date
from datetime import timedelta

from DateTime import DateTime
from zope.component import getUtility
from zope.interface import directlyProvides
from zope.interface import Interface
from zope.schema import ASCIILine
from zope.schema import Choice
from zope.schema import List
from zope.schema import TextLine
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

from Products.CMFCore.interfaces import ICatalogTool
from Products.CMFCore.interfaces import IMembershipTool
from Products.CMFCore.interfaces import ITypesTool
from Products.CMFDefault.utils import Message as _
from Products.CMFDefault.utils import decode


def status_vocab(context):
    """Provides a list of workflow states"""
    ctool = getUtility(ICatalogTool)
    values = [SimpleTerm('', '', _("-- any --"))]
    values += [ SimpleTerm(v, str(v), _(decode(v)))
                for v in ctool.uniqueValuesFor('review_state') ]
    return SimpleVocabulary(values)
directlyProvides(status_vocab, IContextSourceBinder)

def subject_vocab(context):
    """Provides a list of subject keywords"""
    ctool = getUtility(ICatalogTool)
    values = [SimpleTerm('', '', _("-- any --"))]
    values += [SimpleTerm(v, v.encode('hex'), decode(v))
               for v in ctool.uniqueValuesFor('Subject')]
    return SimpleVocabulary(values)
directlyProvides(subject_vocab, IContextSourceBinder)

def date_vocab(context):
    """Provides a list of dates for searching with"""
    mtool = getUtility(IMembershipTool)
    dates = [SimpleTerm(None, 'ever', _('Ever'))]
    if not mtool.isAnonymousUser():
        member = mtool.getAuthenticatedMember()
        login_time = member.getProperty('last_login_time')
        if not hasattr(login_time, 'parts'):
            login_time = DateTime(login_time)
        login = date(*login_time.parts()[:3])
        dates.append(SimpleTerm(
            login, 'last_login', _('Last login'))
                     )

    today = date.today()
    dates.append(SimpleTerm(today - timedelta(days=1),
                            'yesterday',
                            _('Yesterday')
                            )
                 )
    dates.append(SimpleTerm(today - timedelta(days=7),
                            'last_week',
                            _('Last week')
                            )
                 )
    dates.append(SimpleTerm(today - timedelta(days=31),
                            'last_month',
                            _('Last month')
                            )
                 )
    return SimpleVocabulary(dates)
directlyProvides(date_vocab, IContextSourceBinder)

def type_vocab(context):
    """Provides a list of portal types"""
    ttool = getUtility(ITypesTool)
    types = ttool.listTypeInfo()
    terms = [SimpleTerm('', '', _("-- any --"))]
    terms += [ SimpleTerm(t.getId(), t.getId(), decode(t.Title()))
               for t in types ]
    return SimpleVocabulary(terms)
directlyProvides(type_vocab, IContextSourceBinder)


class ISearchSchema(Interface):

    review_state = List(
        title=_('Review Status'),
        description=_("As a reviewer, you may search for items based on "
                      "their review state. If you wish to constrain results "
                      "to items in certain states, select them from this "
                      "list."),
        value_type=Choice(source=status_vocab),
        default=[''])

    SearchableText = TextLine(
        title=_('Full Text'),
        description=_("For a simple text search, enter your search term "
                      "here. Multiple words may be found by combining them "
                      "with AND and OR. This will find text in items' "
                      "contents, title and description."),
        required=False)

    Title = TextLine(
        title=_('Title'),
        required=False)

    Subject = List(
        title=_('Subject'),
        description=_(""),
        value_type=Choice(source=subject_vocab),
        default=[''])

    Description = TextLine(
        title=_('Description'),
        description=_("You may also search the items' descriptions and "
                      "titles specifically. Multiple words may be found by "
                      "combining them with AND and OR."),
        required=False)

    created = Choice(
        title=_('Find new items since...'),
        description=_("You may find only recent items by selecting a "
                      "time-frame."),
        source=date_vocab,
        required=False)

    portal_type = List(
        title=_('Item type'),
        description=_("You may limit your results to particular kinds of "
                      "items by selecting them above. To find all kinds of "
                      "items, do not select anything."),
        value_type=Choice(source=type_vocab),
        default=[''])

    listCreators = ASCIILine(
        title=_('Creator'),
        description=_("To find items by a particular user only, enter their "
                      "username above. Note that you must enter their "
                      "username exactly."),
        required=False)
