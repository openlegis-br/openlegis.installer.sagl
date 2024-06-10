##parameters=ids, delta, **kw
##
from Products.CMFDefault.utils import Message as _

subset_ids = [ obj.getId() for obj in context.listFolderContents() ]
try:
    attempt = context.moveObjectsDown(ids, delta, subset_ids=subset_ids)
    if attempt == 1:
        return context.setStatus(True, _('Item moved down.'))
    elif attempt > 1:
        return context.setStatus(True, _('Items moved down.'))
    else:
        return context.setStatus(False, _('Nothing to change.'))
except ValueError:
    return context.setStatus(False, _('ValueError: Move failed.'))
