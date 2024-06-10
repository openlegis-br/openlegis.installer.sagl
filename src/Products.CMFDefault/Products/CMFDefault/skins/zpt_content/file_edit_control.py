##parameters=file, **kw
##
from Products.CMFDefault.exceptions import ResourceLockedError
from Products.CMFDefault.utils import Message as _

try:
    context.edit(file=file)
    return context.setStatus(True, _('File changed.'))
except ResourceLockedError as errmsg:
    return context.setStatus(False, errmsg)
