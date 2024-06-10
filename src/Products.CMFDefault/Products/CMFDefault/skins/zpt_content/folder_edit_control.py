##parameters=title, description, **kw
##
from Products.CMFDefault.utils import Message as _

if title!=context.Title() or description != context.Description():
    context.setTitle(title)
    context.setDescription(description)
    context.reindexObject()
    return context.setStatus(True, _('Metadata changed.'))
else:
    return context.setStatus(False, _('Nothing to change.'))
