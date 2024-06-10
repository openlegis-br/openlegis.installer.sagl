##parameters=ids, delta, **kw
##
from Products.CMFDefault.utils import Message as _

subset_ids = [ obj.getId() for obj in context.listFolderContents() ]
try:
    attempt = context.moveObjectsUp(ids, delta, subset_ids=subset_ids)
    if attempt == 1:
        return context.setStatus(True, _('Item moved up.'))
    elif attempt > 1:
        return context.setStatus(True, _('Items moved up.'))
    else:
        return context.setStatus(False, _('Nothing to change.'))
except ValueError:
    return context.setStatus(False, _('ValueError: Move failed.'))
