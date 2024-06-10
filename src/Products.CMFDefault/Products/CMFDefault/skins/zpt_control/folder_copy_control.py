##parameters=ids, **kw
##title=Copy objects from a folder to the clipboard
##
from Products.CMFDefault.exceptions import CopyError
from Products.CMFDefault.utils import Message as _

try:
    context.manage_copyObjects(ids, context.REQUEST)
    if len(ids) == 1:
        return context.setStatus(True, _('Item copied.'))
    else:
        return context.setStatus(True, _('Items copied.'))
except CopyError:
    return context.setStatus(False, _('CopyError: Copy failed.'))
